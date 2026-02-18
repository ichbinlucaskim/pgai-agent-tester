"""
Transcript manager with dual-source support.

Combines real-time Twilio STT with optional Whisper post-processing.
Used by phone_system for saving and enriching transcripts.
"""

import json
import os
from datetime import datetime
from typing import Any

from src.utils import get_project_root, log


class TranscriptManager:
    """Manage transcript saving and enrichment."""

    def __init__(self) -> None:
        root = get_project_root()
        self.transcripts_dir = os.path.join(root, "data", "transcripts")
        os.makedirs(self.transcripts_dir, exist_ok=True)

    def save_transcript(self, call_sid: str, transcript_data: dict[str, Any]) -> str | None:
        """
        Save transcript with metadata.

        Args:
            call_sid: Twilio call SID.
            transcript_data: Dict with conversation and metadata.

        Returns:
            Filename if saved, None otherwise.
        """
        filename = os.path.join(self.transcripts_dir, f"{call_sid}.json")
        full_data = {
            "call_sid": call_sid,
            "timestamp": datetime.now().isoformat(),
            "status": transcript_data.get("status", "in_progress"),
            **transcript_data,
        }
        try:
            with open(filename, "w") as f:
                json.dump(full_data, f, indent=2)
            return filename
        except Exception as e:
            log("ERROR", "Failed to save transcript", str(e))
            return None

    def enrich_with_whisper(self, call_sid: str, whisper_transcript: dict[str, Any]) -> bool:
        """
        Add Whisper transcription to existing transcript.

        Args:
            call_sid: Call SID.
            whisper_transcript: Whisper API response dict.

        Returns:
            True if enriched, False otherwise.
        """
        filename = os.path.join(self.transcripts_dir, f"{call_sid}.json")
        if not os.path.exists(filename):
            log("WARNING", f"Transcript not found: {filename}")
            return False
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            data["whisper_transcription"] = {
                "full_text": whisper_transcript["text"],
                "duration": whisper_transcript.get("duration"),
                "segments": whisper_transcript.get("segments", []),
                "language": whisper_transcript.get("language", "en"),
                "transcribed_at": datetime.now().isoformat(),
            }
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            log("SUCCESS", "Transcript enriched with Whisper data")
            return True
        except Exception as e:
            log("ERROR", "Failed to enrich transcript", str(e))
            return False

    def load_transcript(self, call_sid: str) -> dict[str, Any] | None:
        """
        Load transcript from file.

        Args:
            call_sid: Call SID.

        Returns:
            Transcript dict or None if not found.
        """
        filename = os.path.join(self.transcripts_dir, f"{call_sid}.json")
        if not os.path.exists(filename):
            return None
        with open(filename, "r") as f:
            return json.load(f)

    def get_conversation_text(self, call_sid: str, source: str = "realtime") -> str | None:
        """
        Extract conversation as plain text for analysis.

        Args:
            call_sid: Call SID.
            source: "realtime" (Twilio STT) or "whisper" (Whisper API).

        Returns:
            Formatted conversation string or None.
        """
        transcript = self.load_transcript(call_sid)
        if not transcript:
            return None
        if source == "whisper" and "whisper_transcription" in transcript:
            return transcript["whisper_transcription"]["full_text"]
        conversation = transcript.get("transcript", [])
        lines = []
        for turn in conversation:
            speaker = turn.get("speaker", "unknown").capitalize()
            message = turn.get("text", "")
            lines.append(f"{speaker}: {message}")
        return "\n".join(lines)
