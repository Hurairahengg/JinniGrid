"""
JINNI Grid – Strategy Registry
Persistent strategy store using filesystem (JSON sidecar + .py code).
Survives server restarts. No database required.
app/services/strategy_registry.py
"""
import ast
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from typing import Optional

_strategies: dict = {}
_lock = threading.Lock()

# ── Storage Path ────────────────────────────────────────────────
# Lives under <project_root>/data/strategies/ — intentionally OUTSIDE
# the app/ and ui/ source trees so uvicorn's file-watcher never sees
# writes here, even when reload=True.

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_THIS_DIR)
_PROJECT_ROOT = os.path.dirname(_APP_DIR)
STRATEGIES_DIR = os.path.join(_PROJECT_ROOT, "data", "strategies")
os.makedirs(STRATEGIES_DIR, exist_ok=True)

# Legacy dir (Phase 1C wrote here — inside the reload zone)
_LEGACY_DIR = os.path.join(_PROJECT_ROOT, "strategies")


# ── Filename Sanitization ───────────────────────────────────────

_SAFE_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize_id(raw: str) -> str:
    """Strip unsafe chars, cap length, guarantee non-empty."""
    clean = _SAFE_RE.sub("_", raw.strip()).strip("_")[:64]
    return clean or "unnamed_strategy"


def _safe_path(filename: str) -> str:
    """Resolve inside STRATEGIES_DIR with traversal protection."""
    safe = os.path.basename(filename)
    full = os.path.realpath(os.path.join(STRATEGIES_DIR, safe))
    if not full.startswith(os.path.realpath(STRATEGIES_DIR)):
        raise ValueError(f"Path traversal blocked: {filename}")
    return full


def _code_path(sid: str) -> str:
    return _safe_path(f"{_sanitize_id(sid)}.py")


def _meta_path(sid: str) -> str:
    return _safe_path(f"{_sanitize_id(sid)}.meta.json")


# ── Atomic Write ────────────────────────────────────────────────

def _write_atomic(target: str, content: str) -> None:
    """Write to temp file in the same dir, then atomic rename."""
    parent = os.path.dirname(target)
    fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp, target)          # same-fs → os.rename (atomic)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Metadata Persistence ───────────────────────────────────────

def _save_meta(sid: str, record: dict) -> None:
    serialisable = {k: v for k, v in record.items() if k != "file_path"}
    _write_atomic(_meta_path(sid), json.dumps(serialisable, indent=2))


