from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any


def load_module(module_name: str) -> ModuleType:
    return importlib.import_module(module_name)


def load_attr(module_name: str, attr_name: str) -> Any:
    module = load_module(module_name)
    return getattr(module, attr_name)
