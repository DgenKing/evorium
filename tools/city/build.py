#!/usr/bin/env python3
"""Run the deterministic, build-machine-only Ancoats city pipeline."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CITY = Path(__file__).resolve().parent
STAGES = ("fetch", "heights", "geometry", "facades", "props", "export", "navmesh")


def load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("Build dependency missing: install tools/city/requirements.txt") from exc
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise SystemExit(f"Unsupported or invalid city config: {path}")
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, help="run one stage (default: all)")
    parser.add_argument("--config", type=Path, default=CITY / "config.yaml")
    parser.add_argument("--fixture", action="store_true", help="use committed offline fixture data")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    sys.path.insert(0, str(CITY))
    stages = [args.stage] if args.stage else list(STAGES)
    for name in stages:
        module_name = f"{name}"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                raise SystemExit(f"City stage '{name}' is not implemented yet") from exc
            raise
        run = getattr(module, "run", None)
        if not callable(run):
            raise SystemExit(f"City stage '{name}' must expose run(config, *, fixture=False)")
        print(f"[{name}]", flush=True)
        result = run(config, fixture=args.fixture)
        if result is not None:
            print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
