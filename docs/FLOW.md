# Developer Flow Documentation

This document explains how the PGAI Voice Agent Tester executes, from entry point to transcript storage, in execution order.

---

## Entrypoints

### `test_call.py`
CLI script to initiate a test call to Pretty Good AI's line (805-439-8008) using a chosen scenario.

**Usage:**
- `python test_call.py --scenario <name>` - Run specific scenario
- `python test_call.py --list` - List all available scenarios
- `python test_call.py` - Defaults to `appointment_scheduling`

**When used:** Developer wants to run a test call. This is the primary entry point for testing.

---

### `src/phone_system.py`
Flask application with Twilio webhook handlers. Responds to incoming webhooks from Twilio during active calls.

**Webhook endpoints:**
- `POST /voice` - Initial call setup (Twilio calls this when call connects)
- `POST /handle-agent-response` - Agent speech received (called after each agent utterance)
- `POST /call-status` - Call status updates (called when call completes)
- `POST /recording-complete` - Recording ready (called when Twilio finishes processing recording)

**When used:** Automatically invoked by Twilio during live calls. Also contains `make_call()` function called by `test_call.py`.

---

### `analyze_transcript.py`
CLI utility to inspect a single call transcript by `call_sid` after a call completes.

**Usage:** `python analyze_transcript.py <call_sid>`

**When used:** Developer wants to review a completed call's transcript, turn-by-turn conversation, confidence scores, and optional Whisper transcription.

---

## End-to-End Flow (Step by Step)

### 1. Developer Runs a Test Call

**Command:** `python test_call.py --scenario <name>`

**Execution:**
- `test_call.py` imports `make_call()` from `src.phone_system`
- Calls `make_call(scenario_name)` with the selected scenario name
- `make_call()` uses Twilio REST API to initiate an outbound call:
  - From: `TWILIO_PHONE_NUMBER` (your Twilio number)
  - To: `TEST_LINE_NUMBER` (805-439-8008)
  - Webhook URL: `{BASE_URL}/voice?scenario={scenario_name}`
  - Recording: Enabled (`record=True`)
- Returns `call_sid` (Twilio call identifier)
- `test_call.py` prints the call SID and waits (keeps Flask server running)

---

### 2. Inbound Call Setup (`/voice`)

**Trigger:** Twilio POSTs to `POST /voice` when call connects

**Execution in `phone_system.py`:**
- Extracts `CallSid` and `scenario` query parameter from request
- Creates `CallSession` object:
  - Stores `call_sid`, `scenario_name`, initializes empty `transcript` list
  - Loads scenario via `scenario_loader.get_scenario_by_name(scenario_name)`
  - Creates `ConversationManager` instance with scenario
  - Stores session in `active_calls` dict (keyed by `call_sid`)
- Returns TwiML response:
  - `<Gather>` instruction to listen for agent speech
  - Routes next webhook to `/handle-agent-response`
  - Fallback: if no speech detected, says "Hello?" and hangs up

**Key point:** Patient bot does NOT speak first. Clinic agent speaks first, and we listen.

---

### 3. Agent Speaks → Webhook Receives STT Text

**Trigger:** Twilio POSTs to `POST /handle-agent-response` after agent finishes speaking

**Execution in `phone_system.py`:**
- Extracts from request:
  - `CallSid` - Identifies which call
  - `SpeechResult` - Agent's transcribed speech (text)
  - `Confidence` - STT confidence score (0.0-1.0)
- Retrieves `CallSession` from `active_calls[call_sid]`
- Saves agent turn to transcript:
  ```python
  session.transcript.append({
      "speaker": "agent",
      "text": agent_speech,
      "turn": session.turn_count,
      "timestamp": datetime.now().isoformat(),
      "confidence": confidence,
  })
  ```
- Calls `session.save_transcript()` → `TranscriptManager.save_transcript()` → writes to `data/transcripts/{call_sid}.json`
- Checks for closing utterance:
  - If agent said "goodbye", "thanks for calling", etc. → returns empty TwiML (patient stays silent, call ends)
  - Otherwise, proceeds to generate patient reply

---

### 4. Patient Reply Generation

**Execution flow:**

#### 4a. `phone_system.py` → `ConversationManager.generate_reply()`

- Passes `agent_text` and `confidence` to `session.conversation_manager.generate_reply(agent_text, confidence)`

#### 4b. `conversation.py` → Builds Message List

