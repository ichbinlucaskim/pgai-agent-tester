"""
Phone call system using Twilio Programmable Voice.

Handles outbound calls and TwiML webhooks for conversation.
Sprint 1: Basic call flow. Sprint 2: GPT-4 dynamic responses.
Sprint 3: Recording download and transcript persistence.
"""

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

from src.conversation import ConversationManager
from src.recording_manager import RecordingManager
from src.scenario_loader import get_scenario_by_name
from src.transcript_manager import TranscriptManager
from src.utils import get_project_root, log

load_dotenv()

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN"),
)
app = Flask(__name__)

recording_manager = RecordingManager()
transcript_manager = TranscriptManager()

active_calls: dict[str, "CallSession"] = {}


# Closing phrases that indicate the agent is ending the call
CLOSING_PHRASES = [
    "have a great day",
    "have a good day",
    "thanks for calling",
    "thank you for calling",
    "goodbye",
    "bye for now",
    "take care",
    "thanks again",
    "thank you again",
]


def is_closing_utterance(text: str) -> bool:
    """
    Check if agent utterance contains a clear closing phrase.
    
    If true, the patient bot should NOT generate a reply - the call is ending.
    
    Args:
        text: Agent's speech text.
        
    Returns:
        True if text contains a closing phrase, False otherwise.
    """
    if not text:
        return False
    lower = text.lower()
    return any(phrase in lower for phrase in CLOSING_PHRASES)


class CallSession:
    """Track ongoing call state with natural ending detection and transcript saving."""

    def __init__(self, call_sid: str, scenario_name: str = "appointment_scheduling") -> None:
        self.call_sid = call_sid
        self.turn_count = 0
        self.transcript: list[dict[str, Any]] = []
        self.scenario_name = scenario_name
        self.goal_achieved = False
        self.conversation_manager: ConversationManager | None = None

        try:
            scenario = get_scenario_by_name(scenario_name)
            self.conversation_manager = ConversationManager(scenario)
            log("SUCCESS", f"Loaded scenario: {scenario_name}")
        except Exception as e:
            log("ERROR", "Failed to load scenario", str(e))

    # Minimum turns before we allow any "agent is closing" or "natural end" logic.
    # Prevents greeting phrases like "Thanks for calling" from ending the call on turn 1.
    MIN_TURNS_BEFORE_CLOSE = 3

    def should_end_call(self, agent_text: str) -> bool:
        """
        Check if conversation should end.
        Only end if BOTH conditions met:
        1. At least MIN_TURNS_BEFORE_CLOSE turns (avoid ending on greeting).
        2. Agent signals end AND (goal achieved OR max turns reached), or safety cap.
        """
        if self.turn_count < self.MIN_TURNS_BEFORE_CLOSE:
            return False

        agent_lower = agent_text.lower()

        # Ending signals from agent
        end_phrases = [
            "goodbye", "have a great day", "have a good day",
            "take care", "thanks for calling",
        ]

        # Goal achievement indicators (appointment context)
        goal_indicators = [
            "appointment is scheduled", "appointment is confirmed",
            "appointment on", "see you on", "we'll send you",
            "confirmation", "all set", "you're all set",
        ]

        # Check if goal seems achieved
        if any(indicator in agent_lower for indicator in goal_indicators):
            self.goal_achieved = True

        # Only end if agent clearly ending AND (goal achieved OR too many turns)
        has_ending_phrase = any(phrase in agent_lower for phrase in end_phrases)

        if has_ending_phrase and (self.goal_achieved or self.turn_count >= 20):
            return True

        # Safety: force end after 25 turns
        if self.turn_count >= 25:
            return True

        return False

    def save_transcript(self) -> None:
        """Save transcript using TranscriptManager."""
        transcript_data: dict[str, Any] = {
            "scenario_name": self.scenario_name,
            "transcript": self.transcript,
            "turn_count": self.turn_count,
            "status": "in_progress" if self.turn_count < 25 and not self.goal_achieved else "completed",
        }
        if self.conversation_manager:
            transcript_data["scenario_info"] = self.conversation_manager.get_scenario_info()

        filename = transcript_manager.save_transcript(self.call_sid, transcript_data)
        if filename:
            log("INFO", f"Transcript saved: {filename}")


