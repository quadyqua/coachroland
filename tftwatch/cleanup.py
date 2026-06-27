"""Capture hygiene — keep nothing piling up.

The live watcher reads frames in memory and never saves them. The only images
that ever touch disk are debug captures, and they go in ONE managed temp dir that
gets purged at startup, after every game, and on exit. Short-term analysis is kept
as small structured data in memory only (see CoachRoland), never as images.
"""
import tempfile
import pathlib

CAPTURE_DIR = pathlib.Path(tempfile.gettempdir()) / "tftwatch_captures"


def capture_dir() -> pathlib.Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    return CAPTURE_DIR


def purge_captures() -> int:
    """Delete every file in the managed capture dir. Returns count removed."""
    if not CAPTURE_DIR.exists():
        return 0
    removed = 0
    for f in CAPTURE_DIR.glob("*"):
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed
