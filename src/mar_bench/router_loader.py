from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_router_module(router_path: str) -> ModuleType:
    path = Path(router_path).resolve()
    module_name = "mar_router_under_test"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load router module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
