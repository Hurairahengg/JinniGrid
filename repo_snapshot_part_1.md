# Repository Snapshot - Part 1 of 3

- Root folder: `/home/hurairahengg/Documents/JinniGrid`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra. currently im done coding the strategy system and some backend logging savign preesistence saving like sql typa thing with some protfolio data savign as well. but none of the proftfolio stuff ahs been wired to ui nro are the logs. so later u will get to code many things including this also my tsrarggey stuff is ungtested rn as well so yeah . so firm i wil ldrop u my whole project codebases from my readme. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood? and at the strat of every chat u will confirm wetehjr u still have all 26 files in ur memory or not undertstood? to reduce hallucainations
- Total files indexed: `26`
- Files in this chunk: `11`
## Full Project Tree

```text
app/__init__.py
app/config.py
app/logging_config.py
app/persistence.py
app/routes/__init__.py
app/routes/mainRoutes.py
app/services/__init__.py
app/services/mainServices.py
app/services/strategy_registry.py
config.yaml
main.py
README.md
requirements.txt
ui/css/style.css
ui/index.html
ui/js/main.js
ui/js/workerDetailRenderer.js
worker/config.yaml
worker/event_log.py
worker/execution.py
worker/indicators.py
worker/portfolio.py
worker/README.md
worker/requirements.txt
worker/strategyWorker.py
worker/worker_agent.py
```

## Files In This Chunk - Part 1

```text
app/__init__.py
app/routes/__init__.py
app/routes/mainRoutes.py
app/services/strategy_registry.py
ui/js/main.js
worker/config.yaml
worker/event_log.py
worker/indicators.py
worker/README.md
worker/requirements.txt
worker/strategyWorker.py
```

## File Contents


---

## FILE: `app/__init__.py`

- Relative path: `app/__init__.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/__init__.py`
- Size bytes: `2034`
- SHA256: `1d2a3166b4f2cd9b91fb58554de998d2261a21fc79daee6db6c1dc2b85da5304`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid Mother Server - Application Factory
app/__init__.py
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import Config
from app.routes.mainRoutes import router as main_routes_router


