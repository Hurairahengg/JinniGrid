"""
JINNI GRID — Strategy Loader
Dynamically loads a BaseStrategy subclass from raw .py source code.
Does NOT write to disk in production — loads from string via importlib.
"""
import importlib
import importlib.util
import os
import sys
import tempfile
import traceback
from typing import Optional, Tuple


def load_strategy_from_source(
    source_code: str,
    class_name: str,
    strategy_id: str,
) -> Tuple[Optional[object], Optional[str]]:
    """
    Load a strategy class from raw Python source.

    Returns:
        (strategy_instance, None) on success
        (None, error_message) on failure
    """
    # We need BaseStrategy importable by the loaded module.
    # The loaded .py does `from backend.strategies.base import BaseStrategy`
    # or similar. We patch sys.modules so any common import path resolves
    # to our local base_strategy module.
    try:
        _ensure_base_importable()
    except Exception as e:
        return None, f"Failed to prepare base imports: {e}"

    module_name = f"jinni_strategy_{strategy_id}"

    try:
        # Write to temp file so importlib can load it properly
        tmp_dir = tempfile.mkdtemp(prefix="jinni_strat_")
        tmp_path = os.path.join(tmp_dir, f"{module_name}.py")

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        if spec is None or spec.loader is None:
            return None, "Failed to create module spec."

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find the target class
        klass = getattr(module, class_name, None)
        if klass is None:
            available = [k for k in dir(module) if not k.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"

        # Instantiate
        instance = klass()

        # Verify interface
        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."

        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed to load strategy: {e}\n{tb}")
        return None, f"{type(e).__name__}: {e}"


def _ensure_base_importable():
    """
    Make BaseStrategy importable under common import paths that
    strategy files might use (e.g. 'from backend.strategies.base import BaseStrategy').
    """
    worker_dir = os.path.dirname(os.path.abspath(__file__))

    # Import our local base_strategy module
    if "base_strategy" not in sys.modules:
        base_path = os.path.join(worker_dir, "base_strategy.py")
        spec = importlib.util.spec_from_file_location("base_strategy", base_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules["base_strategy"] = mod
            spec.loader.exec_module(mod)

    base_mod = sys.modules.get("base_strategy")
    if base_mod is None:
        return

    # Patch common import paths strategies might use
    # 'from backend.strategies.base import BaseStrategy'
    class _FakePackage:
        pass

    if "backend" not in sys.modules:
        sys.modules["backend"] = _FakePackage()
    if "backend.strategies" not in sys.modules:
        sys.modules["backend.strategies"] = _FakePackage()
    sys.modules["backend.strategies.base"] = base_mod