**In `ConversationManager.generate_reply()`:**

1. **Verification phase check:**
   - If agent asks for name/DOB → returns direct answer (bypasses LLM for speed/accuracy)
   - Example: "date of birth" → returns "February 17th, 2026"

2. **Goal completion check:**
   - If agent asks "anything else?" → checks if goal is achieved
   - Uses `_is_goal_completed()` to scan conversation for keywords (e.g., "appointment is scheduled", "refill sent")
   - If goal achieved → returns "No, that's all. Thank you!"
   - Otherwise → continues conversation

3. **Build OpenAI messages list:**
   ```python
   messages = [
       {"role": "system", "content": self.generate_system_prompt()},  # Patient persona + scenario rules
       *self.conversation_history,  # Previous turns (user/assistant pairs)
       {"role": "user", "content": f"Agent: {agent_text}"},  # Latest agent turn
   ]
   ```
   - `generate_system_prompt()` builds prompt from:
     - Patient profile (name: Lucas, DOB: 02/17/2026)
     - Scenario `patient_context` (goal, background, behavior rules)
     - YAML `response_stages` (converted to behavior instructions)
     - Anti-repetition rules, question-priority behavior, tone constraints

#### 4c. `llm_client.py` → OpenAI API Call

**In `generate_patient_reply(messages)`:**
- Calls `client.chat.completions.create()`:
  - Model: `gpt-4.1-mini` (from `OPENAI_MODEL` env var)
  - Temperature: `0.4` (consistent, natural responses)
  - Max tokens: `256` (keeps responses concise)
- Extracts text from response: `response.choices[0].message.content`
- Applies guards:
  - If empty or < 8 chars → returns "I'm sorry, could you repeat that?"
  - If incomplete phrase ("i need", "i would like") → returns fallback
  - Otherwise → returns generated text

#### 4d. `conversation.py` → Updates History

- Appends to `conversation_history`:
  ```python
  self.conversation_history.append({"role": "user", "content": f"Agent: {agent_text}"})
  self.conversation_history.append({"role": "assistant", "content": patient_reply})
  ```
- Returns `patient_reply` to `phone_system.py`

#### 4e. `phone_system.py` → TwiML Response

- Wraps `patient_reply` in TwiML:
  ```xml
  <Response>
    <Pause length="1.5"/>  <!-- Natural pause before speaking -->
    <Say voice="Polly.Matthew-Neural">{patient_reply}</Say>
    <Gather input="speech" action="/handle-agent-response" .../>  <!-- Listen for next agent turn -->
  </Response>
  ```
- Saves patient turn to transcript:
  ```python
  session.transcript.append({
      "speaker": "patient",
      "text": patient_reply,
      "turn": session.turn_count,
      "timestamp": datetime.now().isoformat(),
  })
  ```
- Returns TwiML as HTTP response → Twilio speaks patient reply → call continues

**Loop:** Steps 3-4 repeat for each turn until call ends.

---

### 5. Call Status Updates

**Trigger:** Twilio POSTs to `POST /call-status` when call status changes

**Execution in `phone_system.py`:**
- Extracts `CallStatus` (e.g., "completed", "busy", "failed")
- If status is "completed":
  - Retrieves `CallSession` from `active_calls[call_sid]`
  - Builds final transcript data:
    ```python
    transcript_data = {
        "scenario_name": session.scenario_name,
        "transcript": session.transcript,
        "turn_count": session.turn_count,
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
        "duration_seconds": call_duration,
    }
    ```
  - Calls `TranscriptManager.save_transcript(call_sid, transcript_data)` → saves final JSON
  - Removes session from `active_calls` dict
  - Logs completion

---

### 6. Recording Download & Transcription

**Trigger:** Twilio POSTs to `POST /recording-complete` when recording is ready

**Execution in `phone_system.py`:**
- Extracts `RecordingUrl` and `CallSid` from request
- Calls `RecordingManager.download_recording(call_sid, recording_url)`:
  - Downloads MP3 file from Twilio URL
  - Saves to `data/recordings/{call_sid}.mp3`
  - Returns local file path
- If `USE_WHISPER_TRANSCRIPTION=true`:
  - Calls `RecordingManager.transcribe_with_whisper(audio_file)`:
    - Uploads audio to OpenAI Whisper API
    - Returns full transcription (more accurate than Twilio STT)
  - Calls `TranscriptManager.enrich_with_whisper(call_sid, whisper_transcript)`:
    - Adds `whisper_transcription` field to existing transcript JSON
    - Includes full text, segments, duration, language

