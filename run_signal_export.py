#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容入口；实现见 scripts/runtime/run_signal_export.py。"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "runtime" / "run_signal_export.py"
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
