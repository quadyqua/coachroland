"""Pytest bootstrap: make the CDragon static data a HARD precondition for the suite.

Champion costs/traits come from a 25 MB CDragon blob that's downloaded once and cached.
On a cold cache (fresh clone, cache wipe, or set rotation) the download happens mid-run,
and until it lands cost/trait lookups return empty — which turns real assertions into a
misleading partial pass (e.g. 18/20) that only goes green once the cache warms. Loading it
up front here means the suite either runs against real data or fails loudly with a clear
message. See cdragon.ensure_loaded().

(Standalone `python tests/test_x.py` runs call ensure_loaded() themselves; this covers the
pytest path.)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tftwatch import cdragon   # noqa: E402

cdragon.ensure_loaded()
