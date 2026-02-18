"""
Utility functions for logging and path resolution.

Used by phone_system, scenario_loader, recording_manager,
transcript_manager, and conversation for consistent log format.
"""

import os
from datetime import datetime
from typing import Literal

LogLevel = Literal["SUCCESS", "ERROR", "WARNING", "INFO", "STATUS", "COST"]


def log(level: LogLevel, message: str, details: str = "") -> None:
    """
    Print formatted log message.

    Args:
        level: Log level (SUCCESS, ERROR, WARNING, INFO, STATUS, COST)
        message: Main message
        details: Optional details (printed on next line with indent)
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")
    if details:
        print(f"         {details}")


def get_project_root() -> str:
    """
    Return project root directory (parent of src/).

    Returns:
        Absolute path to project root.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
