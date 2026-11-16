"""Read the ignored project configuration, with defaults for older installs."""
import runpy
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

@lru_cache(maxsize=1)
def load():
    path=Path(__file__).resolve().parent.parent/'config.py'
    return SimpleNamespace(**runpy.run_path(str(path))) if path.is_file() else SimpleNamespace()
