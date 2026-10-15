"""Named scenarios used across experiments.

The definitions live in lunarsim/phases.py so that the installed package has them too;
this module re-exports them for the experiment scripts (PHASES, OWNERS, P1, P2, P3).
"""
import sys
sys.path.insert(0, ".")
from lunarsim.phases import *  # noqa: F401,F403
from lunarsim.phases import PHASES, OWNERS, P1, P2, P3  # noqa: F401  (explicit for readers and linters)
