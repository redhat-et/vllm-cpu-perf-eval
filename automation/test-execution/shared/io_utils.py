#!/usr/bin/env python3
"""Common I/O utilities for JSON file operations and formatting.

This module provides shared utilities for:
- Loading and saving JSON files with consistent error handling
- Time duration formatting
- Common file path validation
"""

import json
from pathlib import Path
from typing import Any, Dict

# Time conversion constants
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data as a dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Save data to a JSON file with pretty formatting.

    Args:
        file_path: Path to the output JSON file
        data: Dictionary to save as JSON
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  # Add trailing newline


def format_duration(total_seconds: float) -> str:
    """Format duration as HH:MM:SS string.

    Args:
        total_seconds: Duration in seconds

    Returns:
        Formatted string in HH:MM:SS format

    Example:
        >>> format_duration(3665)
        '1:01:05'
    """
    hours = int(total_seconds // SECONDS_PER_HOUR)
    minutes = int((total_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
    seconds = int(total_seconds % SECONDS_PER_MINUTE)
    return f"{hours}:{minutes:02d}:{seconds:02d}"