def create_app() -> FastAPI:
    app_config = Config.get_app_config()
    cors_origins = Config.get_cors_origins()

    app = FastAPI(
        title=app_config["name"],
        version=app_config["version"],
        description="JINNI Grid Mother Server - Integrated Dashboard + Fleet API",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(main_routes_router)

    ui_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "ui")
    )

    css_dir = os.path.join(ui_dir, "css")
    js_dir = os.path.join(ui_dir, "js")
    index_path = os.path.join(ui_dir, "index.html")

    if os.path.isdir(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(index_path)

    # ── Initialize persistence ───────────────────────────────
    from app.persistence import init_db
    init_db()

    # ── Restore strategies from disk ─────────────────────────
    from app.services.strategy_registry import load_strategies_from_disk
    load_strategies_from_disk()

    # ── Load workers from DB into memory cache ───────────────
    from app.services.mainServices import _load_workers_from_db
    _load_workers_from_db()

    return app
```

---

## FILE: `app/routes/__init__.py`

- Relative path: `app/routes/__init__.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/routes/__init__.py`
- Size bytes: `29`
- SHA256: `008e834fc6645b007ba1e7e104c0801cdc690603f54351be5442a106658a3181`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
# JINNI Grid - Route package
```

---

## FILE: `app/routes/mainRoutes.py`

- Relative path: `app/routes/mainRoutes.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/routes/mainRoutes.py`
- Size bytes: `12026`
- SHA256: `fc19dfb410979858b3398cf791d3e33d5db3e4f179c84337d9cb984d47a2da4b`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined API Routes
app/routes/mainRoutes.py
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.config import Config

from app.services.mainServices import (
    process_heartbeat,
    get_all_workers,
    get_fleet_summary,
    get_portfolio_summary,
    get_equity_history,
    create_deployment,
    get_all_deployments,
    get_deployment,
    update_deployment_state,
    stop_deployment,
    enqueue_command,
    poll_commands,
    ack_command,
)

from app.services.strategy_registry import (
    upload_strategy,
    get_all_strategies,
    get_strategy,
    get_strategy_file_content,
    validate_strategy,
)


router = APIRouter()


# =============================================================================
# Health Endpoints
# =============================================================================

@router.get("/api/health", tags=["Health"])
async def health_check():
    app_config = Config.get_app_config()
    return {
        "status": "ok",
        "service": app_config["name"],
        "version": app_config["version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Grid Fleet Endpoints
# =============================================================================

class HeartbeatPayload(BaseModel):
    worker_id: str
    worker_name: Optional[str] = None
    host: Optional[str] = None
    state: Optional[str] = "online"
    agent_version: Optional[str] = None
    mt5_state: Optional[str] = None
    account_id: Optional[str] = None
    broker: Optional[str] = None
    active_strategies: Optional[List[str]] = None
    open_positions_count: Optional[int] = 0
    floating_pnl: Optional[float] = None
    errors: Optional[List[str]] = None
    # Pipeline diagnostics
    total_ticks: Optional[int] = 0
    total_bars: Optional[int] = 0
    on_bar_calls: Optional[int] = 0
    signal_count: Optional[int] = 0
    last_bar_time: Optional[str] = None
    current_price: Optional[float] = None


@router.post("/api/Grid/workers/heartbeat", tags=["Grid"])
async def worker_heartbeat(payload: HeartbeatPayload):
    if not payload.worker_id or not payload.worker_id.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "error": "worker_id is required and must be a non-empty string",
            },
        )

    return process_heartbeat(payload.model_dump())


@router.get("/api/Grid/workers", tags=["Grid"])
@router.get("/api/grid/workers", tags=["Grid"])
async def list_workers():
    return {
        "ok": True,
        "workers": get_all_workers(),
        "summary": get_fleet_summary(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Portfolio Endpoints
# =============================================================================

@router.get("/api/portfolio/summary", tags=["Portfolio"])
async def portfolio_summary():
    return {
        "portfolio": get_portfolio_summary(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/portfolio/equity-history", tags=["Portfolio"])
async def equity_history():
    history = get_equity_history()
    return {
        "equity_history": history,
        "points": len(history),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Strategy Endpoints
# =============================================================================

@router.post("/api/grid/strategies/upload", tags=["Strategies"])
async def upload_strategy_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files accepted.")

    content = await file.read()

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text.")

    result = upload_strategy(file.filename, text)

    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)

    return result


@router.get("/api/grid/strategies", tags=["Strategies"])
async def list_strategies():
    strategies = get_all_strategies()

    return {
        "ok": True,
        "strategies": strategies,
        "count": len(strategies),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/strategies/{strategy_id}", tags=["Strategies"])
async def get_strategy_detail(strategy_id: str):
    rec = get_strategy(strategy_id)

    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")

    return {
        "ok": True,
        "strategy": rec,
    }


@router.get("/api/grid/strategies/{strategy_id}/file", tags=["Strategies"])
async def get_strategy_file(strategy_id: str):
    content = get_strategy_file_content(strategy_id)

    if content is None:
        raise HTTPException(status_code=404, detail="Strategy file not found.")

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "file_content": content,
    }


@router.post("/api/grid/strategies/{strategy_id}/validate", tags=["Strategies"])
async def validate_strategy_endpoint(strategy_id: str):
    result = validate_strategy(strategy_id)

    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result)

    return result


# =============================================================================
# Deployment Endpoints
# =============================================================================

class DeploymentCreate(BaseModel):
    strategy_id: str
    worker_id: str
    symbol: str
    tick_lookback_value: Optional[int] = 30
    tick_lookback_unit: Optional[str] = "minutes"
    bar_size_points: float
    max_bars_in_memory: Optional[int] = 500
    lot_size: Optional[float] = 0.01
    strategy_parameters: Optional[Dict[str, Any]] = None


@router.post("/api/grid/deployments", tags=["Deployments"])
async def create_deployment_endpoint(payload: DeploymentCreate):
    strat = get_strategy(payload.strategy_id)

    if not strat:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found. Upload it first.",
        )

    result = create_deployment(payload.model_dump())

    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)

    deployment = result["deployment"]

    file_content = get_strategy_file_content(payload.strategy_id)

    cmd_payload = {
        "deployment_id": deployment["deployment_id"],
        "strategy_id": deployment["strategy_id"],
        "strategy_file_content": file_content,
        "strategy_class_name": strat.get("class_name"),
        "symbol": deployment["symbol"],
        "tick_lookback_value": deployment["tick_lookback_value"],
        "tick_lookback_unit": deployment["tick_lookback_unit"],
        "bar_size_points": deployment["bar_size_points"],
        "max_bars_in_memory": deployment["max_bars_in_memory"],
        "lot_size": deployment["lot_size"],
        "strategy_parameters": deployment["strategy_parameters"] or {},
    }

    enqueue_command(payload.worker_id, "deploy_strategy", cmd_payload)

    update_deployment_state(deployment["deployment_id"], "sent_to_worker")

    return {
        "ok": True,
        "deployment_id": deployment["deployment_id"],
        "deployment": deployment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments", tags=["Deployments"])
async def list_deployments():
    deployments = get_all_deployments()

    return {
        "ok": True,
        "deployments": deployments,
        "count": len(deployments),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/grid/deployments/{deployment_id}", tags=["Deployments"])
async def get_deployment_detail(deployment_id: str):
    rec = get_deployment(deployment_id)

    if not rec:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    return {
        "ok": True,
        "deployment": rec,
    }


@router.post("/api/grid/deployments/{deployment_id}/stop", tags=["Deployments"])
async def stop_deployment_endpoint(deployment_id: str):
    dep = get_deployment(deployment_id)

    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")

    enqueue_command(
        dep["worker_id"],
        "stop_strategy",
        {
            "deployment_id": deployment_id,
        },
    )

    result = stop_deployment(deployment_id)
    return result


# =============================================================================
# Worker Command Endpoints
# =============================================================================

@router.get("/api/grid/workers/{worker_id}/commands/poll", tags=["Worker Commands"])
async def poll_worker_commands(worker_id: str):
    commands = poll_commands(worker_id)

    return {
        "ok": True,
        "worker_id": worker_id,
        "commands": commands,
        "count": len(commands),
    }


class CommandAck(BaseModel):
    command_id: str


@router.post("/api/grid/workers/{worker_id}/commands/ack", tags=["Worker Commands"])
async def ack_worker_command(worker_id: str, payload: CommandAck):
    result = ack_command(worker_id, payload.command_id)

    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result)

    return result


class RunnerStatusReport(BaseModel):
    deployment_id: str
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    symbol: Optional[str] = None
    runner_state: str
    bar_size_points: Optional[float] = None
    max_bars_in_memory: Optional[int] = None
    current_bars_count: Optional[int] = 0
    last_signal: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.post("/api/grid/workers/{worker_id}/runner-status", tags=["Worker Commands"])
async def report_runner_status(worker_id: str, payload: RunnerStatusReport):
    state_map = {
        "loading_strategy": "loading_strategy",
        "fetching_ticks": "fetching_ticks",
        "generating_initial_bars": "generating_initial_bars",
        "warming_up": "warming_up",
        "running": "running",
        "stopped": "stopped",
        "failed": "failed",
        "idle": "stopped",
    }

    dep_state = state_map.get(payload.runner_state)

    if dep_state:
        update_deployment_state(
            payload.deployment_id,
            dep_state,
            error=payload.last_error,
        )

    return {
        "ok": True,
        "received": True,
    }


# =============================================================================
# System Summary Endpoint
# =============================================================================

@router.get("/api/system/summary", tags=["System"])
async def system_summary():
    fleet = get_fleet_summary()
    portfolio = get_portfolio_summary()

    total = fleet["total_workers"]
    online = fleet["online_workers"]

    if online > 0:
        system_status = "operational"
    elif total > 0:
        system_status = "degraded"
    else:
        system_status = "no_workers"

    return {
        "total_nodes": total,
        "online_nodes": online,
        "stale_nodes": fleet["stale_workers"],
        "offline_nodes": fleet["offline_workers"],
        "warning_nodes": fleet["warning_workers"],
        "error_nodes": fleet["error_workers"],
        "total_open_positions": portfolio["open_positions"],
        "system_status": system_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

## FILE: `app/services/strategy_registry.py`

- Relative path: `app/services/strategy_registry.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/strategy_registry.py`
- Size bytes: `7911`
- SHA256: `7c3d6cd6fd7373b8db09e4fb7b8d95065dc4bcd670b41ad04ead351c9ae01815`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
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
    save_strategy, get_all_strategies_db, get_strategy_db,
    delete_strategy_db, log_event_db,
)

log = logging.getLogger("jinni.strategy")

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "strategies"
)

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(STRATEGY_DIR, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    return safe or "unnamed_strategy"


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _extract_strategy_class(source: str) -> Optional[dict]:
    """Parse source to find a class extending BaseStrategy."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
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
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant):
                                info[target.id] = item.value.value
                return info
    return None


# =============================================================================
# Public API
# =============================================================================

def upload_strategy(filename: str, source_code: str) -> dict:
    """Upload and persist a strategy file."""
    _ensure_dir()

    info = _extract_strategy_class(source_code)
    if info is None:
        return {
            "ok": False,
            "error": "No class extending BaseStrategy found. Check your code.",
        }

    strategy_id = info.get("strategy_id", "")
    if not strategy_id:
        strategy_id = info["class_name"].lower()

    class_name = info["class_name"]
    name = info.get("name", class_name)
    description = info.get("description", "")
    version = info.get("version", "1.0")
    min_lookback = info.get("min_lookback", 0)

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
        "parameters": {},
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
        result.append({
            "strategy_id": s["strategy_id"],
            "filename": s.get("filename", ""),
            "class_name": s.get("class_name", ""),
            "name": s.get("name", s["strategy_id"]),
            "description": s.get("description", ""),
            "version": s.get("version", ""),
            "min_lookback": s.get("min_lookback", 0),
            "file_hash": s.get("file_hash", ""),
            "uploaded_at": s.get("uploaded_at", ""),
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
            "parameters": {},
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
        })
        count += 1

    if count > 0:
        log.info(f"Loaded {count} strategies from disk into DB")
```

---

## FILE: `ui/js/main.js`

- Relative path: `ui/js/main.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/main.js`
- Size bytes: `36232`
- SHA256: `9e96f160f271b67d46c989d5b7e2b7808b7b4f519599e3fd1252b66896a053ea`
- Guessed MIME type: `text/javascript`
- Guessed encoding: `unknown`

```javascript
/* main.js
*/

var ApiClient = (function () {
  'use strict';

  function _request(method, path, body) {
    var opts = { method: method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try {
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        });
      }
      return res.json();
    });
  }

  function _upload(path, file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try {
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          throw new Error(msg);
        });
      }
      return res.json();
    });
  }

  return {

    getFleetWorkers: function () {
      return _request('GET', '/api/Grid/workers');
    },
    getSystemSummary: function () {
      return _request('GET', '/api/system/summary');
    },
    getHealth: function () {
      return _request('GET', '/api/health');
    },


    getStrategies: function () {
      return _request('GET', '/api/grid/strategies');
    },
    getStrategy: function (id) {
      return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id));
    },
    uploadStrategy: function (file) {
      return _upload('/api/grid/strategies/upload', file);
    },
    validateStrategy: function (id) {
      return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate');
    },


    createDeployment: function (cfg) {
      return _request('POST', '/api/grid/deployments', cfg);
    },
    getDeployments: function () {
      return _request('GET', '/api/grid/deployments');
    },
    getDeployment: function (id) {
      return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id));
    },
    stopDeployment: function (id) {
      return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop');
    }
  };
})();


var DeploymentConfig = (function () {
  'use strict';

  var runtimeDefaults = {
    symbol: 'EURUSD',
    lot_size: 0.01,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
    bar_size_points: 100,
    max_bars_memory: 500
  };

  var symbolOptions = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
    'USDCHF', 'NZDUSD', 'XAUUSD', 'BTCUSD', 'USTEC',
    'SPX500', 'DOW30', 'FTSE100'
  ];

  var tickLookbackUnits = ['minutes', 'hours', 'days'];

  return {
    runtimeDefaults: runtimeDefaults,
    symbolOptions: symbolOptions,
    tickLookbackUnits: tickLookbackUnits
  };
})();


var ModalManager = (function () {
  'use strict';

  var _overlay = null;

  function show(options) {
    hide();

    var title = options.title || 'Confirm';
    var bodyHtml = options.bodyHtml || '';
    var confirmText = options.confirmText || 'Confirm';
    var cancelText = options.cancelText || 'Cancel';
    var type = options.type || 'default';
    var onConfirm = options.onConfirm || function () {};

    var confirmClass = type === 'danger' ? 'wd-btn wd-btn-primary' : 'wd-btn wd-btn-primary';
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';

    _overlay = document.createElement('div');
    _overlay.className = 'modal-overlay';
    _overlay.innerHTML =
      '<div class="modal-card">' +
        '<div class="modal-header">' +
          '<span class="modal-title">' + title + '</span>' +
          '<button class="modal-close" id="modal-close">&times;</button>' +
        '</div>' +
        '<div class="modal-body">' + bodyHtml + '</div>' +
        '<div class="modal-footer">' +
          '<button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button>' +
          '<button class="' + confirmClass + '" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(_overlay);

    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () {
      onConfirm();
      hide();
    });

    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) hide();
    });

    var escHandler = function (e) {
      if (e.key === 'Escape') {
        hide();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  function hide() {
    if (_overlay && _overlay.parentNode) {
      _overlay.parentNode.removeChild(_overlay);
    }
    _overlay = null;
  }

  return {
    show: show,
    hide: hide
  };
})();


var ToastManager = (function () {
  'use strict';

  var iconMap = {
    success: 'fa-circle-check',
    info: 'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error: 'fa-circle-xmark'
  };

  function _getContainer() {
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = _getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML =
      '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i>' +
      '<span>' + message + '</span>' +
      '<button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';

    container.appendChild(toast);

    var dismiss = toast.querySelector('.toast-dismiss');
    dismiss.addEventListener('click', function () {
      _remove(toast);
    });

    setTimeout(function () {
      _remove(toast);
    }, duration);
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;

    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';

    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  return {
    show: show
  };
})();


var ThemeManager = (function () {
  'use strict';

  var STORAGE_KEY = 'jinni-Grid-theme';
  var currentTheme = 'dark';

  function init() {
    var saved = localStorage.getItem(STORAGE_KEY);
    currentTheme = saved === 'light' ? 'light' : 'dark';
    applyTheme();
    updateToggleButton();

    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggle);
  }

  function toggle() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, currentTheme);
    applyTheme();
    updateToggleButton();

    if (typeof DashboardRenderer !== 'undefined' && DashboardRenderer.onThemeChange) {
      DashboardRenderer.onThemeChange();
    }
  }

  function applyTheme() {
    document.body.setAttribute('data-theme', currentTheme);
  }

  function updateToggleButton() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;

    var icon = btn.querySelector('i');
    var label = btn.querySelector('span');

    if (currentTheme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      label.textContent = 'Light Mode';
    } else {
      icon.className = 'fa-solid fa-moon';
      label.textContent = 'Dark Mode';
    }
  }

  function getTheme() {
    return currentTheme;
  }

  return {
    init: init,
    toggle: toggle,
    getTheme: getTheme
  };
})();


var DashboardRenderer = (function () {
  'use strict';

  var _fleetInterval = null;
  var _kpiInterval = null;
  var _lastFleetWorkers = [];

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return val;
  }

  function kpiCard(icon, label, value, sentiment) {
    var valueClass = '';
    if (sentiment === 'positive') valueClass = ' positive';
    else if (sentiment === 'negative') valueClass = ' negative';

    return '<div class="portfolio-card">' +
      '<div class="card-icon ' + sentiment + '"><i class="fa-solid ' + icon + '"></i></div>' +
      '<div class="card-info"><div class="card-value' + valueClass + '">' + value + '</div>' +
      '<div class="card-label">' + label + '</div></div></div>';
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _fetchKPIs() {
    var el = document.getElementById('dashboard-kpi-content');
    if (!el) return;

    Promise.all([
      ApiClient.getStrategies().catch(function () {
        return { strategies: [] };
      }),
      ApiClient.getDeployments().catch(function () {
        return { deployments: [] };
      }),
      ApiClient.getSystemSummary().catch(function () {
        return {};
      })
    ]).then(function (results) {
      var strats = results[0].strategies || [];
      var deps = results[1].deployments || [];
      var sys = results[2];

      var registeredCount = strats.length;
      var activeDeployments = deps.filter(function (d) {
        return [
          'queued',
          'sent_to_worker',
          'acknowledged_by_worker',
          'loading_strategy',
          'fetching_ticks',
          'generating_initial_bars',
          'warming_up',
          'running'
        ].indexOf(d.state) !== -1;
      }).length;

      var runningCount = deps.filter(function (d) {
        return d.state === 'running';
      }).length;

      var failedCount = deps.filter(function (d) {
        return d.state === 'failed';
      }).length;

      var onlineWorkers = sys.online_nodes || 0;
      var totalWorkers = sys.total_nodes || 0;

      var html = '<div class="portfolio-grid">';
      html += kpiCard('fa-crosshairs', 'Registered Strategies', String(registeredCount), 'neutral');
      html += kpiCard('fa-rocket', 'Active Deployments', String(activeDeployments), activeDeployments > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-play', 'Running Runners', String(runningCount), runningCount > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-triangle-exclamation', 'Failed Deployments', String(failedCount), failedCount > 0 ? 'negative' : 'neutral');
      html += kpiCard('fa-server', 'Online Workers', onlineWorkers + ' / ' + totalWorkers, onlineWorkers > 0 ? 'positive' : 'warning');
      html += '</div>';

      el.innerHTML = html;
    });
  }

  function _fetchDashboardFleet() {
    var el = document.getElementById('dashboard-fleet-content');
    if (!el) return;

    ApiClient.getFleetWorkers()
      .then(function (data) {
        var s = data.summary || {};
        var workers = data.workers || [];

        _lastFleetWorkers = workers;

        var html = '<div class="fleet-summary">';
        html += fleetBadge(s.total_workers || 0, 'Total', 'total');
        html += fleetBadge(s.online_workers || 0, 'Online', 'online');
        html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
        html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
        html += fleetBadge(s.error_workers || 0, 'Error', 'error');
        html += '</div>';

        if (workers.length > 0) {
          html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
          html += '<thead><tr><th>Worker</th><th>State</th><th>Host</th><th>Strategy</th><th>Heartbeat</th></tr></thead><tbody>';

          workers.forEach(function (w) {
            var name = w.worker_name || w.worker_id;
            var state = w.state || 'unknown';
            var strats = w.active_strategies && w.active_strategies.length > 0
              ? w.active_strategies.join(', ')
              : '<span class="value-null">—</span>';

            html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')">';
            html += '<td class="mono">' + name + '</td>';
            html += '<td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td>';
            html += '<td class="mono">' + _nullVal(w.host) + '</td>';
            html += '<td class="mono">' + strats + '</td>';
            html += '<td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td>';
            html += '</tr>';
          });

          html += '</tbody></table></div>';
        } else {
          html += '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
            '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
            'No workers connected yet — start a worker agent to see fleet data.</div>';
        }

        html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">' +
          'View Fleet <i class="fa-solid fa-arrow-right"></i></span>';

        el.innerHTML = html;
      })
      .catch(function () {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
          '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
          'Could not load fleet data from backend.</div>';
      });
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastFleetWorkers.length; i++) {
      if (_lastFleetWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastFleetWorkers[i]);
        return;
      }
    }
  }

  function _fetchDeployments() {
    var el = document.getElementById('dashboard-deploy-content');
    if (!el) return;

    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [];

      if (deps.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
          '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
          'No deployments yet. Deploy a strategy from the Worker Detail page.</div>';
        return;
      }

      deps = deps.slice().reverse();

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
      html += '<thead><tr><th>Deployment</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th><th>Updated</th></tr></thead><tbody>';

      deps.forEach(function (d) {
        var stateClass = _deployStateClass(d.state);
        var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '—';

        html += '<tr>';
        html += '<td class="mono">' + d.deployment_id + '</td>';
        html += '<td class="mono">' + d.strategy_id + '</td>';
        html += '<td class="mono">' + d.worker_id + '</td>';
        html += '<td class="mono">' + d.symbol + '</td>';
        html += '<td><span class="state-pill ' + stateClass + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span></td>';
        html += '<td class="mono">' + updated + '</td>';
        html += '</tr>';

        if (d.last_error) {
          html += '<tr><td colspan="6" style="color:var(--danger);font-size:11px;padding:4px 12px;">' +
            '<i class="fa-solid fa-circle-xmark" style="margin-right:4px;"></i>' + d.last_error + '</td></tr>';
        }
      });

      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function () {
      el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
        '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
        'Could not load deployment data.</div>';
    });
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';

    if (
      state.indexOf('loading') !== -1 ||
      state.indexOf('fetching') !== -1 ||
      state.indexOf('generating') !== -1 ||
      state.indexOf('warming') !== -1
    ) {
      return 'warning';
    }

    if (
      state === 'queued' ||
      state.indexOf('sent') !== -1 ||
      state.indexOf('acknowledged') !== -1
    ) {
      return 'stale';
    }

    return 'unknown';
  }

  function render() {
    var html = '<div class="dashboard">';

    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System KPIs</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-kpi-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-fleet-content" class="dashboard-fleet-section">';
    html += '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading fleet data…</p></div>';
    html += '</div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-deploy-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchKPIs();
    _fetchDashboardFleet();
    _fetchDeployments();

    _fleetInterval = setInterval(function () {
      _fetchDashboardFleet();
      _fetchDeployments();
    }, 10000);

    _kpiInterval = setInterval(_fetchKPIs, 15000);
  }

  function destroy() {
    if (_fleetInterval) {
      clearInterval(_fleetInterval);
      _fleetInterval = null;
    }

    if (_kpiInterval) {
      clearInterval(_kpiInterval);
      _kpiInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _openWorker: _openWorker
  };
})();


var FleetRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _lastFetchTime = null;
  var _lastWorkers = [];
  var REFRESH_MS = 5000;

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return String(val);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">—</span>';

    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _infoRow(label, value) {
    return '<div class="node-info-row"><span class="node-info-label">' + label +
      '</span><span class="node-info-value">' + value + '</span></div>';
  }

  function renderNodeCard(w) {
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;

    var strategies = w.active_strategies && w.active_strategies.length > 0
      ? w.active_strategies.join(', ')
      : null;

    var errorsStr = w.errors && w.errors.length > 0
      ? w.errors.join(', ')
      : null;

    var pnlVal = _formatPnl(w.floating_pnl);
    var pnlClass = '';

    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlClass = w.floating_pnl >= 0
        ? ' style="color:var(--success)"'
        : ' style="color:var(--danger)"';
    }

    return (
      '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
        '<div class="node-card-top ' + state + '"></div>' +
        '<div class="node-card-header">' +
          '<div class="node-name-group">' +
            '<span class="node-status-dot ' + state + '"></span>' +
            '<span class="node-name">' + name + '</span>' +
          '</div>' +
          '<span class="node-status-badge ' + state + '">' + _stateLabel(state) + '</span>' +
        '</div>' +
        '<div class="node-card-body">' +
          _infoRow('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
          _infoRow('Host', _nullVal(w.host)) +
          _infoRow('MT5', (w.mt5_state === 'connected' ? '<span style="color:var(--success);">Connected</span>' : _nullVal(w.mt5_state, 'Not Connected'))) +
          _infoRow('Broker', _nullVal(w.broker)) +
          _infoRow('Account', _nullVal(w.account_id)) +
          _infoRow('Strategies', _nullVal(strategies, 'No active strategy')) +
          _infoRow('Positions', '<span style="color:var(--accent);">' + String(w.open_positions_count || 0) + '</span>') +
          _infoRow('Float PnL', '<span' + pnlClass + '>' + pnlVal + '</span>') +
          _infoRow('Pipeline', '<span class="mono" style="font-size:10px;">' + (w.total_ticks || 0) + ' ticks / ' + (w.total_bars || 0) + ' bars / ' + (w.signal_count || 0) + ' sig</span>') +
          _infoRow('Price', (w.current_price ? '<span class="mono">' + Number(w.current_price).toFixed(2) + '</span>' : '<span class="value-null">\u2014</span>')) +
          _infoRow('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
          _infoRow('Errors', _nullVal(errorsStr, 'None')) +
          '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy Strategy</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderContent(data) {
    var headerEl = document.getElementById('fleet-page-header');
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    var workers = data.workers || [];
    var s = data.summary || {};

    _lastWorkers = workers;

    if (headerEl) {
      _lastFetchTime = new Date();

      var timeStr = _lastFetchTime.toLocaleTimeString('en-GB', {
        hour12: false
      });

      headerEl.style.display = 'flex';

      var metaEl = headerEl.querySelector('.last-synced');
      if (metaEl) metaEl.textContent = 'Synced: ' + timeStr;
    }

    if (workers.length === 0) {
      contentEl.innerHTML =
        '<div class="empty-state">' +
          '<i class="fa-solid fa-server"></i>' +
          '<h3>No Worker VMs Connected</h3>' +
          '<p>Start a worker agent and send heartbeat to this Mother Server to see workers here.</p>' +
          '<p>Endpoint: <code>POST /api/grid/workers/heartbeat</code></p>' +
        '</div>';
      return;
    }

    var html = '';
    html += '<div class="fleet-summary">';
    html += fleetBadge(s.total_workers || 0, 'Total', 'total');
    html += fleetBadge(s.online_workers || 0, 'Online', 'online');
    html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
    html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
    html += fleetBadge(s.error_workers || 0, 'Error', 'error');
    html += '</div>';

    html += '<div class="fleet-grid">';
    workers.forEach(function (w) {
      html += renderNodeCard(w);
    });
    html += '</div>';

    contentEl.innerHTML = html;
  }

  function _renderError() {
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    contentEl.innerHTML =
      '<div class="error-state">' +
        '<i class="fa-solid fa-triangle-exclamation"></i>' +
        '<h3>Failed to Load Fleet Data</h3>' +
        '<p>Could not connect to the Mother Server API. Check that the backend is running.</p>' +
        '<button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button>' +
      '</div>';
  }

  function _fetchFleetData() {
    ApiClient.getFleetWorkers().then(_renderContent).catch(_renderError);
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastWorkers.length; i++) {
      if (_lastWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastWorkers[i]);
        return;
      }
    }
  }

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header" id="fleet-page-header" style="display:none;">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span>' +
          '<div class="fleet-page-meta">' +
            '<div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div>' +
            '<span class="last-synced">Synced: --:--:--</span>' +
          '</div>' +
        '</div>' +
        '<div id="fleet-content">' +
          '<div class="loading-state"><div class="spinner"></div><p>Loading fleet data…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchFleetData();
    _refreshInterval = setInterval(_fetchFleetData, REFRESH_MS);
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetchFleetData,
    _openWorker: _openWorker
  };
})();


var StrategiesRenderer = (function () {
  'use strict';

  var _refreshInterval = null;

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span>' +
          '<div class="fleet-page-meta">' +
            '<button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>' +
          '</div>' +
        '</div>' +

        '<div class="wd-panel">' +
          '<div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div>' +
          '<div class="wd-panel-body">' +
            '<div class="wd-file-upload" id="strat-upload-area">' +
              '<input type="file" id="strat-file-input" accept=".py" style="display:none" />' +
              '<i class="fa-solid fa-file-code"></i>' +
              '<h4>Upload Strategy File</h4>' +
              '<p>.py files extending BaseStrategy</p>' +
              '<div id="strat-upload-status"></div>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div id="strat-list-content">' +
          '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading strategies…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _attachEvents();
    _fetch();

    _refreshInterval = setInterval(_fetch, 10000);
  }

  function _attachEvents() {
    document.getElementById('strat-refresh').addEventListener('click', _fetch);

    var area = document.getElementById('strat-upload-area');
    var input = document.getElementById('strat-file-input');

    area.addEventListener('click', function () {
      input.click();
    });

    input.addEventListener('change', function () {
      if (!input.files || !input.files[0]) return;

      var file = input.files[0];

      if (!file.name.endsWith('.py')) {
        ToastManager.show('Only .py files accepted.', 'error');
        return;
      }

      _upload(file);
    });
  }

  function _upload(file) {
    var el = document.getElementById('strat-upload-status');

    el.innerHTML =
      '<div class="wd-file-status" style="color:var(--accent);">' +
      '<i class="fa-solid fa-spinner fa-spin"></i> Uploading &amp; validating…</div>';

    ApiClient.uploadStrategy(file).then(function (data) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--success);">' +
        '<i class="fa-solid fa-circle-check"></i> Registered: ' +
        (data.strategy_name || data.strategy_id) +
        '</div>';

      ToastManager.show('Strategy registered: ' + (data.strategy_name || data.strategy_id), 'success');
      _fetch();
    }).catch(function (err) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--danger);">' +
        '<i class="fa-solid fa-circle-xmark"></i> ' +
        err.message +
        '</div>';

      ToastManager.show('Upload failed: ' + err.message, 'error');
    });
  }

  function _fetch() {
    var el = document.getElementById('strat-list-content');
    if (!el) return;

    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];

      if (list.length === 0) {
        el.innerHTML =
          '<div class="empty-state" style="min-height:200px;">' +
            '<i class="fa-solid fa-crosshairs"></i>' +
            '<h3>No Strategies Registered</h3>' +
            '<p>Upload a .py strategy file extending BaseStrategy to get started.</p>' +
          '</div>';
        return;
      }

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">' +
        '<thead><tr><th>Strategy ID</th><th>Name</th><th>Version</th><th>Params</th><th>Status</th><th>Uploaded</th></tr></thead><tbody>';

      list.forEach(function (s) {
        var statusClass = s.validation_status === 'validated' ? 'online' : 'error';
        var statusLabel = s.validation_status === 'validated'
          ? 'Validated'
          : (s.validation_status || 'Unknown');

        var uploaded = s.uploaded_at
          ? s.uploaded_at.replace('T', ' ').substring(0, 19)
          : '—';

        html += '<tr>' +
          '<td class="mono">' + s.strategy_id + '</td>' +
          '<td>' + (s.strategy_name || s.strategy_id) + '</td>' +
          '<td class="mono">' + (s.version || '—') + '</td>' +
          '<td class="mono">' + (s.parameter_count || 0) + '</td>' +
          '<td><span class="state-pill ' + statusClass + '">' + statusLabel.toUpperCase() + '</span></td>' +
          '<td class="mono">' + uploaded + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';

      list.forEach(function (s) {
        if (s.description || s.error) {
          html += '<div style="margin-top:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;font-size:11.5px;">';
          html += '<strong class="mono" style="color:var(--accent);">' + s.strategy_id + '</strong>';

          if (s.description) {
            html += '<span style="color:var(--text-secondary);margin-left:8px;">' + s.description + '</span>';
          }

          if (s.error) {
            html += '<span style="color:var(--danger);margin-left:8px;">Error: ' + s.error + '</span>';
          }

          html += '</div>';
        }
      });

      el.innerHTML = html;
    }).catch(function (err) {
      el.innerHTML =
        '<div class="error-state" style="min-height:200px;">' +
          '<i class="fa-solid fa-triangle-exclamation"></i>' +
          '<h3>Failed to Load Strategies</h3>' +
          '<p>' + err.message + '</p>' +
          '<button class="retry-btn" onclick="StrategiesRenderer._retry()">Retry</button>' +
        '</div>';
    });
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetch
  };
})();


var App = (function () {
  'use strict';

  var currentPage = 'dashboard';
  var _selectedWorker = null;

  var pageIcons = {
    dashboard: 'fa-grip',
    fleet: 'fa-server',
    portfolio: 'fa-chart-line',
    strategies: 'fa-crosshairs',
    logs: 'fa-scroll',
    settings: 'fa-gear'
  };

  var pageDescriptions = {
    portfolio: 'Portfolio analytics will be available when trade execution is implemented.',
    logs: 'Centralized log aggregation, real-time streaming, and advanced search across all fleet nodes.',
    settings: 'System configuration, user preferences, notification settings, and connection management.'
  };

  function init() {
    ThemeManager.init();
    setupNavigation();
    startClock();
    navigateTo('dashboard');
  }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        navigateTo(item.getAttribute('data-page'));
      });
    });
  }

  function navigateTo(page) {
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();

    currentPage = page;

    var navPage = page === 'workerDetail' ? 'fleet' : page;

    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    var titleMap = {
      workerDetail: 'Worker Detail'
    };

    var title = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    document.getElementById('topbar-title').textContent = title;

    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      WorkerDetailRenderer.render(_selectedWorker);
    } else if (page === 'strategies') {
      StrategiesRenderer.render();
    } else {
      renderPlaceholder(page);
    }
  }

  function navigateToWorkerDetail(workerData) {
    _selectedWorker = workerData;
    navigateTo('workerDetail');
  }

  function renderPlaceholder(page) {
    var icon = pageIcons[page] || 'fa-circle-question';
    var title = page.charAt(0).toUpperCase() + page.slice(1);
    var desc = pageDescriptions[page] || 'This section is under development.';

    document.getElementById('main-content').innerHTML =
      '<div class="placeholder-page"><i class="fa-solid ' + icon + '"></i>' +
      '<h2>' + title + '</h2><p>' + desc + '</p></div>';
  }

  function startClock() {
    function update() {
      var now = new Date();

      document.getElementById('topbar-clock').textContent =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    }

    update();
    setInterval(update, 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    navigateTo: navigateTo,
    navigateToWorkerDetail: navigateToWorkerDetail
  };
})();
```

---

## FILE: `worker/config.yaml`

- Relative path: `worker/config.yaml`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/config.yaml`
- Size bytes: `176`
- SHA256: `b6a616e396af64890e55c695fd7cce35828353dfea90fdd1179b08d4642e63b9`
- Guessed MIME type: `application/yaml`
- Guessed encoding: `unknown`

```yaml
worker:
  worker_id: "vm-worker-01"
  worker_name: "Worker 01"

mother_server:
  url: "http://192.168.3.232:5100"

heartbeat:
  interval_seconds: 10

agent:
  version: "0.1.0"
```

---

## FILE: `worker/event_log.py`

- Relative path: `worker/event_log.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/event_log.py`
- Size bytes: `3457`
- SHA256: `df8ec517a77b4d6762a2911bb760f6b2873b1f23a3029a0ad1eac449f9e7bf3d`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Worker-Side Structured Event Logger
worker/event_log.py

Writes structured events to a local SQLite DB on the worker machine.
Events are also forwarded to Mother via heartbeat/status reports.

Categories: SYSTEM, EXECUTION, STRATEGY, PIPELINE, ERROR
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class WorkerEventLog:
    """Per-worker persistent event log."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self._lock = threading.Lock()
        os.makedirs(DATA_DIR, exist_ok=True)
        self._db_path = os.path.join(DATA_DIR, f"events_{worker_id}.db")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=3000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                deployment_id TEXT,
                strategy_id TEXT,
                symbol TEXT,
                message TEXT,
                data_json TEXT,
                level TEXT DEFAULT 'INFO'
            );
            CREATE INDEX IF NOT EXISTS idx_wevents_ts ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_wevents_cat ON events(category);
        """)
        conn.commit()
        conn.close()

    def log(self, category: str, event_type: str, message: str,
            deployment_id: str = None, strategy_id: str = None,
            symbol: str = None, data: dict = None, level: str = "INFO"):
        """Write a structured event."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    INSERT INTO events (timestamp, category, event_type,
                        deployment_id, strategy_id, symbol, message,
                        data_json, level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now, category, event_type, deployment_id, strategy_id,
                    symbol, message,
                    json.dumps(data, default=str) if data else None, level,
                ))
                conn.commit()
            finally:
                conn.close()

        # Also print for console visibility
        print(f"[EVENT:{category}] {event_type} | {message}")

    def get_recent(self, limit: int = 100, category: str = None) -> list:
        conn = self._get_conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM events WHERE category=? ORDER BY id DESC LIMIT ?",
                    (category, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
```

---

## FILE: `worker/indicators.py`

- Relative path: `worker/indicators.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/indicators.py`
- Size bytes: `7085`
- SHA256: `91b2f5f74c0354d5f48ec8887a79fa64817afc12718014bf054de243b480eac7`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Indicator Engine
worker/indicators.py

Ported from JINNI ZERO backtester shared.py / engine_core.py.
Supports: SMA, EMA, WMA, HMA precomputation on range bar series.
Populates ctx.indicators (current bar values) and ctx.ind_series (full series).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# =============================================================================
# Core MA Functions (matching JINNI ZERO backtester exactly)
# =============================================================================

def precompute_sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def precompute_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    # Seed with SMA
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    k = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        val = values[i] * k + prev * (1 - k)
        result[i] = val
        prev = val
    return result


def precompute_wma(values: List[float], period: int) -> List[Optional[float]]:
    """Weighted Moving Average — full series."""
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result
    denom = period * (period + 1) / 2.0
    for i in range(period - 1, n):
        w_sum = 0.0
        for j in range(period):
            w_sum += values[i - period + 1 + j] * (j + 1)
        result[i] = w_sum / denom
    return result


def precompute_hma(values: List[float], period: int) -> List[Optional[float]]:
    """
    Hull Moving Average — full series.
    HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
    """
    n = len(values)
    result = [None] * n
    if period <= 0 or n < period:
        return result

    half = max(int(period / 2), 1)
    sqrt_p = max(int(math.sqrt(period)), 1)

    wma_half = precompute_wma(values, half)
    wma_full = precompute_wma(values, period)

    # Build diff series: 2*WMA(half) - WMA(full)
    diff = []
    diff_start = None
    for i in range(n):
        if wma_half[i] is not None and wma_full[i] is not None:
            diff.append(2.0 * wma_half[i] - wma_full[i])
            if diff_start is None:
                diff_start = i
        else:
            diff.append(0.0)

    if diff_start is None:
        return result

    # Only use valid portion of diff
    valid_diff = diff[diff_start:]
    hma_of_diff = precompute_wma(valid_diff, sqrt_p)

    for i, val in enumerate(hma_of_diff):
        target_idx = diff_start + i
        if target_idx < n:
            result[target_idx] = val

    return result


def precompute_ma(values: List[float], kind: str, period: int) -> List[Optional[float]]:
    """
    Dispatch to the correct MA precompute function.
    Matches JINNI ZERO backtester shared.py exactly.
    """
    kind_upper = kind.upper()
    if kind_upper == "SMA":
        return precompute_sma(values, period)
    elif kind_upper == "EMA":
        return precompute_ema(values, period)
    elif kind_upper == "WMA":
        return precompute_wma(values, period)
    elif kind_upper == "HMA":
        return precompute_hma(values, period)
    else:
        print(f"[INDICATORS] WARNING: Unknown MA kind '{kind}', falling back to SMA")
        return precompute_sma(values, period)


# =============================================================================
# Source Extraction
# =============================================================================

def _source_values(bars: list, source: str) -> List[float]:
    """Extract price series from bars by source name."""
    if source == "open":
        return [float(b.get("open", 0)) for b in bars]
    elif source == "high":
        return [float(b.get("high", 0)) for b in bars]
    elif source == "low":
        return [float(b.get("low", 0)) for b in bars]
    else:
        return [float(b.get("close", 0)) for b in bars]


def precompute_indicator_series(bars: list, spec: dict) -> List[Optional[float]]:
    """
    Precompute a full indicator series from bars + spec.
    Spec format (from strategy.build_indicators()):
        {"key": "hma_200", "kind": "HMA", "period": 200, "source": "close"}
    """
    kind = spec.get("kind", "SMA").upper()
    source = spec.get("source", "close")
    period = int(spec.get("period", 14))
    values = _source_values(bars, source)
    return precompute_ma(values, kind, period)


# =============================================================================
# Indicator Engine (live — recomputes on every new bar)
# =============================================================================

class IndicatorEngine:
    """
    Manages indicator computation for live trading.

    On each new bar:
      1. Recomputes full series for all declared indicators
      2. Updates ctx.indicators with current-bar values
      3. Updates ctx.ind_series with full series (for strategy lookback)

    This matches backtester behavior where indicators are precomputed
    over the full bar array. For live, we recompute on the growing
    bar deque — slightly less efficient but guarantees identical values.
    """

    def __init__(self, indicator_defs: List[Dict[str, Any]]):
        self._defs = indicator_defs
        self._warned: set = set()

        if self._defs:
            keys = [d["key"] for d in self._defs]
            print(f"[INDICATORS] Registered {len(self._defs)} indicators: {keys}")
        else:
            print("[INDICATORS] No indicators requested by strategy.")

    def update(self, bars: list, ctx) -> None:
        """Recompute all indicators from current bar list and update ctx."""
        for defn in self._defs:
            key = defn["key"]
            kind = defn.get("kind", "SMA").upper()
            source = defn.get("source", "close")
            period = int(defn.get("period", 14))

            values = _source_values(bars, source)
            series = precompute_ma(values, kind, period)

            # Store full series
            ctx._ind_series[key] = series

            # Store current value (last bar)
            if series and len(series) > 0:
                ctx._indicators[key] = series[-1]
            else:
                ctx._indicators[key] = None

    def get_series_at(self, indicator_store: dict, key: str, index: int) -> Optional[float]:
        """Get indicator value at a specific bar index."""
        series = indicator_store.get(key)
        if series is None or index < 0 or index >= len(series):
            return None
        return series[index]
```

---

## FILE: `worker/README.md`

- Relative path: `worker/README.md`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/README.md`
- Size bytes: `1215`
- SHA256: `28ead786e4eb10d807621099ef8cec7fec39d645e950a3b2dd1180cea90184c1`
- Guessed MIME type: `text/markdown`
- Guessed encoding: `unknown`

````markdown
# JINNI Grid — Worker Agent

## What It Does

Sends periodic heartbeat POST requests to the JINNI Grid Mother Server.
The Mother Server uses these heartbeats to track worker status in the Fleet dashboard.

## Prerequisites

- Python 3.10+
- `requests` and `pyyaml` packages

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Edit `config.yaml`:
   - Set `worker_id` to a unique ID for this worker
   - Set `worker_name` to a human-readable name
   - Set `mother_server.url` to your Mother Server's IP and port
   - Adjust `heartbeat.interval_seconds` if needed

3. Run the agent:
   ```bash
   python worker_agent.py
   ```

## Config Reference

```yaml
worker:
  worker_id: "vm-worker-01"      # Unique worker identifier
  worker_name: "Worker 01"       # Display name

mother_server:
  url: "http://192.168.1.100:5100"  # Mother Server address

heartbeat:
  interval_seconds: 5            # Seconds between heartbeats

agent:
  version: "0.1.0"               # Agent version reported to Mother Server
```

## What It Does NOT Do

- No MT5 connectivity
- No trading execution
- No strategy deployment
- No broker/account detection

Those features come in future phases.
````

---

## FILE: `worker/requirements.txt`

- Relative path: `worker/requirements.txt`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/requirements.txt`
- Size bytes: `48`
- SHA256: `7a58cbea9db5d6fbf9c1ea4bc53a1363984cef617cc862e83bc855137186f9fc`
- Guessed MIME type: `text/plain`
- Guessed encoding: `unknown`

```text
pyyaml>=6.0
requests>=2.31.0
MetaTrader5>=5.0.45
```

---

## FILE: `worker/strategyWorker.py`

- Relative path: `worker/strategyWorker.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/worker/strategyWorker.py`
- Size bytes: `46091`
- SHA256: `106d42794021f754d383e7e6e3042990c4a3456cf55815b3afca1f965165186c`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Combined Worker Runtime
worker/strategyWorker.py

Uses:
  worker/indicators.py  — HMA/WMA/SMA/EMA precompute + IndicatorEngine
  worker/execution.py   — ExecutionLogger, MT5Executor, signal validation,
                           SL/TP computation, trade records, PositionState
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import traceback
import types
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from worker.indicators import IndicatorEngine, precompute_indicator_series
from worker.execution import (
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, VALID_SIGNALS,
    PositionState, ExecutionLogger, MT5Executor,
    validate_signal, compute_sl, compute_tp, build_trade_record,
)


# =============================================================================
# Strategy Base Class
# =============================================================================

class BaseStrategy(ABC):
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    min_lookback: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id, "name": self.name or self.strategy_id,
            "description": self.description or "", "version": self.version,
            "min_lookback": self.min_lookback,
            "parameters": self.get_parameter_schema(),
        }

    def get_parameter_schema(self) -> Dict[str, Any]:
        return getattr(self, "parameters", {})

    def get_default_parameters(self) -> Dict[str, Any]:
        schema = self.get_parameter_schema()
        defaults = {}
        for key, spec in schema.items():
            if isinstance(spec, dict) and "default" in spec:
                defaults[key] = spec["default"]
        return defaults

    def validate_parameters(self, raw_params: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(self.get_default_parameters())
        for key, value in (raw_params or {}).items():
            params[key] = value
        return params

    def build_indicators(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def on_init(self, ctx: Any) -> None:
        pass

    def on_end(self, ctx: Any) -> None:
        pass

    @abstractmethod
    def on_bar(self, ctx: Any) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Strategy must implement on_bar()")


# =============================================================================
# Strategy Context
# =============================================================================

class StrategyContext:
    def __init__(self, bars: list, params: dict,
                 position: Optional[PositionState] = None):
        self._bars = bars
        self._params = params
        self._position = position or PositionState()
        self._index: int = 0
        self._trades: list = []
        self._equity: float = 0.0
        self._balance: float = 0.0
        self._indicators: dict = {}
        self._ind_series: dict = {}
        self.state: dict = {}

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, val: int):
        self._index = val

    @property
    def bar(self) -> dict:
        if 0 <= self._index < len(self._bars):
            return self._bars[self._index]
        return {}

    @property
    def bars(self) -> list:
        return self._bars

    @property
    def indicators(self) -> dict:
        return self._indicators

    @property
    def ind_series(self) -> dict:
        return self._ind_series

    @property
    def position(self) -> PositionState:
        return self._position

    @position.setter
    def position(self, val: PositionState):
        self._position = val

    @property
    def params(self) -> dict:
        return self._params

    @property
    def trades(self) -> list:
        return self._trades

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, val: float):
        self._equity = val

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, val: float):
        self._balance = val