---

## Module Overview

### `src/scenario_loader.py`
Loads YAML files from `scenarios/` directory. Parses `patient_context`, `response_stages`, `anti_repetition` rules, and converts them to scenario dict format expected by `ConversationManager`. Handles both individual scenario files (`scenarios/<name>.yaml`) and legacy `scenarios.yaml` format.

**Key functions:**
- `load_scenario(name)` - Load single scenario by name
- `list_scenarios()` - List all available scenarios
- `_normalize_scenario_from_file()` - Convert YAML to internal format
- `_build_behavior_from_stages()` - Convert `response_stages` to behavior string

---

### `src/conversation.py`
Orchestrates each conversation turn. Given call state + latest agent text, chooses which response stage applies, builds messages for the LLM, applies closing/goal-completion logic.

**Key class:** `ConversationManager`
- `generate_system_prompt()` - Builds patient persona prompt from scenario YAML
- `generate_reply(agent_text, confidence)` - Main entry point for turn generation
- `_is_goal_completed(conversation_text)` - Checks if scenario goal achieved (appointment scheduled, refill sent, etc.)

**Flow:** Verification check → Goal completion check → Build messages → Call LLM → Update history → Return reply

---

### `src/llm_client.py`
Thin wrapper over OpenAI GPT-4.1 mini API. Single place for temperature/max_tokens config, short reply guards, and fallbacks.

**Key function:** `generate_patient_reply(messages)`
- Calls OpenAI Chat Completions API
- Applies guards: filters empty/incomplete replies
- Returns fallback "I'm sorry, could you repeat that?" on failure

**Design:** Centralized so model swapping, parameter tuning, or post-processing happens in one place.

---

### `src/transcript_manager.py`
Reads/writes JSON transcripts to `data/transcripts/`. Handles both real-time Twilio STT transcripts and optional Whisper enrichments.

**Key methods:**
- `save_transcript(call_sid, transcript_data)` - Save/update transcript JSON
- `load_transcript(call_sid)` - Load transcript by call SID
- `enrich_with_whisper(call_sid, whisper_transcript)` - Add Whisper transcription to existing transcript
- `get_conversation_text(call_sid, source)` - Extract plain text (realtime or whisper)

**File format:** `data/transcripts/{call_sid}.json`

---

### `src/recording_manager.py`
Handles saving/organizing `.mp3` recordings from Twilio. Optional Whisper transcription via OpenAI API.

**Key methods:**
- `download_recording(call_sid, recording_url)` - Download MP3 from Twilio URL
- `transcribe_with_whisper(audio_file)` - Upload to Whisper API, return transcription

**File format:** `data/recordings/{call_sid}.mp3`

**Config:** `DOWNLOAD_RECORDINGS` (default: true), `USE_WHISPER_TRANSCRIPTION` (default: false)

---

### `src/utils.py`
Shared helpers: logging (`log()`), project root detection (`get_project_root()`), time formatting, PHI redaction.

---

## Debugging and Analysis

### Inspect a Specific Call

**Command:** `python analyze_transcript.py <call_sid>`

**Output:**
- Call metadata: status, scenario name, turn count, duration, completion time
- Turn-by-turn transcript:
  - Speaker (Agent/Patient)
  - Text content
  - STT confidence scores (for agent turns)
  - Timestamps
- Optional Whisper transcription (if enabled):
  - Full audio transcription text
  - Duration, language, segments

**Example:**
```bash
python analyze_transcript.py CA1234567890abcdef
```

**Use case:** Review a completed call to understand what happened, debug issues, or analyze agent behavior.

---

### Modify Patient Behavior

**To add or tweak patient behavior:**

1. Edit `scenarios/<name>.yaml`:
   - Modify `patient_context.response_stages` to change how patient responds to specific agent utterances
   - Adjust `anti_repetition` rules to prevent repetition
   - Update `question_priority` behavior
   - Change `goal` or `background` context

2. Re-run test:
   ```bash
   python test_call.py --scenario <name>
   ```

3. Analyze results:
   ```bash
   python analyze_transcript.py <call_sid>
   ```

**Example:** To test how agent handles interruptions, edit `scenarios/edge_barge_in.yaml` and add new response stages.

