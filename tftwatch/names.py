"""Turn raw Riot data IDs into human-readable names.

Riot IDs look like 'TFT14_Jinx', 'TFT14_Vanguard', 'TFT9_Augment_BuiltDifferent2'.
This is a best-effort prettifier. For perfect display names we'd map against
Community Dragon (a Phase 1 upgrade); for scouting this is plenty readable.
"""
import re

_SET_PREFIX = re.compile(r"^TFT\d+[a-zA-Z]?_")
_KIND_PREFIX = re.compile(r"^(Augment|Item|Trait|Set\d+)_", re.IGNORECASE)
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def humanize(raw: str) -> str:
    """'TFT14_Jinx' -> 'Jinx', 'TFT9_Augment_BuiltDifferent2' -> 'Built Different 2'."""
    if not raw:
        return ""
    s = _SET_PREFIX.sub("", raw)
    s = s.replace("TFT_", "")
    s = _KIND_PREFIX.sub("", s)
    s = _CAMEL.sub(" ", s)
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)  # split trailing numbers: "Different2" -> "Different 2"
    return s.strip()
