# -*- coding: utf-8 -*-
"""启动 memory.db 本地 Web 查看器（实现依赖仓库根目录 db_viewer 包）"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from db_viewer.app import main

if __name__ == "__main__":
    main()
