# Architecture

## System Overview

The voice bot system simulates patient calls to Pretty Good AI's test line (805-439-8008) for automated testing and evaluation. The pipeline flows as follows:

**Twilio webhook → Flask server (`src/phone_system.py`) → scenario selection → OpenAI GPT-4.1 mini for patient replies → TwiML back to Twilio**

Speech-to-text (STT) and text-to-speech (TTS) are handled entirely by Twilio's built-in capabilities. The LLM (GPT-4.1 mini) only generates the patient side of the conversation. YAML scenario files drive "how the patient behaves" through detailed rules, anti-repetition constraints, question-priority behavior, and response stages that match agent utterances.

## Key Design Choices

### Model Selection: GPT-4.1 mini

Switched from Gemini to GPT-4.1 mini for reliability and cost-effectiveness. Gemini's safety blocks were too aggressive for test scenarios (e.g., refusing to role-play as a patient), while GPT-4.1 mini provides the right balance of quality, latency, and cost (~$0.01-0.02 per call). The model generates natural, context-aware patient responses that follow scenario-specific behavior rules.

### Centralized LLM Client

All patient reply generation flows through a single helper (`src/llm_client.py` → `generate_patient_reply()`) with built-in guards:
- **Short/incomplete reply detection:** Filters out ultra-short responses (< 8 chars) or incomplete phrases like "I need" or "I would like"
- **Fallback utterances:** Returns "I'm sorry, could you repeat that?" when generation fails or confidence is low
- **Consistent temperature (0.4) and max_tokens (256):** Ensures predictable, concise responses

This centralization makes it easy to swap models, adjust parameters, or add post-processing logic in one place.

### Detailed YAML Scenario Specs

Scenarios in `scenarios/*.yaml` are comprehensive evaluation specifications, not simple prompt templates. Each includes:

- **Anti-repetition rules:** Prevents patient bot from repeating DOB, medication names, or reasons for call unless explicitly asked
- **Question-priority behavior:** Ensures patient answers the agent's latest question first, before adding extra details
- **Response stages:** Maps agent utterances to appropriate patient responses (e.g., `on_agent_asks_dob` → "February 17th, 2026")
- **Tone constraints:** Enforces natural, concise speech (no filler words, 1-2 sentences max)

This design makes edge cases repeatable and testable:
- **State desynchronization:** `edge_state_desync.yaml` tests whether agent remembers "Tuesday at 3 PM" after an insurance detour
- **Conditional logic:** `edge_conditional_logic.yaml` verifies agent applies complex rules (e.g., "after 2 PM, not 4 PM; Wednesdays only if Dr. Kim")
- **Barge-in handling:** `edge_barge_in.yaml` checks if agent acknowledges newly introduced information (back pain) after interruption
- **Multi-intent:** Tests agent's ability to handle multiple requests in one call
- **Policy boundaries:** `edge_policy_boundary.yaml` verifies agent refuses unsafe requests (deleting records, changing diagnoses)
- **Transaction consistency:** Ensures booking changes and cancellations maintain state correctly

### Benefits

This architecture enables:
- **Easy scenario addition:** New test cases are just YAML files with behavior specs
- **Regression testing:** Run the same scenarios after model/prompt updates to detect regressions
- **Extensible evaluation:** Transcripts can be scored automatically (pass/fail per scenario) or analyzed manually
- **Repeatable edge cases:** Complex bugs (state desync, conditional logic failures) can be reproduced consistently

The system is designed to evolve into a full evaluation harness: scenarios define expected patient behavior, transcripts capture actual agent performance, and bug reports highlight failures. Future enhancements could include automated scoring, A/B testing across model versions, and integration with CI/CD pipelines.
