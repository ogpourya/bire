"""Regex flag mappings and conversion utilities."""

from __future__ import annotations

import re
from collections.abc import Sequence

FLAG_NAME_MAP: dict[int, str] = {
    re.ASCII: "ASCII",
    re.IGNORECASE: "IGNORECASE",
    re.LOCALE: "LOCALE",
    re.MULTILINE: "MULTILINE",
    re.DOTALL: "DOTALL",
    re.VERBOSE: "VERBOSE",
    re.UNICODE: "UNICODE",
}

SHORT_FLAG_MAP: dict[str, int] = {
    "a": re.ASCII,
    "i": re.IGNORECASE,
    "l": re.LOCALE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
    "u": re.UNICODE,
}

NAME_TO_FLAG: dict[str, int] = {v: k for k, v in FLAG_NAME_MAP.items()}


def flags_to_names(flags: int) -> list[str]:
    """Convert an integer flag bitmask to an ordered list of flag names."""
    names: list[str] = []
    for bit in (
        re.ASCII,
        re.IGNORECASE,
        re.LOCALE,
        re.MULTILINE,
        re.DOTALL,
        re.VERBOSE,
        re.UNICODE,
    ):
        if flags & bit:
            names.append(FLAG_NAME_MAP[bit])
    return names


def names_to_flags(names: Sequence[str]) -> int:
    """Convert flag names to an integer flag bitmask."""
    flags = 0
    for name in names:
        cleaned = name.strip().upper()
        if cleaned in NAME_TO_FLAG:
            flags |= NAME_TO_FLAG[cleaned]
        else:
            raise ValueError(f"Unknown flag name: {name}")
    return flags
