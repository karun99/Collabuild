#!/usr/bin/env python3
"""Backward-compatible entry point: delegates to `python -m collabuild`."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from collabuild.__main__ import main
main()