def make_call(scenario_name: str = "appointment_scheduling") -> str | None:
    """
    Initiate outbound call with specified scenario.

    Args:
        scenario_name: Scenario key from scenarios.yaml.

    Returns:
        Call SID on success, None on failure.
    """
    base_url = os.getenv("BASE_URL", "").strip().rstrip("/")

    if not base_url:
        log("ERROR", "BASE_URL not set in .env")
        return None

    if not base_url.startswith("https://"):
        log("WARNING", "BASE_URL should be HTTPS for Twilio webhooks")

    try:
        call = twilio_client.calls.create(
            to=os.getenv("TEST_LINE_NUMBER"),
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            url=f"{base_url}/voice?scenario={scenario_name}",
            record=True,
            recording_status_callback=f"{base_url}/recording-complete",
            status_callback=f"{base_url}/call-status",
        )

        log("SUCCESS", "Call initiated", f"SID: {call.sid} | Scenario: {scenario_name}")

        active_calls[call.sid] = CallSession(call.sid, scenario_name)
        return call.sid

    except Exception as e:
        log("ERROR", "Call failed", str(e))
        errors_path = os.path.join(get_project_root(), "data", "errors.log")
        os.makedirs(os.path.dirname(errors_path), exist_ok=True)
        with open(errors_path, "a") as f:
            f.write(f"{datetime.now().isoformat()} - Call initiation failed: {e}\n")

        error_str = str(e).lower()
        if "authenticate" in error_str:
            log("INFO", "Hint: Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")
        elif "balance" in error_str or "insufficient" in error_str:
            log("INFO", "Hint: Check Twilio account balance")
        elif "not a valid phone number" in error_str:
            log("INFO", "Hint: Phone number format should be E.164 (e.g. +1XXXXXXXXXX)")
        return None


@app.route("/voice", methods=["POST"])
def voice_webhook() -> str:
    """
    Call-init: Listen immediately. No patient greeting.
    Clinic AI speaks first (greeting + first question). We only respond
    after receiving the agent's utterance in /handle-agent-response.
    """
    call_sid = request.form.get("CallSid", "")

    # Initialize call session if not exists
    if call_sid not in active_calls:
        scenario_name = request.values.get("scenario", "appointment_scheduling")
        log("INFO", f"Initializing call session for {call_sid} with scenario {scenario_name}")
        active_calls[call_sid] = CallSession(call_sid, scenario_name)

    response = VoiceResponse()

    # No initial Pause: connect and listen immediately so clinic greeting plays and we capture it.
    # We only get one POST per completed utterance (no partial STT chunks); patient does not barge in.
    gather = Gather(
        input="speech",
        timeout=20,
        speech_timeout=3,  # Wait for agent to fully finish; avoid mid-sentence cutoff
        action="/handle-agent-response",
        method="POST",
    )
    response.append(gather)

    # Fallback if no speech detected (minimal pause before "Hello?")
    response.pause(length=1)
    response.say("Hello?", voice="Polly.Matthew-Neural")
    response.hangup()

    return str(response)


@app.route("/handle-agent-response", methods=["POST"])
def handle_agent_response() -> str:
    """
    Process agent's speech and generate patient response.
    """
    call_sid = request.form.get("CallSid", "")
    agent_speech = request.form.get("SpeechResult", "")
    confidence_str = request.form.get("Confidence", "1.0")

    try:
        confidence = float(confidence_str)
    except (ValueError, TypeError):
        confidence = 0.0

    log("INFO", f"Handling response for call {call_sid}")

    if confidence < 0.7:
        log("WARNING", f"Low STT confidence ({confidence})")
    else:
        log("SUCCESS", f"Agent said (confidence {confidence}): {agent_speech}")

    # Initialize call session if needed
    if call_sid not in active_calls:
        log("WARNING", f"Call {call_sid} not in active_calls, creating now")
        active_calls[call_sid] = CallSession(call_sid, "appointment_scheduling")

    session = active_calls[call_sid]

    # Save agent turn
    session.transcript.append({
        "speaker": "agent",
        "text": agent_speech,
        "turn": session.turn_count,
        "timestamp": datetime.now().isoformat(),
        "confidence": confidence,
    })
    session.turn_count += 1
    session.save_transcript()

    # Early exit: if agent clearly closed the call, do NOT call the LLM.
    # Only after MIN_TURNS_BEFORE_CLOSE: greeting phrases like "Thanks for calling" often
    # appear in the first agent utterance and must not be treated as closing.
    if session.turn_count >= CallSession.MIN_TURNS_BEFORE_CLOSE and is_closing_utterance(agent_speech):
        log("INFO", "Agent closing detected - patient will not respond", f"closed because: agent_closing_utterance (turn_count={session.turn_count})")
        response = VoiceResponse()
        return str(response)

    # Check if call should end (goal achieved, max turns, etc.). Also gated by min turns.
    if session.should_end_call(agent_speech):
        reason = "goal_achieved" if session.goal_achieved else "max_turns_reached"
        log("INFO", "Natural call ending detected", f"closed because: {reason} (turn_count={session.turn_count})")
        response = VoiceResponse()
        response.pause(length=1)
        response.say("Thank you, goodbye.", voice="Polly.Matthew-Neural")
        response.hangup()
        return str(response)

    # Generate patient reply only after agent's turn is complete (this handler runs when Gather
    # returns one full SpeechResult — we do not respond to partial STT chunks; patient does not barge in).
    patient_reply = generate_gpt_reply(call_sid, agent_speech, confidence)
    log("INFO", f"Patient will say: '{patient_reply}'")

    # Build TwiML: short pause before patient speaks so we don't sound like we're interrupting.
    # The 1.5s pause creates natural conversation rhythm and masks LLM processing latency.
    response = VoiceResponse()
    if patient_reply:
        # ~1.5s "thinking" pause after agent finishes, before patient speaks
        response.pause(length=1.5)
        response.say(patient_reply, voice="Polly.Matthew-Neural")
        log("SUCCESS", f"TwiML generated: {patient_reply[:50]}...")

        # Listen for next agent turn. Note: Twilio Gather only captures one complete utterance
        # per webhook call - we do not support true barge-in (interrupting mid-sentence).
        # speech_timeout=3 means wait 3 seconds of silence before considering agent finished.
        gather = Gather(
            input="speech",
            timeout=10,
            speech_timeout=3,  # Wait for agent to fully finish before considering turn complete
            action="/handle-agent-response",
            method="POST",
        )
        response.append(gather)
    else:
        response.pause(length=1)
        response.say("Thank you, goodbye.", voice="Polly.Matthew-Neural")
        response.hangup()

    # Persist transcript after TwiML is built (does not delay audible response)
    session.transcript.append({
        "speaker": "patient",
        "text": patient_reply or "Thank you, goodbye.",
        "turn": session.turn_count,
        "timestamp": datetime.now().isoformat(),
    })
    session.turn_count += 1
    session.save_transcript()

    return str(response)


