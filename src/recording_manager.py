"""
Recording download and transcription manager.

Handles Twilio recording URLs and optional Whisper post-processing.
Used by phone_system when recording-complete webhook is called.
"""

import os
from datetime import datetime
from typing import Any

import requests
from openai import OpenAI
from twilio.rest import Client

from src.utils import get_project_root, log

_twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN"),
)
_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class RecordingManager:
    """Download and process call recordings."""

    def __init__(self) -> None:
        root = get_project_root()
        self.recordings_dir = os.path.join(root, "data", "recordings")
        self.should_download = os.getenv("DOWNLOAD_RECORDINGS", "true").lower() == "true"
        self.use_whisper = os.getenv("USE_WHISPER_TRANSCRIPTION", "false").lower() == "true"
        os.makedirs(self.recordings_dir, exist_ok=True)

    def download_recording(self, call_sid: str, recording_url: str) -> str | None:
        """
        Download recording from Twilio.

        Args:
            call_sid: Twilio call SID.
            recording_url: Recording URL from Twilio webhook.

        Returns:
            Local file path if successful, None otherwise.
        """
        if not self.should_download:
            log("INFO", "Recording download disabled (DOWNLOAD_RECORDINGS=false)")
            return None

        try:
            if not recording_url.startswith("http"):
                recording_url = f"https://api.twilio.com{recording_url}.mp3"

            log("STATUS", "Downloading recording...")

            response = requests.get(
                recording_url,
                auth=(
                    os.getenv("TWILIO_ACCOUNT_SID"),
                    os.getenv("TWILIO_AUTH_TOKEN"),
                ),
                stream=True,
            )

            if response.status_code != 200:
                log("ERROR", f"Download failed: HTTP {response.status_code}")
                return None

            filename = os.path.join(self.recordings_dir, f"{call_sid}.mp3")
            with open(filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(filename)
            log("SUCCESS", f"Recording saved: {filename}", f"{file_size / 1024:.1f} KB")
            return filename

        except Exception as e:
            log("ERROR", "Recording download failed", str(e))
            errors_path = os.path.join(get_project_root(), "data", "errors.log")
            os.makedirs(os.path.dirname(errors_path), exist_ok=True)
            with open(errors_path, "a") as f:
                f.write(f"{datetime.now().isoformat()} - Recording download failed for {call_sid}: {e}\n")
            return None

    def transcribe_with_whisper(self, audio_file: str) -> dict[str, Any] | None:
        """
        Transcribe audio file using Whisper API.

        Args:
            audio_file: Path to audio file.

        Returns:
            Dict with text, duration, segments, language; or None.
        """
        if not self.use_whisper:
            log("INFO", "Whisper transcription disabled (USE_WHISPER_TRANSCRIPTION=false)")
            return None

        if not os.path.exists(audio_file):
            log("ERROR", f"Audio file not found: {audio_file}")
            return None

        try:
            log("STATUS", "Transcribing with Whisper...")

            with open(audio_file, "rb") as f:
                transcript = _openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="en",
                    response_format="verbose_json",
                )

            duration_seconds = getattr(transcript, "duration", 0) or 0
            cost = (duration_seconds / 60) * 0.006
            log("SUCCESS", "Whisper transcription complete", f"Duration: {duration_seconds:.1f}s (~${cost:.4f})")

            return {
                "text": transcript.text,
                "duration": duration_seconds,
                "segments": getattr(transcript, "segments", []),
                "language": getattr(transcript, "language", "en"),
            }

        except Exception as e:
            log("ERROR", "Whisper transcription failed", str(e))
            errors_path = os.path.join(get_project_root(), "data", "errors.log")
            os.makedirs(os.path.dirname(errors_path), exist_ok=True)
            with open(errors_path, "a") as f:
                f.write(f"{datetime.now().isoformat()} - Whisper transcription failed for {audio_file}: {e}\n")
            return None

    def get_recording_metadata(self, call_sid: str) -> dict[str, Any] | None:
        """
        Fetch recording metadata from Twilio.

        Args:
            call_sid: Twilio call SID.

        Returns:
            Dict with recording_sid, duration, date_created, uri; or None.
        """
        try:
            recordings = _twilio_client.recordings.list(call_sid=call_sid, limit=1)
            if not recordings:
                return None
            recording = recordings[0]
            return {
                "recording_sid": recording.sid,
                "duration": recording.duration,
                "date_created": recording.date_created.isoformat() if recording.date_created else None,
                "uri": recording.uri,
            }
        except Exception as e:
            log("WARNING", "Could not fetch recording metadata", str(e))
            return None