---

### View Logs

**Flask console output:**
- Real-time logs during call execution
- Agent speech (with confidence scores)
- Patient replies (before TTS)
- Errors, warnings, status updates

**Transcript files:**
- `data/transcripts/{call_sid}.json` - Full conversation history
- Includes turn-by-turn data, metadata, optional Whisper transcription

---

## Constraints / Design Notes

### Centralized LLM Calls

**Why:** All patient reply generation flows through `llm_client.generate_patient_reply()`. This ensures:
- Consistent model configuration (temperature, max_tokens) across all calls
- Single place to swap models (e.g., GPT-4.1 mini → GPT-4o)
- Unified error handling and fallback logic
- Easy to add post-processing (e.g., profanity filters, length limits)

**Trade-off:** Slight indirection, but worth it for maintainability.

---

### Closing Detection and Goal Completion

**Why:** Closing detection lives in `phone_system.py` (`is_closing_utterance()`), while goal completion lives in `conversation.py` (`_is_goal_completed()`).

**Reasoning:**
- **Closing detection** (early exit): If agent says "goodbye", we skip LLM call entirely → saves API costs, prevents awkward back-and-forth
- **Goal completion** (conversation logic): Only end when agent asks "anything else?" AND goal achieved → prevents premature termination

**Separation:** `phone_system.py` handles webhook/HTTP concerns (when to stop generating replies), `conversation.py` handles conversation logic (what to say, when goal is met).

---

### YAML + Transcripts + BUG_REPORT as QA Harness

**How it works together:**

1. **YAML scenarios** (`scenarios/*.yaml`):
   - Define expected patient behavior (response stages, anti-repetition rules)
   - Specify test goals (appointment scheduling, refill request, etc.)
   - Enable repeatable tests (same scenario → same patient behavior)

2. **Transcripts** (`data/transcripts/*.json`):
   - Capture actual agent behavior (what agent said, when, with what confidence)
   - Enable post-call analysis (did agent achieve goal? did it handle edge cases?)
   - Provide data for automated scoring (pass/fail per scenario)

3. **BUG_REPORT.md** (`docs/BUG_REPORT.md`):
   - Documents bugs found across scenarios
   - Categorizes by type (state desync, conditional logic, policy boundaries)
   - Provides examples with call IDs for reproducibility

**Together:** YAML defines test cases → Transcripts capture results → BUG_REPORT documents failures. This forms a mini QA harness: run scenarios → analyze transcripts → document bugs → iterate.

**Future extension:** Automated scoring could parse transcripts, check for goal achievement, detect bug patterns, and generate pass/fail reports.

---

### No True Barge-in Support

**Constraint:** Twilio `Gather` only captures one complete utterance per webhook call. Patient cannot interrupt agent mid-sentence.

**Workaround:** `speech_timeout=3` waits for 3 seconds of silence before considering agent finished. This prevents mid-sentence cutoffs but doesn't enable true interruption.

**Impact:** Edge case scenarios like `edge_barge_in` simulate interruption by having patient add information after agent finishes, not during.

---

### State Management

**In-memory:** `active_calls` dict in `phone_system.py` stores `CallSession` objects during active calls.

**Persistent:** Transcripts saved to disk after each turn (`session.save_transcript()`) and on call completion.

**Limitation:** If Flask server restarts mid-call, in-memory state is lost. Transcripts persist, but conversation history in `ConversationManager` would reset. For production, consider Redis or database for session state.

---

## Quick Reference: Data Flow Diagram

```
Developer
  ↓
test_call.py → make_call(scenario_name)
  ↓
Twilio REST API → Initiates outbound call
  ↓
POST /voice → CallSession created, TwiML returned
  ↓
Agent speaks → Twilio STT
  ↓
POST /handle-agent-response → agent_text received
  ↓
ConversationManager.generate_reply(agent_text)
  ↓
llm_client.generate_patient_reply(messages)
  ↓
OpenAI GPT-4.1 mini → patient_reply
  ↓
TwiML <Say> → Twilio TTS → Patient speaks
  ↓
[Loop: Steps repeat until call ends]
  ↓
POST /call-status → CallSession saved, removed from memory
  ↓
POST /recording-complete → MP3 downloaded, optional Whisper transcription
  ↓
data/transcripts/{call_sid}.json (final transcript)
```

---

**Last Updated:** February 18, 2026