def _load_meta(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[STRATEGY] Bad metadata {path}: {exc}")
        return None


# ── AST Validation (unchanged logic) ───────────────────────────

def _ast_literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _validate_strategy_file(file_content: str) -> dict:
    result = {
        "valid": False, "error": None, "class_name": None,
        "strategy_id": None, "name": None, "description": None,
        "version": None, "min_lookback": None, "parameters": {},
    }
    try:
        tree = ast.parse(file_content)
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        return result

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        if "BaseStrategy" not in bases:
            continue

        result["class_name"] = node.name
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                val = _ast_literal(item.value)
                name = target.id
                if name == "strategy_id" and val is not None:
                    result["strategy_id"] = str(val)
                elif name == "name" and val is not None:
                    result["name"] = str(val)
                elif name == "description" and val is not None:
                    result["description"] = str(val)
                elif name == "version" and val is not None:
                    result["version"] = str(val)
                elif name == "min_lookback" and val is not None:
                    result["min_lookback"] = val
                elif name == "parameters" and isinstance(item.value, ast.Dict):
                    try:
                        result["parameters"] = ast.literal_eval(item.value)
                    except (ValueError, TypeError):
                        result["parameters"] = {}

        if result["strategy_id"]:
            result["valid"] = True
        else:
            result["strategy_id"] = node.name.lower()
            result["valid"] = True
        break

    if result["class_name"] is None:
        result["error"] = "No class extending BaseStrategy found in file."
    return result


# ── Startup Restore ─────────────────────────────────────────────

def load_strategies_from_disk() -> int:
    """
    Scan STRATEGIES_DIR for *.meta.json, restore into memory.
    Also migrates any orphan .py files from the legacy strategies/ dir.
    Called ONCE at server startup.
    """
    _migrate_legacy_dir()

    count = 0
    if not os.path.isdir(STRATEGIES_DIR):
        print("[STRATEGY] Startup: storage dir missing — nothing to load.")
        return 0

    for fname in sorted(os.listdir(STRATEGIES_DIR)):
        if not fname.endswith(".meta.json"):
            continue
        meta = _load_meta(os.path.join(STRATEGIES_DIR, fname))
        if not meta:
            continue
        sid = meta.get("strategy_id")
        if not sid:
            print(f"[STRATEGY] Skipping {fname}: no strategy_id")
            continue
        code = _code_path(sid)
        if not os.path.exists(code):
            print(f"[STRATEGY] Skipping {sid}: .py missing at {code}")
            continue
        meta["file_path"] = code
        with _lock:
            _strategies[sid] = meta
        count += 1
        print(f"[STRATEGY] Restored: {sid} ({meta.get('strategy_name', '?')})")

    print(f"[STRATEGY] Startup complete — {count} strategies loaded from {STRATEGIES_DIR}")
    return count


def _migrate_legacy_dir() -> None:
    """
    One-time migration: if the old <root>/strategies/ dir has .py files
    without corresponding entries in data/strategies/, re-validate and move.
    """
    if not os.path.isdir(_LEGACY_DIR):
        return
    migrated = 0
    for fname in os.listdir(_LEGACY_DIR):
        if not fname.endswith(".py"):
            continue
        src = os.path.join(_LEGACY_DIR, fname)
        try:
            with open(src, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        validation = _validate_strategy_file(content)
        if not validation["valid"]:
            print(f"[STRATEGY] Legacy skip (invalid): {fname}")
            continue
        sid = _sanitize_id(validation["strategy_id"])
        if os.path.exists(_code_path(sid)):
            continue  # already in new location
        # Migrate
        try:
            _write_atomic(_code_path(sid), content)
            now = datetime.now(timezone.utc)
            record = _build_record(sid, validation, now)
            _save_meta(sid, record)
            os.unlink(src)
            migrated += 1
            print(f"[STRATEGY] Migrated legacy: {fname} → {sid}")
        except Exception as e:
            print(f"[STRATEGY] Migration failed for {fname}: {e}")
    if migrated:
        print(f"[STRATEGY] Migrated {migrated} strategies from legacy dir.")


# ── Record Builder ──────────────────────────────────────────────

def _build_record(sid: str, validation: dict, now: datetime) -> dict:
    return {
        "strategy_id": sid,
        "strategy_name": validation["name"] or sid,
        "class_name": validation["class_name"],
        "version": validation["version"] or "unknown",
        "description": validation["description"] or "",
        "min_lookback": validation["min_lookback"],
        "parameters": validation["parameters"],
        "parameter_count": len(validation["parameters"]),
        "filename": f"{sid}.py",
        "file_path": _code_path(sid),
        "uploaded_at": now.isoformat(),
        "validation_status": "validated",
        "load_status": "registered",
        "error": None,
    }


# ── Public API ──────────────────────────────────────────────────

def upload_strategy(filename: str, file_content: str) -> dict:
    """Validate → atomic-write .py + .meta.json → register in memory."""

    if not filename.endswith(".py"):
        return {"ok": False, "error": "Only .py files accepted."}
    if not file_content or not file_content.strip():
        return {"ok": False, "error": "Empty file content."}

    validation = _validate_strategy_file(file_content)
    if not validation["valid"]:
        return {
            "ok": False,
            "error": validation["error"] or "Validation failed.",
            "validation": validation,
        }

    sid = _sanitize_id(validation["strategy_id"])
    now = datetime.now(timezone.utc)

    # ---- persist code ----
    code_file = _code_path(sid)
    try:
        _write_atomic(code_file, file_content)
    except Exception as e:
        print(f"[STRATEGY] Code write failed: {e}")
        return {"ok": False, "error": f"Failed to save strategy file: {e}"}

    # ---- persist metadata ----
    record = _build_record(sid, validation, now)
    try:
        _save_meta(sid, record)
    except Exception as e:
        print(f"[STRATEGY] Meta write failed: {e}")
        try:
            os.unlink(code_file)
        except OSError:
            pass
        return {"ok": False, "error": f"Failed to save metadata: {e}"}

    # ---- register in memory ----
    with _lock:
        _strategies[sid] = record

    print(f"[STRATEGY] Registered '{sid}' from {filename} (class={validation['class_name']})")
    return {
        "ok": True,
        "strategy_id": sid,
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
    rec = get_strategy(strategy_id)
    if not rec:
        return None
    path = rec.get("file_path")
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def validate_strategy(strategy_id: str) -> dict:
    rec = get_strategy(strategy_id)
    if not rec:
        return {"ok": False, "error": "Strategy not found."}
    content = get_strategy_file_content(strategy_id)
    if not content:
        return {"ok": False, "error": "Strategy file missing from disk."}
    validation = _validate_strategy_file(content)
    with _lock:
        if strategy_id in _strategies:
            _strategies[strategy_id]["validation_status"] = (
                "validated" if validation["valid"] else "failed"
            )
            _strategies[strategy_id]["error"] = validation.get("error")
    try:
        _save_meta(strategy_id, _strategies[strategy_id])
    except Exception as e:
        print(f"[STRATEGY] Meta update after re-validate failed: {e}")
    return {"ok": validation["valid"], "validation": validation}


def delete_strategy(strategy_id: str) -> dict:
    """Remove strategy from memory + disk."""
    with _lock:
        rec = _strategies.pop(strategy_id, None)
    if not rec:
        return {"ok": False, "error": "Strategy not found."}

    for path in (_code_path(strategy_id), _meta_path(strategy_id)):
        try:
            if os.path.exists(path):
                os.unlink(path)
                print(f"[STRATEGY] Deleted file: {path}")
        except OSError as e:
            print(f"[STRATEGY] Delete failed {path}: {e}")

    print(f"[STRATEGY] Removed '{strategy_id}'")
    return {"ok": True, "strategy_id": strategy_id}