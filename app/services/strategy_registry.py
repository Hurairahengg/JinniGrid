"""
JINNI Grid - Strategy Registry
In-memory strategy store. Upload, validate (AST), list, serve file content.
No database — all lost on restart.
"""
import ast
import os
import threading
import uuid
from datetime import datetime, timezone

_strategies: dict = {}
_lock = threading.Lock()

# Uploaded .py files live here
_this_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir = os.path.dirname(_this_dir)
_project_root = os.path.dirname(_app_dir)
STRATEGIES_DIR = os.path.join(_project_root, "strategies")
os.makedirs(STRATEGIES_DIR, exist_ok=True)


# ── AST-based lightweight validation ────────────────────────────────

def _ast_literal(node):
    """Safely extract a literal value from an AST node."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _validate_strategy_file(file_content: str) -> dict:
    """
    Parse .py with AST. Find BaseStrategy subclass, extract metadata.
    Does NOT import or execute the code.
    """
    result = {
        "valid": False,
        "error": None,
        "class_name": None,
        "strategy_id": None,
        "name": None,
        "description": None,
        "version": None,
        "min_lookback": None,
        "parameters": {},
    }

    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        return result

    # Walk top-level class definitions
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class inherits from BaseStrategy (by name)
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        if "BaseStrategy" not in bases:
            continue

        result["class_name"] = node.name

        # Extract class-level assignments
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        val = _ast_literal(item.value)
                        if target.id == "strategy_id" and val is not None:
                            result["strategy_id"] = str(val)
                        elif target.id == "name" and val is not None:
                            result["name"] = str(val)
                        elif target.id == "description" and val is not None:
                            result["description"] = str(val)
                        elif target.id == "version" and val is not None:
                            result["version"] = str(val)
                        elif target.id == "min_lookback" and val is not None:
                            result["min_lookback"] = val
                        elif target.id == "parameters" and isinstance(item.value, ast.Dict):
                            try:
                                result["parameters"] = ast.literal_eval(item.value)
                            except (ValueError, TypeError):
                                result["parameters"] = {}

        # Found a BaseStrategy subclass — good enough
        if result["strategy_id"]:
            result["valid"] = True
        else:
            # Use class name as fallback id
            result["strategy_id"] = node.name.lower()
            result["valid"] = True

        break  # first BaseStrategy subclass wins

    if result["class_name"] is None:
        result["error"] = "No class extending BaseStrategy found in file."

    return result


# ── Public API ──────────────────────────────────────────────────────

def upload_strategy(filename: str, file_content: str) -> dict:
    """
    Validate and register a strategy .py file.
    Returns dict with registration result.
    """
    if not filename.endswith(".py"):
        return {"ok": False, "error": "Only .py files accepted."}

    validation = _validate_strategy_file(file_content)

    if not validation["valid"]:
        return {
            "ok": False,
            "error": validation["error"] or "Validation failed.",
            "validation": validation,
        }

    strategy_id = validation["strategy_id"]
    now = datetime.now(timezone.utc)

    # Write file to disk
    safe_filename = f"{strategy_id}.py"
    file_path = os.path.join(STRATEGIES_DIR, safe_filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    record = {
        "strategy_id": strategy_id,
        "strategy_name": validation["name"] or strategy_id,
        "class_name": validation["class_name"],
        "version": validation["version"] or "unknown",
        "description": validation["description"] or "",
        "min_lookback": validation["min_lookback"],
        "parameters": validation["parameters"],
        "parameter_count": len(validation["parameters"]),
        "filename": safe_filename,
        "file_path": file_path,
        "uploaded_at": now.isoformat(),
        "validation_status": "validated",
        "load_status": "registered",
        "error": None,
    }

    with _lock:
        _strategies[strategy_id] = record

    print(f"[STRATEGY] Registered '{strategy_id}' from {filename} (class={validation['class_name']})")

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "strategy_name": record["strategy_name"],
        "validation": validation,
    }


def get_all_strategies() -> list:
    with _lock:
        return list(_strategies.values())


def get_strategy(strategy_id: str) -> dict | None:
    with _lock:
        return _strategies.get(strategy_id)


def get_strategy_file_content(strategy_id: str) -> str | None:
    """Return raw .py content for transfer to worker."""
    rec = get_strategy(strategy_id)
    if not rec:
        return None
    path = rec.get("file_path")
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    """Re-validate an already registered strategy."""
    rec = get_strategy(strategy_id)
    if not rec:
        return {"ok": False, "error": "Strategy not found."}
    content = get_strategy_file_content(strategy_id)
    if not content:
        return {"ok": False, "error": "Strategy file missing from disk."}
    validation = _validate_strategy_file(content)
    with _lock:
        if strategy_id in _strategies:
            _strategies[strategy_id]["validation_status"] = "validated" if validation["valid"] else "failed"
            _strategies[strategy_id]["error"] = validation.get("error")
    return {"ok": validation["valid"], "validation": validation}