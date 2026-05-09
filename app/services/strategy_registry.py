"""
JINNI Grid — Strategy Registry (DB-backed)
app/services/strategy_registry.py

Strategies are stored:
  - Source code: data/strategies/{strategy_id}.py (filesystem)
  - Metadata: SQLite via app/persistence.py
"""

import ast
import hashlib
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from app.persistence import (
    save_strategy, get_all_strategies_db, get_strategy_db, log_event_db
)

log = logging.getLogger("jinni.strategy")

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "strategies"
)

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(STRATEGY_DIR, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    return safe or "unnamed_strategy"


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

def _safe_eval_node(node):
    """
    Safely evaluate an AST node to a Python literal.
    Handles: str, int, float, bool, None, dict, list, tuple, set.
    Returns None if the node cannot be safely evaluated.
    """
    try:
        # ast.literal_eval on the source representation
        source = ast.unparse(node)
        return ast.literal_eval(source)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None

def _extract_strategy_class(source: str) -> Optional[dict]:
    """Parse source to find a class extending BaseStrategy."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        log.warning(f"Strategy syntax error: {e}")
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name == "BaseStrategy":
                info = {"class_name": node.name}
                for item in node.body:
                    # Class-level simple assignments: strategy_id = "xyz"
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if not isinstance(target, ast.Name):
                                continue
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[target.id] = val
                    # Class-level annotated assignments: strategy_id: str = "xyz"
                    elif isinstance(item, ast.AnnAssign):
                        if (isinstance(item.target, ast.Name)
                                and item.value is not None):
                            val = _safe_eval_node(item.value)
                            if val is not None:
                                info[item.target.id] = val
                log.info(f"Extracted strategy class: {node.name} fields={list(info.keys())}")
                return info

    # Log what classes WERE found for debugging
    classes_found = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if classes_found:
        log.warning(f"Found classes {classes_found} but none extend BaseStrategy")
    else:
        log.warning("No classes found in strategy source at all")
    return None


# =============================================================================
# Public API
# =============================================================================

def upload_strategy(filename: str, source_code: str) -> dict:
    """Upload and persist a strategy file."""
    _ensure_dir()

    # Check syntax first
    try:
        ast.parse(source_code)
    except SyntaxError as e:
        return {
            "ok": False,
            "error": f"Python syntax error at line {e.lineno}: {e.msg}",
        }

    info = _extract_strategy_class(source_code)
    if info is None:
        # Give a detailed error
        try:
            tree = ast.parse(source_code)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        except Exception:
            classes = []
        if classes:
            return {
                "ok": False,
                "error": f"Found classes {classes} but none extend BaseStrategy. "
                         f"Your class must inherit from BaseStrategy.",
            }
        return {
            "ok": False,
            "error": "No class found in file. Strategy must contain a class extending BaseStrategy.",
        }

    strategy_id = info.get("strategy_id", "")
    if not strategy_id:
        strategy_id = info["class_name"].lower()

    class_name = info["class_name"]
    name = info.get("name", class_name)
    description = info.get("description", "")
    version = info.get("version", "1.0")
    min_lookback = info.get("min_lookback", 0)
    parameters = info.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}

    safe_name = _sanitize_filename(strategy_id)
    file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")
    fhash = _file_hash(source_code)

    # Atomic write
    tmp_path = file_path + ".tmp"
    with _lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(source_code)
            os.replace(tmp_path, file_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"ok": False, "error": f"File write failed: {e}"}

    now = datetime.now(timezone.utc).isoformat()

    # Persist metadata to DB
    save_strategy(strategy_id, {
        "filename": filename,
        "class_name": class_name,
        "name": name,
        "description": description,
        "version": version,
        "min_lookback": min_lookback,
        "file_hash": fhash,
        "file_path": file_path,
        "parameters": parameters,
        "uploaded_at": now,
        "is_valid": True,
    })

    log.info(f"Strategy uploaded: {strategy_id} ({class_name}) hash={fhash}")

    log_event_db("strategy", "uploaded",
                 f"Strategy {strategy_id} uploaded from {filename}",
                 strategy_id=strategy_id,
                 data={"class_name": class_name, "version": version, "hash": fhash})

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": class_name,
        "name": name,
        "version": version,
        "file_hash": fhash,
    }


def get_all_strategies() -> list:
    """Return all valid strategies from DB."""
    db_strategies = get_all_strategies_db()
    result = []
    for s in db_strategies:
        params = s.get("parameters", {})
        if isinstance(params, str):
            try:
                import json
                params = json.loads(params)
            except Exception:
                params = {}
        result.append({
            "strategy_id": s["strategy_id"],
            "strategy_name": s.get("name", s["strategy_id"]),
            "name": s.get("name", s["strategy_id"]),
            "filename": s.get("filename", ""),
            "class_name": s.get("class_name", ""),
            "description": s.get("description", ""),
            "version": s.get("version", ""),
            "min_lookback": s.get("min_lookback", 0),
            "file_hash": s.get("file_hash", ""),
            "uploaded_at": s.get("uploaded_at", ""),
            "validation_status": "validated" if s.get("is_valid") else "invalid",
            "parameter_count": len(params) if isinstance(params, dict) else 0,
            "parameters": params,
            "error": None,
        })
    return result


def get_strategy(strategy_id: str) -> Optional[dict]:
    return get_strategy_db(strategy_id)


def get_strategy_file_content(strategy_id: str) -> Optional[str]:
    """Read strategy source code from disk."""
    rec = get_strategy_db(strategy_id)
    if not rec:
        return None

    file_path = rec.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        # Try default path
        safe_name = _sanitize_filename(strategy_id)
        file_path = os.path.join(STRATEGY_DIR, f"{safe_name}.py")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    content = get_strategy_file_content(strategy_id)
    if content is None:
        return {"ok": False, "error": "Strategy file not found."}

    info = _extract_strategy_class(content)
    if info is None:
        return {"ok": False, "error": "No BaseStrategy class found in file."}

    try:
        compile(content, f"{strategy_id}.py", "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}

    log_event_db("strategy", "validated",
                 f"Strategy {strategy_id} passed validation",
                 strategy_id=strategy_id)

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "class_name": info["class_name"],
        "valid": True,
    }


def load_strategies_from_disk():
    """Scan data/strategies/ for .py files and register any not already in DB."""
    _ensure_dir()
    count = 0

    for fname in os.listdir(STRATEGY_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(STRATEGY_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue

        info = _extract_strategy_class(source)
        if info is None:
            continue

        strategy_id = info.get("strategy_id", "")
        if not strategy_id:
            strategy_id = info["class_name"].lower()

        # Check if already in DB
        existing = get_strategy_db(strategy_id)
        if existing:
            continue

        save_strategy(strategy_id, {
            "filename": fname,
            "class_name": info["class_name"],
            "name": info.get("name", info["class_name"]),
            "description": info.get("description", ""),
            "version": info.get("version", "1.0"),
            "min_lookback": info.get("min_lookback", 0),
            "file_hash": _file_hash(source),
            "file_path": fpath,
            "parameters": info.get("parameters", {}),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
        })
        count += 1

    if count > 0:
        log.info(f"Loaded {count} strategies from disk into DB")