# =============================================================================
# Range Bar Engine
# =============================================================================

def _make_bar(time_: int, open_: float, high_: float, low_: float,
              close_: float, volume_: float) -> dict:
    return {
        "time": int(time_), "open": round(open_, 5), "high": round(high_, 5),
        "low": round(low_, 5), "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    def __init__(self, bar_size_points: float, max_bars: int = 500,
                 on_bar: Optional[Callable[[dict], None]] = None):
        self.range_size = float(bar_size_points)
        self.max_bars = max_bars
        self._on_bar = on_bar
        self.trend = 0
        self.bar: Optional[dict] = None
        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None
        self.total_ticks = 0
        self.total_bars_emitted = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _emit(self, bar_dict: dict) -> None:
        ts = int(bar_dict["time"])
        if self._last_emitted_ts is not None and ts <= self._last_emitted_ts:
            ts = self._last_emitted_ts + 1
        bar_dict["time"] = ts
        self._last_emitted_ts = ts
        self.bars.append(bar_dict)
        self.total_bars_emitted += 1
        if self._on_bar:
            self._on_bar(bar_dict)

    def _start_bar(self, ts: int, price: float, volume: float) -> None:
        self.bar = {"time": ts, "open": price, "high": price,
                    "low": price, "close": price, "volume": volume}

    def process_tick(self, ts: int, price: float, volume: float = 0.0) -> None:
        self.total_ticks += 1
        if self.bar is None:
            self._start_bar(ts, price, volume)
            return
        p, rs = price, self.range_size
        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]
            if self.trend == 0:
                up_t, dn_t = o + rs, o - rs
                if p >= up_t:
                    self.bar["high"] = max(self.bar["high"], up_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": up_t, "high": up_t,
                                "low": up_t, "close": up_t, "volume": 0.0}
                    continue
                if p <= dn_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], dn_t)
                    self.bar["close"] = dn_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": dn_t, "high": dn_t,
                                "low": dn_t, "close": dn_t, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == 1:
                cont_t, rev_t = o + rs, o - (2 * rs)
                if p >= cont_t:
                    self.bar["high"] = max(self.bar["high"], cont_t)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p <= rev_t:
                    ro, rc = o - rs, o - (2 * rs)
                    h_ = max(self.bar["high"], o)
                    l_ = min(self.bar["low"], rc)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = -1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break
            if self.trend == -1:
                cont_t, rev_t = o - rs, o + (2 * rs)
                if p <= cont_t:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_t)
                    self.bar["close"] = cont_t
                    self._emit(_make_bar(self.bar["time"], self.bar["open"],
                               self.bar["high"], self.bar["low"],
                               self.bar["close"], self.bar["volume"]))
                    self.bar = {"time": ts, "open": cont_t, "high": cont_t,
                                "low": cont_t, "close": cont_t, "volume": 0.0}
                    continue
                if p >= rev_t:
                    ro, rc = o + rs, o + (2 * rs)
                    h_ = max(self.bar["high"], rc)
                    l_ = min(self.bar["low"], o)
                    self._emit(_make_bar(self.bar["time"], ro, h_, l_, rc,
                               self.bar["volume"]))
                    self.trend = 1
                    self.bar = {"time": ts, "open": rc, "high": rc,
                                "low": rc, "close": rc, "volume": 0.0}
                    continue
                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

    def reset(self) -> None:
        self.trend = 0
        self.bar = None
        self.bars.clear()
        self._last_emitted_ts = None
        self.total_ticks = 0
        self.total_bars_emitted = 0


