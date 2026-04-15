#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download a BGE embedding model into a local directory under repo root.

Example:
  python scripts/runtime/download_bge_model.py --repo BAAI/bge-small-zh-v1.5 --out models/bge-small-zh-v1.5
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _strip_wrapping_quotes(s: str) -> str:
    s = str(s or "")
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def main() -> None:
    p = argparse.ArgumentParser(description="Download BGE model to local folder (HF snapshot_download)")
    p.add_argument("--repo", type=str, default="BAAI/bge-small-zh-v1.5")
    p.add_argument("--out", type=str, default="models/bge-small-zh-v1.5")
    p.add_argument(
        "--endpoint",
        type=str,
        default="",
        help="HuggingFace Hub endpoint mirror (e.g. https://hf-mirror.com). When set, exports HF_ENDPOINT.",
    )
    args = p.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Windows 常见坑：环境变量被写成带引号的路径，导致 Path('"E:\\xx"\\token') 报 Errno 22
    for k in ("HF_HOME", "TRANSFORMERS_CACHE", "HUGGINGFACE_HUB_CACHE"):
        if os.getenv(k):
            os.environ[k] = _strip_wrapping_quotes(os.getenv(k) or "")

    # Use HF mirror endpoint if provided
    if args.endpoint:
        os.environ["HF_ENDPOINT"] = _strip_wrapping_quotes(args.endpoint.strip())

    # 如果没设置缓存目录，就默认放到项目内，避免写到不可写磁盘
    repo_root = Path(__file__).resolve().parents[2]
    default_hf_home = repo_root / "data_cache" / "hf"
    default_hf_home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(default_hf_home))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(default_hf_home / "hub"))

    try:
        from huggingface_hub import snapshot_download  # type: ignore[import-not-found]
    except Exception as e:
        raise RuntimeError("缺少 huggingface-hub。请执行：pip install -U \".[embeddings]\"") from e

    snapshot_download(
        repo_id=args.repo,
        local_dir=str(out_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    print(f"[OK] Downloaded {args.repo} -> {out_dir}")


if __name__ == "__main__":
    main()

