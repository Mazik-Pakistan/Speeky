"""
Accent Assessment feature area.

Holds three related stories (ACC-US-01/02/03) around target-accent
scoring. Only ACC-US-03 (Target Accent / English Variant Selection) is
implemented so far — target_accent_selection.py. The other two
(staleness re-baseline, score dispute) are not built yet; this package
exists now so their modules land alongside this one instead of being
scattered elsewhere later.

Distinct from backend/lib/pronunciation_coach/ (word-level pronunciation
scoring pipeline) - not modified by, and does not modify, anything in
that package. See target_accent_selection.py's module docstring for how
the two are expected to relate once wired together.
"""

from .target_accent_selection import (
    AccentChangeLogEntry,
    TargetAccentOption,
    TargetAccentRegistry,
    TargetAccentSelectionResult,
    TargetAccentSelectionService,
    UserAccentPreference,
)

__all__ = [
    "AccentChangeLogEntry",
    "TargetAccentOption",
    "TargetAccentRegistry",
    "TargetAccentSelectionResult",
    "TargetAccentSelectionService",
    "UserAccentPreference",
]