# =============================================================================
# MT5 Tick Normalizer + Connector
# =============================================================================

def _tick_field(raw, field: str, default: float = 0.0) -> float:
    try:
        return float(raw[field])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    try:
        return float(getattr(raw, field))
    except (AttributeError, TypeError, ValueError):
        pass
    return default


def normalize_tick(raw) -> Optional[dict]:
    ts_val = _tick_field(raw, "time", -1.0)
    if ts_val < 0:
        return None
    ts = int(ts_val)
    time_msc_val = _tick_field(raw, "time_msc", -1.0)
    time_msc = int(time_msc_val) if time_msc_val >= 0 else ts * 1000
    bid = _tick_field(raw, "bid", 0.0)
    ask = _tick_field(raw, "ask", 0.0)
    last = _tick_field(raw, "last", 0.0)
    volume = _tick_field(raw, "volume", 0.0)
    price = bid if bid > 0 else (last if last > 0 else ask)
    if price <= 0:
        return None
    return {"ts": ts, "time_msc": time_msc, "price": price,
            "bid": bid, "ask": ask, "last": last, "volume": volume}


def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    mt5 = _import_mt5()
    if mt5 is None:
        return False, "MetaTrader5 package not installed."
    if not mt5.initialize():
        return False, f"MT5 initialize() failed: {mt5.last_error()}"
    info = mt5.terminal_info()
    if info is None:
        return False, "MT5 terminal_info() returned None."
    account = mt5.account_info()
    acct_str = f" | account={account.login} broker={account.company}" if account else ""
    print(f"[MT5] Connected: {info.name}{acct_str}")
    return True, "ok"


