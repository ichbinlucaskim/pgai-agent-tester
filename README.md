# PGAI Voice Agent Tester

Python voice bot that calls Pretty Good AI's test line (805-439-8008). Simulates realistic patient scenarios (appointments, refills, general inquiries, edge cases). Records, transcribes, and logs calls for later analysis.

## Quickstart

```bash
python test_call.py --scenario appointment
```

## Prerequisites

- **Python 3.9+**
- **Twilio Account** with Programmable Voice enabled
- **OpenAI API Key** (for GPT-4.1 mini patient bot)
- **ngrok** (or similar tunneling service) for webhook exposure
- **Twilio Phone Number** configured for voice calls

## Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set the following (do NOT commit real values):
   - `OPENAI_API_KEY` - Your OpenAI API key (get from https://platform.openai.com/api-keys)
   - `TWILIO_ACCOUNT_SID` - Twilio Account SID (from https://console.twilio.com)
   - `TWILIO_AUTH_TOKEN` - Twilio Auth Token
   - `TWILIO_PHONE_NUMBER` - Your Twilio phone number in E.164 format (e.g., +1XXXXXXXXXX)
   - `BASE_URL` - Your ngrok HTTPS URL (see below)
   - `OPENAI_MODEL` - Optional, defaults to `gpt-4.1-mini`
   - `FLASK_PORT` - Optional, defaults to `5000`
   - `TEST_LINE_NUMBER` - Optional, defaults to `805-439-8008`
   - `DOWNLOAD_RECORDINGS` - Optional, defaults to `true`
   - `USE_WHISPER_TRANSCRIPTION` - Optional, defaults to `false`

4. **Start ngrok tunnel:**
   ```bash
   ngrok http 5000
   ```
   Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

5. **Update `.env` with ngrok URL:**
   ```
   BASE_URL=https://abc123.ngrok-free.app
   ```

## Run

1. **Start Flask server** (in one terminal):
   ```bash
   python -m src.phone_system
   ```
   Or:
   ```bash
   python test_call.py  # This will start the server if needed
   ```

2. **Make a test call** (in another terminal):
   ```bash
   # Run specific scenario
   python test_call.py --scenario appointment
   python test_call.py --scenario medication_refill
   python test_call.py --scenario general_inquiry
   
   # List available scenarios
   python test_call.py --list
   ```

The Flask server handles Twilio webhooks, generates patient replies using GPT-4.1 mini, and saves transcripts automatically.

3. **Analyze a transcript** (after a call completes):
   ```bash
   python analyze_transcript.py <call_sid>
   ```
   This displays the full conversation transcript, turn-by-turn, with confidence scores and scenario metadata.

## Scenarios

Test scenarios are defined in YAML files under `scenarios/`. Each scenario specifies patient behavior, goals, and evaluation criteria.

### Standard Scenarios

- **`appointment`** - New patient appointment scheduling for knee pain
- **`medication_refill`** - Request prescription refill (Lisinopril)
- **`general_inquiry`** - General questions about services
- **`reschedule_cancel`** - Reschedule or cancel existing appointment

### Edge Case Scenarios

- **`edge_state_desync`** - State desynchronization via U-turn (booking → insurance → back to booking)
- **`edge_conditional_logic`** - Complex conditional preferences (time windows, provider rules)
- **`edge_barge_in`** - Interruption handling (patient adds back pain mid-flow)
- **`edge_contradiction`** - Contradictory information handling
- **`edge_infinite_loop`** - Infinite loop detection (repetitive agent responses)
- **`edge_policy_boundary`** - Policy and authorization boundary testing
- **`edge_multi_patient`** - Multi-patient access attempts
- **`edge_ssn_harvest`** - SSN harvesting attempts
- **`edge_transfer_escape`** - Transfer request handling
- **`edge_gdpr_request`** - GDPR/data deletion requests
- **`edge_appointment_bombing`** - Rapid-fire appointment requests

**Note:** YAML scenario files contain detailed test specifications (anti-repetition rules, question priority, response stages). These are evaluation specs for the patient bot, not production-facing copy.

## Outputs

### Transcripts

Saved to `data/transcripts/` as JSON files:
- Format: `{scenario_name}_{timestamp}.json`
- Each transcript includes:
  - Turn-by-turn speaker labels (`agent` / `patient`)
  - Timestamps for each turn
  - STT confidence scores
  - Scenario metadata
  - Call duration and turn count

### Recordings

Saved to `data/recordings/` as MP3 files:
- Format: `{call_sid}.mp3`
- Automatically downloaded after call completion
- Optional Whisper transcription available (set `USE_WHISPER_TRANSCRIPTION=true`)

### Bug Reports

See `docs/BUG_REPORT.md` for comprehensive bug analysis across all test scenarios.

## API Keys and Environment Variables

### Required Variables

- **`OPENAI_API_KEY`** - Used for GPT-4.1 mini patient reply generation
- **`TWILIO_ACCOUNT_SID`** - Twilio account identifier
- **`TWILIO_AUTH_TOKEN`** - Twilio authentication token
- **`TWILIO_PHONE_NUMBER`** - Your Twilio phone number (must be voice-enabled)
- **`BASE_URL`** - Public HTTPS URL for Twilio webhooks (ngrok tunnel)

### Optional Variables

- **`OPENAI_MODEL`** - OpenAI model name (default: `gpt-4.1-mini`)
- **`FLASK_PORT`** - Flask server port (default: `5000`)
- **`TEST_LINE_NUMBER`** - Test line to call (default: `805-439-8008`)
- **`DOWNLOAD_RECORDINGS`** - Download call recordings (default: `true`)
- **`USE_WHISPER_TRANSCRIPTION`** - Post-process with Whisper (default: `false`, costs ~$0.006/min)

### Security Note

**Do NOT commit secrets.** The `.env` file is git-ignored. Always use `.env.example` as a template without real values.

## Project Structure

```
pgai-agent/
├── src/                    # Core modules
│   ├── phone_system.py    # Flask server, Twilio webhooks
│   ├── conversation.py    # ConversationManager (patient bot logic)
│   ├── llm_client.py      # OpenAI client wrapper
│   ├── scenario_loader.py # YAML scenario loading
│   ├── transcript_manager.py  # Transcript persistence
│   └── recording_manager.py   # Recording download/transcription
├── scenarios/             # YAML test scenario definitions
├── data/                  # Outputs (git-ignored)
│   ├── transcripts/      # JSON transcript files
│   ├── recordings/       # MP3 call recordings
│   └── metrics/          # Analysis outputs
├── docs/                 # Documentation
│   └── BUG_REPORT.md    # Bug analysis report
├── archive/              # Old/alternative implementations (not used)
├── test_call.py         # CLI entry point
├── analyze_transcript.py # Utility to analyze saved transcripts
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── README.md           # This file
```

## How It Works

1. **Call Initiation:** `test_call.py` calls `src.phone_system.make_call()` which initiates a Twilio outbound call
2. **Webhook Flow:** Twilio POSTs to `/voice` → Flask routes to `/handle-agent-response` for each agent utterance
3. **Patient Reply Generation:** `ConversationManager` uses GPT-4.1 mini to generate context-aware patient responses based on scenario YAML
4. **TwiML Response:** Patient reply sent back as TwiML `<Say>` instruction
5. **Recording & Transcript:** After call ends, recording downloaded and transcript saved to `data/`

See `ARCHITECTURE.md` for detailed design decisions.

## Troubleshooting

- **No webhook received:** Check ngrok is running and `BASE_URL` matches your ngrok HTTPS URL
- **Call fails:** Verify Twilio credentials in `.env` and account balance
- **No audio:** Ensure Twilio phone number is voice-enabled
- **Low STT confidence:** Check audio quality; agent speech may be unclear
- **GPT errors:** Verify `OPENAI_API_KEY` is valid and account has credits

## License

Interview project for Pretty Good AI.
