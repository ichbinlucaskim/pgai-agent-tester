"""
Utility to analyze and compare transcripts.

Usage: python analyze_transcript.py <call_sid>
"""

import sys

from src.transcript_manager import TranscriptManager


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python analyze_transcript.py <call_sid>")
        sys.exit(1)

    call_sid = sys.argv[1]
    transcript_manager = TranscriptManager()
    transcript = transcript_manager.load_transcript(call_sid)

    if not transcript:
        print(f"[ERROR] Transcript not found: {call_sid}")
        sys.exit(1)

    print(f"\nTranscript Analysis: {call_sid}")
    print("-" * 50)
    print(f"Status: {transcript.get('status', 'unknown')}")
    print(f"Scenario: {transcript.get('scenario_name', 'unknown')}")
    print(f"Turn count: {transcript.get('turn_count', 0)}")
    if transcript.get("duration_seconds"):
        print(f"Duration: {transcript.get('duration_seconds')}s")
    if transcript.get("completed_at"):
        print(f"Completed: {transcript.get('completed_at')}")

    scenario_info = transcript.get("scenario_info", {})
    if scenario_info:
        print(f"Test type: {scenario_info.get('test_type', 'standard')}")

    print("\n--- Realtime transcript (turn-by-turn) ---")
    for turn in transcript.get("transcript", []):
        speaker = turn.get("speaker", "unknown").capitalize()
        text = turn.get("text", "")
        confidence = turn.get("confidence")
        if confidence is not None:
            print(f"  {speaker}: {text} (confidence: {confidence:.2f})")
        else:
            print(f"  {speaker}: {text}")

    if "whisper_transcription" in transcript:
        print("\n--- Whisper transcription (full audio) ---")
        wt = transcript["whisper_transcription"]
        print(wt.get("full_text", ""))
        if wt.get("duration"):
            print(f"\n  Duration: {wt['duration']:.1f}s")
        if wt.get("transcribed_at"):
            print(f"  Transcribed at: {wt['transcribed_at']}")
    print()


if __name__ == "__main__":
    main()