def generate_gpt_reply(call_sid: str, agent_text: str, confidence: float = 1.0) -> str:
    """
    Generate patient reply using GPT-4 or fallback rules.

    Args:
        call_sid: Current call SID.
        agent_text: What the agent said.
        confidence: STT confidence 0-1.

    Returns:
        Patient reply string.
    """
    if call_sid not in active_calls:
        return "Okay, thank you."
    session = active_calls[call_sid]
    if session.conversation_manager:
        try:
            return session.conversation_manager.generate_reply(agent_text, confidence)
        except Exception as e:
            log("ERROR", "GPT generation failed", str(e))
    return generate_simple_reply_fallback(agent_text)


def generate_simple_reply_fallback(agent_text: str) -> str:
    """Fallback rule-based replies when GPT is unavailable. Uses Lucas profile."""
    agent_lower = agent_text.lower()
    if "date of birth" in agent_lower or "birthday" in agent_lower:
        return "February 17th, 2026"
    if "phone" in agent_lower or "callback" in agent_lower or "number" in agent_lower:
        return "Yes, that's correct."
    if "name" in agent_lower:
        return "Lucas"
    return "Okay, thank you."


@app.route("/recording-complete", methods=["POST"])
def recording_complete() -> str:
    """Webhook when call recording is ready; download and optionally transcribe with Whisper."""
    recording_url = request.form.get("RecordingUrl", "")
    call_sid = request.form.get("CallSid", "")
    recording_duration = request.form.get("RecordingDuration", "0")

    log("STATUS", f"Recording complete for call {call_sid}", f"Duration: {recording_duration}s")

    audio_file = recording_manager.download_recording(call_sid, recording_url)
    if audio_file:
        whisper_transcript = recording_manager.transcribe_with_whisper(audio_file)
        if whisper_transcript:
            transcript_manager.enrich_with_whisper(call_sid, whisper_transcript)
    return "OK"


@app.route("/call-status", methods=["POST"])
def call_status() -> str:
    """Track call status and save final transcript when call completes."""
    call_sid = request.form.get("CallSid", "")
    call_status_val = request.form.get("CallStatus", "")
    call_duration = request.form.get("CallDuration", "0")

    log("STATUS", f"Call {call_sid} status: {call_status_val}")

    if call_status_val == "completed" and call_sid in active_calls:
        session = active_calls[call_sid]
        transcript_data: dict[str, Any] = {
            "scenario_name": session.scenario_name,
            "transcript": session.transcript,
            "turn_count": session.turn_count,
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "duration_seconds": int(call_duration) if str(call_duration).isdigit() else 0,
        }
        if session.conversation_manager:
            transcript_data["scenario_info"] = session.conversation_manager.get_scenario_info()

        filename = transcript_manager.save_transcript(call_sid, transcript_data)
        log("SUCCESS", "Call completed", f"Duration: {call_duration}s | Turns: {session.turn_count}")
        log("INFO", f"Transcript: {filename}")
        del active_calls[call_sid]
    return "OK"


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    log("INFO", f"Starting Flask server on port {port}")
    log("INFO", "1. Run ngrok: ngrok http 5000")
    log("INFO", "2. Set BASE_URL in .env to your ngrok HTTPS URL")
    log("INFO", "3. Run: python test_call.py to initiate a test call")
    app.run(host="0.0.0.0", port=port, debug=True)
