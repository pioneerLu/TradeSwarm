#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容入口；实现见 scripts/experimental/run_platform_test.py。"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "experimental" / "run_platform_test.py"
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