def shutdown_mt5() -> None:
    mt5 = _import_mt5()
    if mt5:
        mt5.shutdown()


def get_mt5_account_info() -> Optional[dict]:
    mt5 = _import_mt5()
    if mt5 is None:
        return None
    account = mt5.account_info()
    if account is None:
        return None
    terminal = mt5.terminal_info()
    return {
        "login": str(account.login),
        "broker": str(account.company) if account.company else None,
        "server": str(account.server) if account.server else None,
        "balance": float(account.balance),
        "equity": float(account.equity),
        "terminal": str(terminal.name) if terminal else None,
    }


def fetch_historical_ticks(symbol, lookback_value, lookback_unit):
    mt5 = _import_mt5()
    if mt5 is None:
        return None, "MetaTrader5 package not installed."
    now = datetime.now(timezone.utc)
    if lookback_unit == "minutes":
        from_time = now - timedelta(minutes=lookback_value)
    elif lookback_unit == "hours":
        from_time = now - timedelta(hours=lookback_value)
    elif lookback_unit == "days":
        from_time = now - timedelta(days=lookback_value)
    else:
        return None, f"Invalid lookback_unit: {lookback_unit}"
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return None, f"Symbol '{symbol}' not found in MT5."
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return None, f"Failed to enable symbol '{symbol}' in MT5."
    print(f"[MT5] Fetching ticks: {symbol} from {from_time.isoformat()}")
    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return None, f"No ticks for {symbol}. MT5 error: {mt5.last_error()}"
    result, skipped = [], 0
    for raw_tick in ticks:
        n = normalize_tick(raw_tick)
        if n is None:
            skipped += 1
            continue
        result.append({"ts": n["ts"], "price": n["price"], "volume": n["volume"]})
    if not result:
        return None, f"All {len(ticks)} ticks had no valid price."
    print(f"[MT5] Got {len(result)} ticks for {symbol} (skipped {skipped})")
    return result, "ok"


