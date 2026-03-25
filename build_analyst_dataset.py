#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容入口；实现见 scripts/experimental/build_analyst_dataset.py。"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "scripts" / "experimental" / "build_analyst_dataset.py"
sys.argv[0] = str(TARGET)
runpy.run_path(str(TARGET), run_name="__main__")
