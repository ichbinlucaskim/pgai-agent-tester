"""
Test script with scenario selection.

Usage:
  python test_call.py
  python test_call.py appointment_scheduling
  python test_call.py --list
"""

import sys
import time

from src.phone_system import make_call
from src.scenario_loader import list_scenarios


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_scenarios()
        return

    scenario_name = sys.argv[1] if len(sys.argv) > 1 else "appointment_scheduling"

    print(f"[INFO] Initiating test call with scenario: {scenario_name}")
    call_sid = make_call(scenario_name)

    if call_sid:
        print(f"[SUCCESS] Call SID: {call_sid}")
        print("[INFO] Check Flask console for conversation logs")
        print("[INFO] Press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[SUCCESS] Exiting...")
    else:
        print("[ERROR] Call failed")


if __name__ == "__main__":
    main()