def stream_live_ticks(symbol, poll_interval=0.05):
    mt5 = _import_mt5()
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")
    cursor_time = datetime.now(timezone.utc)
    last_tick_msc = 0
    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            for raw_tick in ticks:
                n = normalize_tick(raw_tick)
                if n is None:
                    continue
                if n["time_msc"] <= last_tick_msc:
                    continue
                last_tick_msc = n["time_msc"]
                yield {"ts": n["ts"], "price": n["price"], "volume": n["volume"]}
            last_ts = _tick_field(ticks[-1], "time", 0.0)
            if last_ts > 0:
                cursor_time = datetime.fromtimestamp(int(last_ts), tz=timezone.utc)
        time.sleep(poll_interval)


class _MT5ConnectorFacade:
    init_mt5 = staticmethod(init_mt5)
    shutdown_mt5 = staticmethod(shutdown_mt5)
    fetch_historical_ticks = staticmethod(fetch_historical_ticks)
    stream_live_ticks = staticmethod(stream_live_ticks)
    get_mt5_account_info = staticmethod(get_mt5_account_info)


mt5_connector = _MT5ConnectorFacade()


# =============================================================================
# Strategy Loader
# =============================================================================

def load_strategy_from_source(source_code: str, class_name: str,
                              strategy_id: str) -> Tuple[Optional[object], Optional[str]]:
    try:
        _ensure_base_importable()
    except Exception as exc:
        return None, f"Failed to prepare base imports: {exc}"

    module_name = f"jinni_strategy_{strategy_id}"
    try:
        tmp_dir = tempfile.mkdtemp(prefix="jinni_strat_")
        tmp_path = os.path.join(tmp_dir, f"{module_name}.py")
        with open(tmp_path, "w", encoding="utf-8") as file:
            file.write(source_code)
        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        if spec is None or spec.loader is None:
            return None, "Failed to create module spec."
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        klass = getattr(module, class_name, None)
        if klass is None:
            available = [k for k in dir(module) if not k.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"
        instance = klass()
        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."
        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed: {exc}\n{tb}")
        return None, f"{type(exc).__name__}: {exc}"


def _ensure_base_importable():
    current_module = sys.modules[__name__]
    sys.modules["base_strategy"] = current_module
    sys.modules["worker.base_strategy"] = current_module
    if "backend" not in sys.modules:
        bm = types.ModuleType("backend")
        bm.__path__ = []
        sys.modules["backend"] = bm
    if "backend.strategies" not in sys.modules:
        sm = types.ModuleType("backend.strategies")
        sm.__path__ = []
        sys.modules["backend.strategies"] = sm
    sys.modules["backend.strategies.base"] = current_module


# =============================================================================
# Strategy Runner
# =============================================================================

class StrategyRunner:
    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

        self.deployment_id: str = deployment_config["deployment_id"]
        self.strategy_id: str = deployment_config["strategy_id"]
        self.class_name: str = deployment_config.get("strategy_class_name", "")
        self.source_code: str = deployment_config.get("strategy_file_content", "")
        self.symbol: str = deployment_config["symbol"]
        self.tick_lookback_value: int = deployment_config.get("tick_lookback_value", 30)
        self.tick_lookback_unit: str = deployment_config.get("tick_lookback_unit", "minutes")
        self.bar_size_points: float = deployment_config["bar_size_points"]
        self.max_bars: int = deployment_config.get("max_bars_in_memory", 500)
        self.lot_size: float = deployment_config.get("lot_size", 0.01)
        self.strategy_parameters: dict = deployment_config.get("strategy_parameters") or {}

        self._strategy = None
        self._ctx: Optional[StrategyContext] = None
        self._bar_engine: Optional[RangeBarEngine] = None
        self._executor: Optional[MT5Executor] = None
        self._exec_log: Optional[ExecutionLogger] = None
        self._indicator_engine: Optional[IndicatorEngine] = None
        self._runner_state: str = "idle"
        self._last_signal: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._started_at: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bar_index: int = 0

        # MT5 info
        self._mt5_state: Optional[str] = None
        self._mt5_broker: Optional[str] = None
        self._mt5_account_id: Optional[str] = None
        self._mt5_server: Optional[str] = None
        self._mt5_balance: Optional[float] = None
        self._mt5_equity: Optional[float] = None

        # Pipeline counters
        self._total_ticks_ingested: int = 0
        self._total_bars_produced: int = 0
        self._on_bar_call_count: int = 0
        self._signal_count: int = 0
        self._warmup_signal_count: int = 0
        self._last_bar_time: Optional[int] = None
        self._current_price: Optional[float] = None
        self._trade_counter: int = 0

        # Active trade tracking (for MA-cross exit + trade records)
        self._active_trade_meta: Optional[dict] = None

    # ── Diagnostics ─────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        exec_stats = self._exec_log.get_stats() if self._exec_log else {}
        open_count = self._executor.get_open_count() if self._executor else 0
        floating = self._executor.get_floating_pnl() if self._executor else 0.0

        if self._executor and self._executor._mt5:
            try:
                acct = self._executor._mt5.account_info()
                if acct:
                    self._mt5_balance = float(acct.balance)
                    self._mt5_equity = float(acct.equity)
            except Exception:
                pass

        return {
            "runner_state": self._runner_state,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "mt5_state": self._mt5_state,
            "broker": self._mt5_broker,
            "account_id": self._mt5_account_id,
            "mt5_server": self._mt5_server,
            "mt5_balance": self._mt5_balance,
            "mt5_equity": self._mt5_equity,
            "total_ticks": self._total_ticks_ingested,
            "total_bars": self._total_bars_produced,
            "current_bars_in_memory": (
                self._bar_engine.current_bars_count if self._bar_engine else 0
            ),
            "on_bar_calls": self._on_bar_call_count,
            "signal_count": self._signal_count,
            "warmup_signals": self._warmup_signal_count,
            "last_bar_time": self._last_bar_time,
            "current_price": self._current_price,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "open_positions_count": open_count,
            "floating_pnl": floating,
            "trade_count": self._trade_counter,
            **{f"exec_{k}": v for k, v in exec_stats.items()},
        }

    # ── Status Reporting ────────────────────────────────────

    def _report_status(self):
        if not self._status_callback:
            return
        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": getattr(self._strategy, "name", None) if self._strategy else None,
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": self._bar_engine.current_bars_count if self._bar_engine else 0,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for attempt in range(3):
            try:
                self._status_callback(status)
                return
            except Exception as exc:
                print(f"[RUNNER] Status report attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    time.sleep(1.0)

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state
        if error:
            self._last_error = error
        print(f"[RUNNER] {self.deployment_id} -> {state}"
              + (f" (error: {error})" if error else ""))
        self._report_status()

    # ── MT5 Info ────────────────────────────────────────────

    def _capture_mt5_info(self):
        info = mt5_connector.get_mt5_account_info()
        if info:
            self._mt5_state = "connected"
            self._mt5_broker = info.get("broker")
            self._mt5_account_id = info.get("login")
            self._mt5_server = info.get("server")
            self._mt5_balance = info.get("balance")
            self._mt5_equity = info.get("equity")
            print(f"[RUNNER] MT5 info: broker={self._mt5_broker} "
                  f"account={self._mt5_account_id} balance={self._mt5_balance}")
        else:
            self._mt5_state = "connected_no_account"

    # ── Position Refresh ────────────────────────────────────

    def _refresh_position(self):
        if self._executor:
            pos = self._executor.get_position_state()
            if self._active_trade_meta and pos.has_position:
                pos.entry_bar = self._active_trade_meta.get("entry_bar")
            self._ctx.position = pos

    # ── Pipeline Log ────────────────────────────────────────

    def _log_pipeline(self, label: str = ""):
        c = f" [{label}]" if label else ""
        exec_s = self._exec_log.get_stats() if self._exec_log else {}
        pos_n = self._executor.get_open_count() if self._executor else 0
        print(
            f"[PIPELINE]{c} dep={self.deployment_id} | "
            f"ticks={self._total_ticks_ingested} "
            f"bars={self._total_bars_produced} "
            f"on_bar={self._on_bar_call_count} "
            f"signals={self._signal_count} "
            f"buys={exec_s.get('buys_filled', 0)} "
            f"sells={exec_s.get('sells_filled', 0)} "
            f"closes={exec_s.get('closes_filled', 0)} "
            f"ma_exits={exec_s.get('ma_cross_exits', 0)} "
            f"positions={pos_n} "
            f"trades={self._trade_counter} "
            f"price={self._current_price}"
        )

    # ── MA-Cross Exit Check ─────────────────────────────────

    def _check_ma_cross_exit(self, bar: dict) -> bool:
        """
        Check if any engine-level MA cross exit triggers.
        Matches JINNI ZERO backtester _check_exit() MA cross logic.
        Returns True if a position was closed.
        """
        if not self._active_trade_meta:
            return False

        pos = self._ctx.position
        if not pos.has_position:
            return False

        close_price = float(bar.get("close", 0))
        direction = pos.direction

        # Check TP MA cross
        tp_ma_key = self._active_trade_meta.get("engine_tp_ma_key")
        if tp_ma_key:
            tp_ma_val = self._ctx.indicators.get(tp_ma_key)
            if tp_ma_val is not None:
                if direction == "long" and close_price < tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True
                if direction == "short" and close_price > tp_ma_val:
                    self._exec_log.log_ma_cross_exit(tp_ma_key, direction,
                                                     tp_ma_val, close_price)
                    self._close_and_record("MA_TP_EXIT", bar)
                    return True

        # Check SL MA cross
        sl_ma_key = self._active_trade_meta.get("engine_sl_ma_key")
        if sl_ma_key:
            sl_ma_val = self._ctx.indicators.get(sl_ma_key)
            if sl_ma_val is not None:
                if direction == "long" and close_price < sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True
                if direction == "short" and close_price > sl_ma_val:
                    self._exec_log.log_ma_cross_exit(sl_ma_key, direction,
                                                     sl_ma_val, close_price)
                    self._close_and_record("MA_SL_EXIT", bar)
                    return True

        return False

    # ── Close + Record Trade ────────────────────────────────

    def _close_and_record(self, reason: str, bar: dict):
        """Close all positions and write trade record to ctx._trades."""
        pos = self._ctx.position
        if not pos.has_position:
            return

        results = self._executor.close_all_positions()
        self._exec_log.log_close(results, reason=reason)

        # Build trade record
        meta = self._active_trade_meta or {}
        for r in results:
            if r.get("success"):
                self._trade_counter += 1
                record = build_trade_record(
                    trade_id=self._trade_counter,
                    direction=pos.direction or "long",
                    entry_price=pos.entry_price or 0,
                    entry_bar=meta.get("entry_bar", self._bar_index),
                    entry_time=meta.get("entry_time", bar.get("time", 0)),
                    exit_price=r.get("price", 0),
                    exit_bar=self._bar_index,
                    exit_time=bar.get("time", 0),
                    exit_reason=reason,
                    sl=pos.sl,
                    tp=pos.tp,
                    lot_size=pos.size or self.lot_size,
                    ticket=r.get("ticket"),
                    profit=r.get("profit", 0),
                )
                self._ctx._trades.append(record)
                print(f"[TRADE #{self._trade_counter}] {record['direction'].upper()} "
                      f"entry={record['entry_price']} exit={record['exit_price']} "
                      f"reason={reason} profit={record.get('profit', 0):.2f}")

        self._active_trade_meta = None
        self._refresh_position()

    # ── Bar Callback ────────────────────────────────────────

    def _on_new_bar(self, bar: dict):
        self._total_bars_produced += 1
        self._last_bar_time = bar.get("time")

        if self._stop_event.is_set():
            return
        if self._strategy is None or self._ctx is None:
            return

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx.index = len(bars_list) - 1
        self._bar_index = self._ctx.index

        # Update indicators
        if self._indicator_engine:
            self._indicator_engine.update(bars_list, self._ctx)

        # Refresh real position from MT5
        self._refresh_position()

        # Check engine-level MA cross exits BEFORE calling strategy
        if self._ctx.position.has_position:
            if self._check_ma_cross_exit(bar):
                # Position was closed by MA cross — strategy will see flat
                self._refresh_position()

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0
        if self._ctx.index < min_lb:
            return

        self._on_bar_call_count += 1

        try:
            raw_signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed", f"on_bar error: {type(exc).__name__}: {exc}")
            self._stop_event.set()
            return

        action = validate_signal(raw_signal, self._bar_index)
        self._handle_signal(action, bar)

        if self._on_bar_call_count % 50 == 0:
            self._log_pipeline("LIVE_BAR")

    # ── Signal Handling + Execution ─────────────────────────

    def _handle_signal(self, action: dict, bar: dict):
        sig = action.get("signal")
        if sig not in VALID_SIGNALS:
            return

        pos = self._ctx.position

        self._exec_log.log_signal(
            sig, self._bar_index, self._last_bar_time,
            self._current_price, pos,
        )

        # ── HOLD ────────────────────────────────────────
        if sig == SIGNAL_HOLD:
            self._exec_log.log_hold()
            if "update_sl" in action or "update_tp" in action:
                self._handle_modify(action)
            return

        # ── CLOSE variants ──────────────────────────────
        if sig == SIGNAL_CLOSE or action.get("close"):
            if not pos.has_position:
                self._exec_log.log_skip("CLOSE", "no position")
                return
            reason = action.get("close_reason", "strategy_close")
            self._close_and_record(reason, bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_LONG:
            if not pos.has_position or pos.direction != "long":
                self._exec_log.log_skip("CLOSE_LONG", "no long position")
                return
            self._close_and_record("strategy_close_long", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        if sig == SIGNAL_CLOSE_SHORT:
            if not pos.has_position or pos.direction != "short":
                self._exec_log.log_skip("CLOSE_SHORT", "no short position")
                return
            self._close_and_record("strategy_close_short", bar)
            self._signal_count += 1
            self._last_signal = action
            return

        # ── BUY / SELL ──────────────────────────────────
        if sig not in (SIGNAL_BUY, SIGNAL_SELL):
            return

        self._signal_count += 1
        self._last_signal = action
        direction = "long" if sig == SIGNAL_BUY else "short"

        # Already in same direction
        if pos.has_position and pos.direction == direction:
            self._exec_log.log_skip(sig, f"already {direction}")
            return

        # In opposite direction — close first
        if pos.has_position:
            self._close_and_record("reverse", bar)

        # Compute SL from signal (ma_snapshot, fixed, or direct)
        entry_estimate = self._current_price or float(bar.get("close", 0))
        sl_price = compute_sl(action, entry_estimate, direction)
        tp_price = compute_tp(action, entry_estimate, sl_price, direction)

        # Validate SL/TP sanity
        if sl_price is not None:
            if direction == "long" and sl_price >= entry_estimate:
                print(f"[EXEC] WARNING: Long SL {sl_price} >= entry {entry_estimate}, clearing SL")
                sl_price = None
            elif direction == "short" and sl_price <= entry_estimate:
                print(f"[EXEC] WARNING: Short SL {sl_price} <= entry {entry_estimate}, clearing SL")
                sl_price = None

        if tp_price is not None:
            if direction == "long" and tp_price <= entry_estimate:
                print(f"[EXEC] WARNING: Long TP {tp_price} <= entry {entry_estimate}, clearing TP")
                tp_price = None
            elif direction == "short" and tp_price >= entry_estimate:
                print(f"[EXEC] WARNING: Short TP {tp_price} >= entry {entry_estimate}, clearing TP")
                tp_price = None

        comment = action.get("comment", f"JG_{sig}")

        # Execute
        if sig == SIGNAL_BUY:
            result = self._executor.open_buy(sl=sl_price, tp=tp_price, comment=comment)
        else:
            result = self._executor.open_sell(sl=sl_price, tp=tp_price, comment=comment)

        self._exec_log.log_open(sig, result, sl_price, tp_price)

        if result.get("success"):
            fill_price = result.get("price", entry_estimate)

            # Recompute TP from actual fill price for R-multiple
            if action.get("tp_mode") == "r_multiple" and sl_price is not None:
                real_risk = abs(fill_price - sl_price)
                r = float(action.get("tp_r", 1.0))
                if real_risk > 0:
                    if direction == "long":
                        tp_price = round(fill_price + real_risk * r, 5)
                    else:
                        tp_price = round(fill_price - real_risk * r, 5)
                    # Modify TP on the position
                    mod_result = self._executor.modify_sl_tp(
                        result["ticket"], sl=sl_price, tp=tp_price
                    )
                    self._exec_log.log_modify(mod_result, sl=sl_price, tp=tp_price)

            # Store trade metadata for MA-cross exits + trade records
            self._active_trade_meta = {
                "entry_bar": self._bar_index,
                "entry_time": bar.get("time", 0),
                "entry_price": fill_price,
                "direction": direction,
                "sl": sl_price,
                "tp": tp_price,
                "ticket": result.get("ticket"),
                "engine_sl_ma_key": action.get("engine_sl_ma_key"),
                "engine_tp_ma_key": action.get("engine_tp_ma_key"),
            }

        self._refresh_position()
        self._report_status()

    def _handle_modify(self, action: dict):
        pos = self._ctx.position
        if not pos.has_position or not pos.ticket:
            self._exec_log.log_skip("MODIFY", "no position")
            return
        new_sl = action.get("update_sl")
        new_tp = action.get("update_tp")
        result = self._executor.modify_sl_tp(pos.ticket, sl=new_sl, tp=new_tp)
        self._exec_log.log_modify(result, sl=new_sl, tp=new_tp)
        self._refresh_position()

    # ── Lifecycle ───────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._set_state("stopped")
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        try:
            self._run_lifecycle()
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] FATAL: {self.deployment_id}:\n{tb}")
            self._set_state("failed", f"{type(exc).__name__}: {exc}")
            try:
                mt5_connector.shutdown_mt5()
            except Exception:
                pass

    def _run_lifecycle(self):
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")
        strategy_instance, load_error = load_strategy_from_source(
            self.source_code, self.class_name, self.strategy_id,
        )
        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return
        self._strategy = strategy_instance
        params = self._strategy.validate_parameters(self.strategy_parameters)
        self._ctx = StrategyContext(bars=[], params=params)

        # Build indicator engine from strategy declarations
        indicator_defs = self._strategy.build_indicators(params)
        self._indicator_engine = IndicatorEngine(indicator_defs)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state("failed", f"on_init() failed: {type(exc).__name__}: {exc}")
            return
        print(f"[RUNNER] Strategy loaded: {self.class_name} | "
              f"min_lookback={getattr(self._strategy, 'min_lookback', 0)} | "
              f"indicators={len(indicator_defs)} | params={params}")

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()
        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return
        self._capture_mt5_info()

        # Phase 2b: Create executor + logger
        self._executor = MT5Executor(self.symbol, self.lot_size, self.deployment_id)
        self._exec_log = ExecutionLogger(self.deployment_id, self.symbol)

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")
        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol, self.tick_lookback_value, self.tick_lookback_unit,
        )
        if ticks is None:
            self._set_state("failed", f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return
        if len(ticks) == 0:
            self._set_state("failed", "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return
        self._total_ticks_ingested = len(ticks)
        self._current_price = ticks[-1]["price"]
        print(f"[RUNNER] Fetched {len(ticks)} historical ticks for {self.symbol}")

        # Phase 4: Generate Initial Bars
        self._set_state("generating_initial_bars")
        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,
        )
        for tick in ticks:
            self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])

        initial_count = self._bar_engine.current_bars_count
        self._total_bars_produced = self._bar_engine.total_bars_emitted
        if self._bar_engine.bars:
            self._last_bar_time = self._bar_engine.bars[-1].get("time")

        print(f"[RUNNER] Initial bars: {initial_count} "
              f"(total emitted: {self._total_bars_produced}) "
              f"(from {len(ticks)} ticks, bar_size={self.bar_size_points}pt)")

        if initial_count == 0:
            self._set_state("failed",
                f"No bars from {len(ticks)} ticks. "
                f"bar_size_points={self.bar_size_points} may be too large for {self.symbol}.")
            mt5_connector.shutdown_mt5()
            return

        self._log_pipeline("INITIAL_BARS")

        # Phase 5: Warm Up (signals logged, NOT executed)
        self._set_state("warming_up")
        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return
            self._ctx.index = i
            self._bar_index = i

            # Compute indicators for warmup bars
            if self._indicator_engine:
                warmup_slice = bars_list[:i + 1]
                self._indicator_engine.update(warmup_slice, self._ctx)

            self._refresh_position()

            if i < min_lb:
                continue

            self._on_bar_call_count += 1
            try:
                raw_signal = self._strategy.on_bar(self._ctx)
                if raw_signal:
                    s = raw_signal.get("signal")
                    if s in (SIGNAL_BUY, SIGNAL_SELL, SIGNAL_CLOSE,
                             SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT):
                        self._warmup_signal_count += 1
                        print(f"[RUNNER] Warmup signal #{self._warmup_signal_count} "
                              f"at bar {i}: {s} (NOT executed)")
            except Exception as exc:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {exc}")

        print(f"[RUNNER] Warmup complete. on_bar calls: {self._on_bar_call_count} | "
              f"warmup signals: {self._warmup_signal_count} (all skipped)")
        self._log_pipeline("WARMUP_DONE")

        # Phase 6: Live Tick Loop (signals ARE executed)
        self._set_state("running")
        self._bar_engine._on_bar = self._on_new_bar
        live_tick_count = 0

        try:
            for tick in mt5_connector.stream_live_ticks(self.symbol):
                if self._stop_event.is_set():
                    break
                self._total_ticks_ingested += 1
                self._current_price = tick["price"]
                live_tick_count += 1
                self._bar_engine.process_tick(tick["ts"], tick["price"], tick["volume"])
                if live_tick_count % 5000 == 0:
                    self._log_pipeline("LIVE_TICK")
        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state("failed", f"Live loop error: {type(exc).__name__}: {exc}")
        finally:
            self._log_pipeline("SHUTDOWN")
            mt5_connector.shutdown_mt5()
            self._mt5_state = "disconnected"
            if not self._stop_event.is_set():
                self._set_state("stopped")
```
