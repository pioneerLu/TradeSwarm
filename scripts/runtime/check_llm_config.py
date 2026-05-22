#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Print resolved SiliconFlow LLM metadata without making any LLM requests.

This is intended for experiment reproducibility checks:
- verify profile exists (fail-fast)
- verify model_name/temperature/base_url before a run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.config import get_llm_metadata  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check and print resolved LLM metadata (no network calls).",
    )
    parser.add_argument("--config", type=str, default=str(REPO_ROOT / "config" / "config.yaml"))
    parser.add_argument("--llm-profile", type=str, default=None)
    parser.add_argument("--llm-model", type=str, default=None)
    parser.add_argument("--llm-temperature", type=float, default=None)
    args = parser.parse_args()

    meta = get_llm_metadata(
        config_path=args.config,
        profile=args.llm_profile,
        model_override=args.llm_model,
        temperature_override=args.llm_temperature,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

