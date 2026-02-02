# arbitrage/utils/paths.py
from pathlib import Path

PROJECT_ROOT = Path.cwd()

if not (Path.cwd() / "config").exists():
    raise RuntimeError(f"请在项目根目录{PROJECT_ROOT}运行 arbitrage")

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
