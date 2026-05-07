# Repository Snapshot - Part 1 of 2

- Root folder: `/home/hurairahengg/Documents/JinniGrid`
- I’m building a system called JinniGrid, basically a Kubernetes-style setup: there’s a main Mother server that runs the UI and orchestrates everything, and then a fleet of lightweight/stateless worker VMs. The workers run a special Renko-style bar engine (not normal timeframe candles), and strategies can be uploaded through the Mother UI to be executed across the system, generating MT5-style reports and other outputs. The strategy upload/execution system is mostly finished, but it hasn’t been fully tested yet and there are confirmed bugs. I’m going to drop you the full project codebase via my README—understand what each part does and keep it in context, because later I’ll send big prompts to update and improve the code.
- Total files indexed: `20`
- Files in this chunk: `12`
## Full Project Tree

```text
app/__init__.py
app/config.py
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
config.yaml
main.py
README.md
requirements.txt
ui/css/style.css
worker/config.yaml
worker/README.md
worker/requirements.txt
worker/strategyWorker.py
```

## File Contents


---

## FILE: `app/__init__.py`

- Relative path: `app/__init__.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/__init__.py`
- Size bytes: `1435`
- SHA256: `4d60c40b38c216050d4e4ccb9025182e767c1b7ffe533320ae7beeda71e01856`
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
- Size bytes: `13145`
- SHA256: `a8f34fb7fd82583a79077e256fd8f696e8d17a1db01b4b079e2347f32230010e`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined API Routes

Combined from:
- app/routes/grid.py
- app/routes/health.py
- app/routes/portfolio.py
- strategy/deployment/command routes
- app/routes/system.py

Service imports updated to:
- app.services.mainServices

Important:
- Route casing is preserved.
- /api/Grid is kept for worker heartbeat/list.
- /api/grid is kept for strategy/deployment/command routes.
- Added lowercase /api/grid/workers alias to prevent frontend 404.
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
# Original file: app/routes/health.py
# Prefix preserved: /api
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
# Original file: app/routes/grid.py
# Prefix preserved: /api/Grid
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
    active_strategies: Optional[List[str]] = []
    open_positions_count: Optional[int] = 0
    floating_pnl: Optional[float] = None
    errors: Optional[List[str]] = []


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
    """
    List all workers.

    Both routes are intentionally supported:
    - /api/Grid/workers  original backend casing
    - /api/grid/workers  frontend compatibility alias
    """
    return {
        "ok": True,
        "workers": get_all_workers(),
        "summary": get_fleet_summary(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Portfolio Endpoints
# Original file: app/routes/portfolio.py
# Prefix preserved: /api/portfolio
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
# Original prefix preserved: /api/grid
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
    """
    Return raw .py content.
    Used by workers to fetch strategy code.
    """
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
# Original prefix preserved: /api/grid
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
    strategy_parameters: Optional[Dict[str, Any]] = {}


@router.post("/api/grid/deployments", tags=["Deployments"])
async def create_deployment_endpoint(payload: DeploymentCreate):
    # Verify strategy exists
    strat = get_strategy(payload.strategy_id)

    if not strat:
        raise HTTPException(
            status_code=404,
            detail="Strategy not found. Upload it first.",
        )

    # Create deployment record
    result = create_deployment(payload.model_dump())

    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result)

    deployment = result["deployment"]

    # Fetch strategy file content for the worker
    file_content = get_strategy_file_content(payload.strategy_id)

    # Enqueue deploy command for the worker
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
        "strategy_parameters": deployment["strategy_parameters"],
    }

    enqueue_command(payload.worker_id, "deploy_strategy", cmd_payload)

    # Update deployment state
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

    # Enqueue stop command for the worker
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
# Original prefix preserved: /api/grid
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
    """
    Worker reports its runner state.
    Mother updates deployment accordingly.
    """
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
# Original file: app/routes/system.py
# Prefix preserved: /api/system
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

## FILE: `config.yaml`

- Relative path: `config.yaml`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/config.yaml`
- Size bytes: `215`
- SHA256: `9039bd9eac4b71db0e39e29e0cee3b35ba952ba108ebbd604db1570561efc855`
- Guessed MIME type: `application/yaml`
- Guessed encoding: `unknown`

```yaml
server:
  host: "192.168.3.232"
  port: 5100
  debug: true
  cors_origins:
    - "*"

app:
  name: "JINNI Grid Mother Server"
  version: "0.2.0"

fleet:
  stale_threshold_seconds: 30
  offline_threshold_seconds: 90
```

---

## FILE: `main.py`

- Relative path: `main.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/main.py`
- Size bytes: `1128`
- SHA256: `11acc786f605771a9f4e4f1707b03648dffb489b8e3c8287e30a94d7916e41c6`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID - Mother Server Entry Point
Run: python main.py
"""

import uvicorn
from app import create_app
from app.config import Config
import os
import uvicorn


# App instance at module level so uvicorn reloader can find it
app = create_app()


def main():
    server_config = Config.get_server_config()
    app_config = Config.get_app_config()

    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 5100)
    debug = server_config.get("debug", False)
    name = app_config.get("name", "JINNI GRID Mother Server")
    version = app_config.get("version", "0.2.0")

    print("")
    print("=" * 56)
    print(f"  {name} v{version}")
    print("=" * 56)
    print(f"  Dashboard:   http://{host}:{port}")
    print(f"  API docs:    http://{host}:{port}/docs")
    print(f"  Debug mode:  {debug}")
    print("=" * 56)
    print("")

    run_kwargs = {"host": host, "port": port, "reload": debug}

    if debug:
        run_kwargs["reload_excludes"] = [
            "data/*",
            "strategies/*",
        ]

    uvicorn.run("main:app", **run_kwargs)


if __name__ == "__main__":
    main()
```

---

## FILE: `README.md`

- Relative path: `README.md`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/README.md`
- Size bytes: `5209`
- SHA256: `ed4bd32e218906fdf60ab14ecafc02d8a70ec0ecd6c6f0b36a3a1d0e8bedcb02`
- Guessed MIME type: `text/markdown`
- Guessed encoding: `unknown`

````markdown
# JINNI Grid — Distributed Live Trading Dashboard

## Phase 1B Update — Integrated Mother Server + Worker Heartbeat System

### Overview

JINNI Grid is a distributed live trading system. The Mother Server monitors worker VMs running trading systems. This phase implements the foundational heartbeat/fleet system with a professional dashboard UI.

### What's Implemented

- **Mother Server** — FastAPI backend serving the dashboard UI and fleet API
- **Real Worker Heartbeat** — `POST /api/Grid/workers/heartbeat` endpoint
- **In-Memory Worker Registry** — Tracks workers with freshness/stale logic
- **Fleet API** — `GET /api/Grid/workers` returns real connected worker data
- **Dashboard** — Professional dark-themed UI with portfolio overview (mock) and fleet overview (live from API)
- **Fleet Management Page** — Full fleet page with worker cards, auto-refresh, loading/empty/error states
- **Worker Agent** — Standalone script for worker VMs to send heartbeats
- **Theme System** — Dark/light mode with localStorage persistence
- **Config-Driven** — Host, port, CORS, fleet thresholds all from `config.yaml`

### What's NOT Implemented

- No MT5 connectivity
- No strategy deployment or management
- No trading execution
- No backtesting
- No database (in-memory only, lost on restart)
- No authentication
- No WebSocket
- No Docker/Gridrnetes

---

### Quick Start

#### 1. Start Mother Server

```bash
cd jinni-Grid
pip install -r requirements.txt
python main.py
```

Open `http://<mother-ip>:5100` in your browser.

#### 2. Start Worker Agent

On a worker machine (or same machine for testing):

```bash
cd jinni-Grid/worker
pip install -r requirements.txt
# Edit config.yaml — set mother_server.url to your Mother Server IP:port
python worker_agent.py
```

The worker will appear in the Fleet page within seconds.

---

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/Grid/workers/heartbeat` | Worker heartbeat |
| `GET` | `/api/Grid/workers` | Fleet worker list + summary |
| `GET` | `/api/portfolio/summary` | Portfolio summary (mock) |
| `GET` | `/api/portfolio/equity-history` | Equity curve (mock) |
| `GET` | `/api/system/summary` | System summary |
| `GET` | `/docs` | Swagger UI |

---

### Project Structure

```
jinni-Grid/
  main.py                     Entry point
  config.yaml                 Server + fleet configuration
  requirements.txt            Python dependencies
  README.md                   This file
  app/
    __init__.py               App factory (FastAPI + static files + routes)
    config.py                 Config loader
    routes/
      health.py               GET /api/health
      Grid.py                 POST heartbeat + GET workers
      portfolio.py            Portfolio endpoints (mock)
      system.py               System summary
    services/
      mock_data.py            Portfolio + equity mock data
      worker_registry.py      In-memory worker state store
  ui/
    index.html                Dashboard HTML
    css/
      theme.css               Dark/light theme variables
      base.css                Reset + utilities
      layout.css              Sidebar + topbar + content
      dashboard.css           All component styles
    js/
      mockData.js             Portfolio + equity (client-side mock)
      apiClient.js            API fetch wrapper
      themeManager.js         Dark/light toggle
      dashboardRenderer.js    Dashboard page renderer
      fleetRenderer.js        Fleet page renderer
      app.js                  Navigation + clock + init
  worker/
    worker_agent.py           Heartbeat sender script
    config.yaml               Worker configuration
    requirements.txt          Worker dependencies
    README.md                 Worker setup docs
```

---

### Configuration

#### Mother Server (`config.yaml`)

```yaml
server:
  host: "0.0.0.0"              # Bind to all interfaces
  port: 5100                    # Server port
  debug: true                   # Auto-reload on changes
  cors_origins: ["*"]           # Allowed CORS origins

app:
  name: "JINNI Grid Mother Server"
  version: "0.2.0"

fleet:
  stale_threshold_seconds: 30   # Mark worker stale after 30s
  offline_threshold_seconds: 90 # Mark worker offline after 90s
```

#### Worker (`worker/config.yaml`)

```yaml
worker:
  worker_id: "vm-worker-01"
  worker_name: "Worker 01"
mother_server:
  url: "http://192.168.1.100:5100"
heartbeat:
  interval_seconds: 5
agent:
  version: "0.1.0"
```

---

### Fleet Freshness Logic

| Heartbeat Age | Effective State |
|---------------|-----------------|
| < 30 seconds | Worker's reported state (online/running/etc.) |
| 30 - 89 seconds | **Stale** |
| >= 90 seconds | **Offline** |

Thresholds are configurable in `config.yaml` under `fleet`.

---

### Notes

- All fleet data is **real** — driven by actual worker heartbeats
- Portfolio data is still **mock** — will be connected to real accounts later
- Worker registry is **in-memory only** — cleared on server restart
- The server binds to `0.0.0.0` — accessible from other machines on the same network
````

---

## FILE: `requirements.txt`

- Relative path: `requirements.txt`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/requirements.txt`
- Size bytes: `68`
- SHA256: `e1bb6d373c1916a0cfc941a59698ad1f70b2d70b84da0c666131c6adeec80e95`
- Guessed MIME type: `text/plain`
- Guessed encoding: `unknown`

```text
fastapi>=0.110.0
uvicorn>=0.27.0
pyyaml>=6.0
python-multipart>=0.0.9
```

---

## FILE: `ui/css/style.css`

- Relative path: `ui/css/style.css`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/css/style.css`
- Size bytes: `42961`
- SHA256: `8b19900ad85f1d1f6fa62028a6751b4f5163eea14c4cfdf562c444da41859b9c`
- Guessed MIME type: `text/css`
- Guessed encoding: `unknown`

```css
/* base.css */

*,*::before,*::after { margin:0; padding:0; box-sizing:border-box; }
html { font-size: 14px; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
  height: 100vh;
  -webkit-font-smoothing: antialiased;
}
a { text-decoration: none; color: inherit; }
button { font-family: inherit; border: none; cursor: pointer; background: none; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }
.text-success { color: var(--success) !important; }
.text-danger  { color: var(--danger) !important; }
.text-warning { color: var(--warning) !important; }
.text-accent  { color: var(--accent) !important; }
.text-muted   { color: var(--text-muted) !important; }
.text-stale   { color: var(--stale) !important; }
.mono { font-family: 'JetBrains Mono', monospace; }

/* ── dashboard.css  ───────────────────────────────────────────────────── */

.dashboard {
  display: flex; flex-direction: column; gap: 28px;
  width: 100%; max-width: 1400px;
}

/* ── Section Header ─────────────────────────────────────────────── */

.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.section-header i { color: var(--accent); font-size: 14px; }
.section-header h2 { font-size: 14px; font-weight: 600; color: var(--text-primary); letter-spacing: 0.3px; }
.section-badge {
  margin-left: 8px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
  font-weight: 500; padding: 2px 8px; border-radius: 4px;
  background: var(--accent-dim); color: var(--accent);
}

/* ── Portfolio Cards Grid ───────────────────────────────────────── */

.portfolio-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  width: 100%;
}

.portfolio-card {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 16px 18px; display: flex; align-items: flex-start; gap: 14px;
  box-shadow: var(--shadow-sm); animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.portfolio-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.portfolio-card:nth-child(1) { animation-delay: 0.02s; }
.portfolio-card:nth-child(2) { animation-delay: 0.04s; }
.portfolio-card:nth-child(3) { animation-delay: 0.06s; }
.portfolio-card:nth-child(4) { animation-delay: 0.08s; }
.portfolio-card:nth-child(5) { animation-delay: 0.10s; }
.portfolio-card:nth-child(6) { animation-delay: 0.12s; }
.portfolio-card:nth-child(7) { animation-delay: 0.14s; }
.portfolio-card:nth-child(8) { animation-delay: 0.16s; }

/* ── Card Icon ──────────────────────────────────────────────────── */

.card-icon {
  width: 40px; height: 40px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; flex-shrink: 0;
}
.card-icon.neutral  { background: var(--accent-dim);  color: var(--accent); }
.card-icon.positive { background: var(--success-dim); color: var(--success); }
.card-icon.negative { background: var(--danger-dim);  color: var(--danger); }
.card-icon.warning  { background: var(--warning-dim); color: var(--warning); }

/* ── Card Info ──────────────────────────────────────────────────── */

.card-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; overflow: hidden; }
.card-value {
  font-family: 'JetBrains Mono', monospace; font-size: 17px;
  font-weight: 700; color: var(--text-primary); line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-value.positive { color: var(--success); }
.card-value.negative { color: var(--danger); }
.card-label {
  font-size: 11.5px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.6px; color: var(--text-muted);
  white-space: nowrap;
}

/* ── Equity Chart ───────────────────────────────────────────────── */

.chart-container {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 20px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease 0.2s both; width: 100%;
}
.chart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.chart-title { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.chart-period { font-size: 11px; color: var(--text-muted); font-weight: 500; }
.chart-wrapper { height: 280px; position: relative; }

/* ── Fleet Summary Badges ───────────────────────────────────────── */

.fleet-summary { display: flex; gap: 14px; flex-wrap: wrap; width: 100%; }
.fleet-badge {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 10px 16px; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.3s ease both;
}
.badge-count { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.badge-label { font-size: 11.5px; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.badge-count.total   { color: var(--text-primary); }
.badge-count.online  { color: var(--success); }
.badge-count.warning { color: var(--warning); }
.badge-count.stale   { color: var(--stale); }
.badge-count.offline { color: var(--text-muted); }
.badge-count.error   { color: var(--danger); }

/* ── Fleet Grid ─────────────────────────────────────────────────── */

.fleet-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  width: 100%;
}

/* ── Node Card ──────────────────────────────────────────────────── */

.node-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
  animation: fadeInUp 0.4s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
  min-width: 0;
}
.node-card:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); background: var(--bg-card-hover); }
.node-card:nth-child(1) { animation-delay: 0.02s; }
.node-card:nth-child(2) { animation-delay: 0.04s; }
.node-card:nth-child(3) { animation-delay: 0.06s; }
.node-card:nth-child(4) { animation-delay: 0.08s; }
.node-card:nth-child(5) { animation-delay: 0.10s; }
.node-card:nth-child(6) { animation-delay: 0.12s; }

/* ── Node Card Top Bar ──────────────────────────────────────────── */

.node-card-top { height: 2px; }
.node-card-top.online  { background: var(--success); }
.node-card-top.running { background: var(--success); }
.node-card-top.idle    { background: var(--accent); }
.node-card-top.warning { background: var(--warning); }
.node-card-top.stale   { background: var(--stale); }
.node-card-top.offline { background: var(--text-muted); }
.node-card-top.error   { background: var(--danger); }

/* ── Node Card Header ───────────────────────────────────────────── */

.node-card-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px 10px; }
.node-name-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
.node-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.node-status-dot.online  { background: var(--success); }
.node-status-dot.running { background: var(--success); }
.node-status-dot.idle    { background: var(--accent); }
.node-status-dot.warning { background: var(--warning); }
.node-status-dot.stale   { background: var(--stale); }
.node-status-dot.offline { background: var(--text-muted); }
.node-status-dot.error   { background: var(--danger); }
.node-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
  font-weight: 500; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.node-status-badge {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; padding: 3px 8px; border-radius: 4px; flex-shrink: 0;
}
.node-status-badge.online  { background: var(--success-dim); color: var(--success); }
.node-status-badge.running { background: var(--success-dim); color: var(--success); }
.node-status-badge.idle    { background: var(--accent-dim);  color: var(--accent); }
.node-status-badge.warning { background: var(--warning-dim); color: var(--warning); }
.node-status-badge.stale   { background: var(--stale-dim);   color: var(--stale); }
.node-status-badge.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.node-status-badge.error   { background: var(--danger-dim);  color: var(--danger); }
.node-status-badge.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Node Card Body ─────────────────────────────────────────────── */

.node-card-body { padding: 0 16px 14px; }
.node-info-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0; border-bottom: 1px solid var(--border-subtle);
}
.node-info-row:last-child { border-bottom: none; }
.node-info-label { font-size: 11px; color: var(--text-muted); font-weight: 500; white-space: nowrap; }
.node-info-value {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  color: var(--text-secondary); font-weight: 400; text-align: right;
  max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.node-info-value.strategy { color: var(--accent); font-weight: 500; }
.node-info-value.inactive { color: var(--text-muted); }

/* ── State Pills ────────────────────────────────────────────────── */

.state-pill {
  display: inline-block; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.4px;
  padding: 2px 8px; border-radius: 4px;
}
.state-pill.online  { background: var(--success-dim); color: var(--success); }
.state-pill.running { background: var(--success-dim); color: var(--success); }
.state-pill.idle    { background: var(--accent-dim);  color: var(--accent); }
.state-pill.warning { background: var(--warning-dim); color: var(--warning); }
.state-pill.stale   { background: var(--stale-dim);   color: var(--stale); }
.state-pill.error   { background: var(--danger-dim);  color: var(--danger); }
.state-pill.offline { background: rgba(100,116,139,0.15); color: var(--text-muted); }
.state-pill.unknown { background: rgba(100,116,139,0.15); color: var(--text-muted); }

/* ── Compact Fleet Table ────────────────────────────────────────── */

.compact-fleet-wrapper {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; overflow-x: auto;
  box-shadow: var(--shadow-sm); margin-top: 12px;
}
.compact-fleet-table { width: 100%; border-collapse: separate; border-spacing: 0; }
.compact-fleet-table th {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 600; padding: 8px 12px;
  text-align: left; border-bottom: 1px solid var(--border-primary);
}
.compact-fleet-table td {
  font-size: 12px; padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary);
}
.compact-fleet-table td.mono { font-family: 'JetBrains Mono', monospace; }
.compact-fleet-table tr:hover td { background: var(--bg-card-hover); }

/* ── View Fleet Link ────────────────────────────────────────────── */

.view-fleet-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--accent); font-weight: 500;
  cursor: pointer; margin-top: 12px; transition: opacity 0.2s;
}
.view-fleet-link:hover { opacity: 0.8; }

/* ── Null Value ─────────────────────────────────────────────────── */

.value-null { color: var(--text-muted); font-style: italic; }

/* ── Dashboard Fleet Section ────────────────────────────────────── */

.dashboard-fleet-section { min-height: 120px; }

/* ── Loading State ──────────────────────────────────────────────── */

.loading-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-state p { font-size: 13px; color: var(--text-muted); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty State ────────────────────────────────────────────────── */

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.empty-state i { font-size: 52px; color: var(--text-muted); opacity: 0.25; }
.empty-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.empty-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.empty-state code {
  font-family: 'JetBrains Mono', monospace; font-size: 11.5px;
  background: var(--bg-secondary); padding: 2px 8px;
  border-radius: 4px; color: var(--accent);
}

/* ── Error State ────────────────────────────────────────────────── */

.error-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 300px; gap: 14px;
  animation: fadeInUp 0.4s ease both; padding: 40px;
}
.error-state i { font-size: 52px; color: var(--danger); opacity: 0.4; }
.error-state h3 { font-size: 16px; font-weight: 600; color: var(--text-secondary); }
.error-state p {
  font-size: 13px; color: var(--text-muted); max-width: 420px;
  text-align: center; line-height: 1.6;
}
.retry-btn {
  padding: 8px 20px; background: var(--accent-dim); color: var(--accent);
  border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: 1px solid transparent; transition: all 0.2s ease;
}
.retry-btn:hover { background: var(--accent); color: #fff; }

/* ── Fleet Page ─────────────────────────────────────────────────── */

.fleet-page {
  display: flex; flex-direction: column; gap: 24px;
  width: 100%; max-width: 1400px;
  animation: fadeInUp 0.3s ease both;
}
.fleet-page-header {
  display: flex; align-items: center; justify-content: space-between;
}
.fleet-page-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.fleet-page-meta { display: flex; align-items: center; gap: 14px; }
.auto-refresh-badge {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  color: var(--text-muted); background: var(--bg-card);
  border: 1px solid var(--border-primary); padding: 4px 10px; border-radius: 5px;
}
.auto-refresh-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--success); animation: pulse-glow 2s ease-in-out infinite;
}
.last-synced {
  font-size: 11px; color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Placeholder Page ───────────────────────────────────────────── */

.placeholder-page {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; min-height: 400px; gap: 16px;
  animation: fadeInUp 0.4s ease both;
}
.placeholder-page i { font-size: 48px; color: var(--text-muted); opacity: 0.3; }
.placeholder-page h2 { font-size: 18px; font-weight: 600; color: var(--text-secondary); }
.placeholder-page p {
  font-size: 13px; color: var(--text-muted); max-width: 360px;
  text-align: center; line-height: 1.6;
}

/* ── Animations ─────────────────────────────────────────────────── */

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Responsive ─────────────────────────────────────────────────── */

@media (max-width: 1100px) {
  .portfolio-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fleet-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .portfolio-grid { grid-template-columns: minmax(0, 1fr); }
  .fleet-grid { grid-template-columns: minmax(0, 1fr); }
}

/* ── layout.css  ────────────────────────────────────────────────── */

body { display: flex; flex-direction: row; }

/* ── Sidebar (always dark) ──────────────────────────────────────── */

.sidebar {
  width: 240px; min-width: 240px; height: 100vh; background: #0d1117;
  display: flex; flex-direction: column; border-right: 1px solid #1e293b; z-index: 10;
}
.sidebar-brand {
  height: 60px; display: flex; align-items: center; gap: 12px;
  padding: 0 20px; border-bottom: 1px solid #1e293b;
}
.brand-mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-weight: 700;
  font-size: 12px; color: #fff; letter-spacing: -0.5px; flex-shrink: 0;
}
.brand-text { display: flex; flex-direction: column; line-height: 1; }
.brand-name { font-weight: 700; font-size: 13px; color: #e2e8f0; letter-spacing: 1.2px; }
.brand-sub { font-size: 10px; color: #64748b; margin-top: 3px; letter-spacing: 0.5px; }

/* ── Navigation ─────────────────────────────────────────────────── */

.sidebar-nav { flex: 1; display: flex; flex-direction: column; padding: 12px 0; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 10px 20px;
  color: #94a3b8; font-size: 13px; font-weight: 500;
  border-left: 3px solid transparent; transition: all 0.2s ease;
}
.nav-item:hover { color: #e2e8f0; background: rgba(255,255,255,0.03); }
.nav-item.active { color: #06b6d4; border-left-color: #06b6d4; background: rgba(6,182,212,0.08); }
.nav-item i { width: 18px; text-align: center; font-size: 14px; }

/* ── Sidebar Footer / Theme Toggle ──────────────────────────────── */

.sidebar-footer { padding: 12px 16px; border-top: 1px solid #1e293b; }
.theme-toggle {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 8px 12px; border-radius: 6px; color: #94a3b8;
  font-size: 12px; font-weight: 500; transition: all 0.2s ease;
}
.theme-toggle:hover { color: #e2e8f0; background: rgba(255,255,255,0.05); }
.theme-toggle i { width: 16px; text-align: center; font-size: 13px; }

/* ── Main Wrapper ───────────────────────────────────────────────── */

.main-wrapper {
  flex: 1; display: flex; flex-direction: column;
  height: 100vh; min-width: 0; overflow: hidden;
}

/* ── Top Bar ────────────────────────────────────────────────────── */

.topbar {
  height: 60px; min-height: 60px; background: var(--bg-topbar);
  border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between; padding: 0 28px;
}
.topbar-left { display: flex; align-items: baseline; gap: 12px; }
.topbar-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.topbar-subtitle { font-size: 11.5px; color: var(--text-muted); font-weight: 400; }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.topbar-status { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); font-weight: 500; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot--online { background: var(--success); }
.status-dot--offline { background: var(--text-muted); }
.status-dot--warning { background: var(--warning); }
.status-dot--error { background: var(--danger); }
.status-dot.pulse { animation: pulse-glow 2s ease-in-out infinite; }

@keyframes pulse-glow {
  0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
  50% { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
}

.topbar-clock {
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
  font-weight: 500; color: var(--text-secondary); letter-spacing: 0.5px;
}

/* ── Content Area ───────────────────────────────────────────────── */

.content {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 24px 28px;
  background: var(--bg-primary);
  width: 100%;
}

/*theme.css*/

[data-theme="dark"] {
  --bg-primary: #0b0f19;
  --bg-secondary: #111827;
  --bg-card: #151c2c;
  --bg-card-hover: #1a2236;
  --bg-topbar: #0d1117;
  --border-primary: #1e293b;
  --border-subtle: #162033;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #06b6d4;
  --accent-dim: rgba(6, 182, 212, 0.15);
  --success: #10b981;
  --success-dim: rgba(16, 185, 129, 0.15);
  --danger: #ef4444;
  --danger-dim: rgba(239, 68, 68, 0.15);
  --warning: #f59e0b;
  --warning-dim: rgba(245, 158, 11, 0.15);
  --stale: #fb923c;
  --stale-dim: rgba(251, 146, 60, 0.15);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
  --scrollbar-track: #0b0f19;
  --scrollbar-thumb: #1e293b;
  --scrollbar-thumb-hover: #334155;
}
[data-theme="light"] {
  --bg-primary: #f0f4f8;
  --bg-secondary: #e2e8f0;
  --bg-card: #ffffff;
  --bg-card-hover: #f8fafc;
  --bg-topbar: #ffffff;
  --border-primary: #e2e8f0;
  --border-subtle: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --accent: #0891b2;
  --accent-dim: rgba(8, 145, 178, 0.12);
  --success: #059669;
  --success-dim: rgba(5, 150, 105, 0.12);
  --danger: #dc2626;
  --danger-dim: rgba(220, 38, 38, 0.12);
  --warning: #d97706;
  --warning-dim: rgba(217, 119, 6, 0.12);
  --stale: #ea580c;
  --stale-dim: rgba(234, 88, 12, 0.12);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.1);
  --scrollbar-track: #f0f4f8;
  --scrollbar-thumb: #cbd5e1;
  --scrollbar-thumb-hover: #94a3b8;
}
body,.topbar,.content,.portfolio-card,.node-card,.section-header,.fleet-summary,
.chart-container,.fleet-page,.loading-state,.empty-state,.error-state,.compact-fleet-wrapper,
.fleet-badge {
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

/* worker-detail.css*/


/* ── Clickable Fleet Enhancement ──────────────────────────── */
.node-card.clickable { cursor: pointer; }
.node-card.clickable:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-dim), var(--shadow-md); }
.node-card-action {
  display: flex; align-items: center; gap: 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px solid var(--border-subtle); font-size: 11px; color: var(--accent);
  font-weight: 500;
}
.compact-fleet-table tr.clickable { cursor: pointer; }
.compact-fleet-table tr.clickable:hover td { background: var(--bg-card-hover); }

/* ── Worker Detail Page ───────────────────────────────────── */
.worker-detail { display: flex; flex-direction: column; gap: 24px; max-width: 1400px; animation: fadeInUp 0.3s ease both; }

.wd-header {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 20px; display: flex; align-items: center; justify-content: space-between;
  box-shadow: var(--shadow-sm);
}
.wd-header-left { display: flex; align-items: center; gap: 16px; }
.wd-back-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 6px;
}
.wd-back-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-header-info { display: flex; flex-direction: column; gap: 4px; }
.wd-header-info h2 { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.wd-header-meta {
  display: flex; align-items: center; gap: 8px; font-size: 11.5px;
  color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
}
.meta-sep { opacity: 0.4; }
.wd-header-right { display: flex; align-items: center; gap: 12px; }
.wd-refresh-btn {
  padding: 8px 14px; background: var(--bg-secondary); border: 1px solid var(--border-primary);
  border-radius: 6px; color: var(--text-secondary); font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-refresh-btn:hover { color: var(--accent); border-color: var(--accent); }
.wd-emergency-btn {
  padding: 8px 16px; background: var(--danger-dim); color: var(--danger);
  border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.5px; border: 1px solid transparent; cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.wd-emergency-btn:hover { background: var(--danger); color: #fff; }

/* ── Status Cards Grid ────────────────────────────────────── */
.wd-status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.wd-status-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 6px;
  box-shadow: var(--shadow-sm);
}
.wd-status-card .status-label {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 500;
}
.wd-status-card .status-value {
  font-family: 'JetBrains Mono', monospace; font-size: 15px; font-weight: 600;
  color: var(--text-primary);
}
.status-indicator { display: flex; align-items: center; gap: 6px; }
.wd-status-dot-sm {
  width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0;
}
.wd-status-dot-sm.green { background: var(--success); }
.wd-status-dot-sm.amber { background: var(--warning); }
.wd-status-dot-sm.orange { background: var(--stale); }
.wd-status-dot-sm.red { background: var(--danger); }
.wd-status-dot-sm.blue { background: var(--accent); }
.wd-status-dot-sm.gray { background: var(--text-muted); }

/* ── Content Layout ───────────────────────────────────────── */
.wd-content { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.wd-main-col { display: flex; flex-direction: column; gap: 20px; }
.wd-side-col { display: flex; flex-direction: column; gap: 20px; }

/* ── Panel ────────────────────────────────────────────────── */
.wd-panel {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; overflow: hidden; box-shadow: var(--shadow-sm);
}
.wd-panel-header {
  font-size: 13px; font-weight: 600; color: var(--text-primary);
  padding: 16px 20px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.panel-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 500;
  padding: 2px 8px; border-radius: 4px; background: var(--accent-dim); color: var(--accent);
}
.panel-badge.mock {
  background: var(--warning-dim); color: var(--warning);
}
.wd-panel-body { padding: 20px; }

/* ── File Upload ──────────────────────────────────────────── */
.wd-file-upload {
  border: 2px dashed var(--border-primary); border-radius: 8px; padding: 32px;
  text-align: center; transition: all 0.2s; cursor: pointer;
}
.wd-file-upload:hover { border-color: var(--accent); }
.wd-file-upload.has-file { border-color: var(--success); border-style: solid; }
.wd-file-upload i { font-size: 32px; color: var(--text-muted); opacity: 0.4; }
.wd-file-upload h4 { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-top: 10px; }
.wd-file-upload p { font-size: 11.5px; color: var(--text-muted); margin-top: 4px; }
.file-name {
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent);
  font-weight: 500; margin-top: 8px;
}
.wd-file-status {
  display: flex; align-items: center; gap: 6px; justify-content: center;
  margin-top: 8px; font-size: 11px;
}

/* ── Metadata Preview ─────────────────────────────────────── */
.wd-metadata {
  margin-top: 16px; background: var(--bg-secondary); border-radius: 8px;
  padding: 16px; animation: fadeInUp 0.3s ease both;
}
.wd-metadata-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.wd-metadata-item { display: flex; flex-direction: column; gap: 2px; }
.wd-metadata-label {
  font-size: 10px; text-transform: uppercase; color: var(--text-muted);
  font-weight: 500; letter-spacing: 0.4px;
}
.wd-metadata-value {
  font-size: 12px; color: var(--text-primary);
  font-family: 'JetBrains Mono', monospace;
}

/* ── Form Controls ────────────────────────────────────────── */
.wd-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.wd-form-group { display: flex; flex-direction: column; gap: 5px; }
.wd-form-label {
  font-size: 11px; color: var(--text-muted); font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.wd-form-input, .wd-form-select {
  width: 100%; padding: 8px 12px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 12px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s;
}
.wd-form-input:focus, .wd-form-select:focus { border-color: var(--accent); }
.wd-form-select { cursor: pointer; }

/* ── Toggle Switch ────────────────────────────────────────── */
.wd-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-toggle-row:last-child { border-bottom: none; }
.wd-toggle-label { display: flex; flex-direction: column; gap: 2px; }
.wd-toggle-label span:first-child { font-size: 12px; color: var(--text-primary); font-weight: 500; }
.wd-toggle-label span:last-child { font-size: 10.5px; color: var(--text-muted); }
.wd-toggle {
  position: relative; width: 40px; height: 22px; -webkit-appearance: none;
  appearance: none; background: var(--border-primary); border-radius: 11px;
  cursor: pointer; transition: background 0.2s; flex-shrink: 0; border: none;
}
.wd-toggle:checked { background: var(--accent); }
.wd-toggle::after {
  content: ''; position: absolute; width: 18px; height: 18px; border-radius: 50%;
  background: var(--text-primary); top: 2px; left: 2px; transition: transform 0.2s;
}
.wd-toggle:checked::after { transform: translateX(18px); }

/* ── Parameters Editor ────────────────────────────────────── */
.wd-params-list { display: flex; flex-direction: column; }
.wd-param-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle); gap: 12px;
}
.wd-param-row:last-child { border-bottom: none; }
.wd-param-row.modified { border-left: 3px solid var(--accent); padding-left: 12px; margin-left: -4px; }
.wd-param-info { flex: 1; min-width: 0; }
.wd-param-name { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.wd-param-desc { font-size: 10.5px; color: var(--text-muted); margin-top: 2px; }
.wd-param-type-badge {
  display: inline-block; font-size: 9px; font-weight: 600; text-transform: uppercase;
  padding: 1px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}
.type-int { background: var(--accent-dim); color: var(--accent); }
.type-float { background: var(--warning-dim); color: var(--warning); }
.type-bool { background: var(--success-dim); color: var(--success); }
.type-string { background: var(--stale-dim); color: var(--stale); }
.wd-param-controls { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wd-param-input {
  width: 100px; padding: 6px 10px; background: var(--bg-secondary);
  border: 1px solid var(--border-primary); border-radius: 6px;
  color: var(--text-primary); font-size: 11.5px; font-family: 'JetBrains Mono', monospace;
  outline: none; transition: border-color 0.2s; text-align: right;
}
.wd-param-input:focus { border-color: var(--accent); }
.wd-param-reset {
  width: 24px; height: 24px; border-radius: 50%; background: transparent;
  border: none; color: var(--text-muted); font-size: 11px; cursor: pointer;
  opacity: 0.5; transition: all 0.2s; display: flex; align-items: center; justify-content: center;
}
.wd-param-reset:hover { opacity: 1; color: var(--accent); }

/* ── Checklist ────────────────────────────────────────────── */
.wd-checklist { display: flex; flex-direction: column; }
.wd-check-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.wd-check-item:last-child { border-bottom: none; }
.wd-check-icon {
  width: 18px; height: 18px; border-radius: 4px; display: flex;
  align-items: center; justify-content: center; font-size: 10px; flex-shrink: 0;
}
.wd-check-icon.pass { background: var(--success-dim); color: var(--success); }
.wd-check-icon.fail { background: var(--danger-dim); color: var(--danger); }
.wd-check-icon.warn { background: var(--warning-dim); color: var(--warning); }
.wd-check-icon.info { background: var(--accent-dim); color: var(--accent); }
.wd-check-text { font-size: 12px; color: var(--text-secondary); }
.wd-check-text.pass { color: var(--text-primary); }
.wd-check-text.dimmed { color: var(--text-muted); font-style: italic; }

/* ── Deploy Action Bar ────────────────────────────────────── */
.wd-action-bar {
  padding: 16px 20px; display: flex; align-items: center;
  justify-content: space-between; border-top: 1px solid var(--border-primary);
}
.wd-action-bar-left, .wd-action-bar-right { display: flex; gap: 10px; }
.wd-btn {
  padding: 8px 18px; border-radius: 6px; font-size: 12px; font-weight: 500;
  border: 1px solid transparent; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; gap: 6px;
}
.wd-btn-ghost { background: transparent; border-color: var(--border-primary); color: var(--text-secondary); }
.wd-btn-ghost:hover { color: var(--text-primary); border-color: var(--text-muted); }
.wd-btn-outline { background: transparent; border-color: var(--accent); color: var(--accent); }
.wd-btn-outline:hover { background: var(--accent); color: #fff; }
.wd-btn-primary { background: var(--accent); color: #fff; font-weight: 600; }
.wd-btn-primary:hover { filter: brightness(1.1); }
.wd-btn-primary.deploy {
  background: linear-gradient(135deg, #06b6d4, #3b82f6); box-shadow: var(--shadow-md);
}
.wd-btn-primary.deploy:hover { box-shadow: var(--shadow-lg); transform: translateY(-1px); }

/* ── Activity Timeline ────────────────────────────────────── */
.wd-timeline { display: flex; flex-direction: column; }
.wd-timeline-item {
  display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-subtle);
}
.wd-timeline-item:last-child { border-bottom: none; }
.wd-timeline-time {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--text-muted);
  width: 60px; flex-shrink: 0;
}
.wd-timeline-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  flex-shrink: 0; margin-top: 5px;
}
.wd-timeline-text { font-size: 11.5px; color: var(--text-secondary); }

/* ── Modal ────────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
  animation: modal-fade-in 0.2s ease;
}
.modal-card {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 12px; width: 480px; max-width: 90vw; box-shadow: var(--shadow-lg);
  animation: modal-slide-in 0.3s ease;
}
.modal-header {
  padding: 20px 24px; border-bottom: 1px solid var(--border-primary);
  display: flex; align-items: center; justify-content: space-between;
}
.modal-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.modal-close { font-size: 18px; cursor: pointer; color: var(--text-muted); transition: color 0.2s; background: none; border: none; }
.modal-close:hover { color: var(--text-primary); }
.modal-body { padding: 20px 24px; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.modal-footer {
  padding: 16px 24px; border-top: 1px solid var(--border-primary);
  display: flex; justify-content: flex-end; gap: 10px;
}
.modal-summary {
  background: var(--bg-secondary); border-radius: 8px; padding: 14px; margin-top: 12px;
}
.modal-summary-row { display: flex; justify-content: space-between; padding: 4px 0; }
.modal-summary-label { font-size: 11.5px; color: var(--text-muted); }
.modal-summary-value { font-size: 12px; font-family: 'JetBrains Mono', monospace; color: var(--text-primary); }
.modal-warning {
  background: var(--warning-dim); border-radius: 6px; padding: 10px 14px;
  margin-top: 12px; font-size: 11.5px; color: var(--warning);
  display: flex; gap: 8px; align-items: flex-start; line-height: 1.5;
}

@keyframes modal-fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes modal-slide-in {
  from { opacity: 0; transform: translateY(-10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Toast ─────────────────────────────────────────────────── */
.toast-container {
  position: fixed; top: 20px; right: 20px; z-index: 1100;
  display: flex; flex-direction: column; gap: 8px;
}
.toast {
  padding: 12px 18px; border-radius: 8px; box-shadow: var(--shadow-md);
  display: flex; align-items: center; gap: 10px; font-size: 12.5px; font-weight: 500;
  animation: toast-in 0.3s ease; min-width: 300px; max-width: 420px;
}
.toast-success { background: var(--success-dim); border: 1px solid rgba(16,185,129,0.2); color: var(--success); }
.toast-info { background: var(--accent-dim); border: 1px solid rgba(6,182,212,0.2); color: var(--accent); }
.toast-warning { background: var(--warning-dim); border: 1px solid rgba(245,158,11,0.2); color: var(--warning); }
.toast-error { background: var(--danger-dim); border: 1px solid rgba(239,68,68,0.2); color: var(--danger); }
.toast i { font-size: 14px; flex-shrink: 0; }
.toast-dismiss {
  margin-left: auto; cursor: pointer; opacity: 0.6; font-size: 14px;
  background: none; border: none; color: inherit;
}
.toast-dismiss:hover { opacity: 1; }

@keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 1200px) {
  .wd-content { grid-template-columns: 1fr; }
  .wd-status-grid { grid-template-columns: repeat(2, 1fr); }
  .wd-form-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .wd-status-grid { grid-template-columns: 1fr; }
}
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
- Size bytes: `33487`
- SHA256: `f9aebacfb6ec1a66d6088205dc1acda8d2d9d6727879f49498ef6325606b04ee`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID — Combined Worker Runtime
worker/strategyWorker.py

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
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# Strategy Base Class
# =============================================================================

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"
VALID_SIGNALS = {SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE, None}


class BaseStrategy(ABC):
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    min_lookback: int = 0

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name or self.strategy_id,
            "description": self.description or "",
            "version": self.version,
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

@dataclass
class PositionState:
    """Read-only position snapshot passed to strategies."""

    has_position: bool = False
    direction: Optional[str] = None   # "long" / "short" / None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: Optional[float] = None
    entry_bar: Optional[int] = None


class StrategyContext:
    """
    The ctx object strategies receive in on_bar(ctx).
    Read-only except ctx.state, which is a mutable dict persisting across bars.
    """

    def __init__(
        self,
        bars: list,
        params: dict,
        position: Optional[PositionState] = None,
    ):
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

def _make_bar(
    time_: int,
    open_: float,
    high_: float,
    low_: float,
    close_: float,
    volume_: float,
) -> dict:
    return {
        "time": int(time_),
        "open": round(open_, 5),
        "high": round(high_, 5),
        "low": round(low_, 5),
        "close": round(close_, 5),
        "volume": round(volume_, 2),
    }


class RangeBarEngine:
    """
    Tick-by-tick range bar builder.

    Usage:
        engine = RangeBarEngine(
            bar_size_points=6.0,
            max_bars=500,
            on_bar=my_callback,
        )
        engine.process_tick(timestamp, price, volume)
    """

    def __init__(
        self,
        bar_size_points: float,
        max_bars: int = 500,
        on_bar: Optional[Callable[[dict], None]] = None,
    ):
        self.range_size: float = float(bar_size_points)
        self.max_bars: int = max_bars
        self._on_bar: Optional[Callable[[dict], None]] = on_bar

        self.trend: int = 0   # 0 = startup, 1 = bull, -1 = bear
        self.bar: Optional[dict] = None

        self.bars: deque = deque(maxlen=max_bars)
        self._last_emitted_ts: Optional[int] = None

        self.total_ticks: int = 0
        self.total_bars_emitted: int = 0

    @property
    def current_bars_count(self) -> int:
        return len(self.bars)

    def _emit(self, bar_dict: dict) -> None:
        """Emit a completed bar: dedup timestamp, store in buffer, fire callback."""
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
        self.bar = {
            "time": ts,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }

    def process_tick(self, ts: int, price: float, volume: float = 0.0) -> None:
        """
        Feed a single tick. May emit zero, one, or multiple completed bars.
        """
        self.total_ticks += 1

        if self.bar is None:
            self._start_bar(ts, price, volume)
            return

        p = price
        rs = self.range_size

        self.bar["volume"] += volume

        while True:
            o = self.bar["open"]

            # STARTUP / NO TREND
            if self.trend == 0:
                up_target = o + rs
                down_target = o - rs

                if p >= up_target:
                    self.bar["high"] = max(self.bar["high"], up_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = up_target

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            self.bar["open"],
                            self.bar["high"],
                            self.bar["low"],
                            self.bar["close"],
                            self.bar["volume"],
                        )
                    )

                    self.trend = 1
                    new_open = up_target
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                if p <= down_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], down_target)
                    self.bar["close"] = down_target

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            self.bar["open"],
                            self.bar["high"],
                            self.bar["low"],
                            self.bar["close"],
                            self.bar["volume"],
                        )
                    )

                    self.trend = -1
                    new_open = down_target
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

            # BULL TREND
            if self.trend == 1:
                cont_target = o + rs
                rev_target = o - (2 * rs)

                if p >= cont_target:
                    self.bar["high"] = max(self.bar["high"], cont_target)
                    self.bar["low"] = min(self.bar["low"], o)
                    self.bar["close"] = cont_target

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            self.bar["open"],
                            self.bar["high"],
                            self.bar["low"],
                            self.bar["close"],
                            self.bar["volume"],
                        )
                    )

                    new_open = cont_target
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                if p <= rev_target:
                    rev_open = o - rs
                    rev_close = o - (2 * rs)
                    high_ = max(self.bar["high"], o)
                    low_ = min(self.bar["low"], rev_close)

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            rev_open,
                            high_,
                            low_,
                            rev_close,
                            self.bar["volume"],
                        )
                    )

                    self.trend = -1
                    new_open = rev_close
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

            # BEAR TREND
            if self.trend == -1:
                cont_target = o - rs
                rev_target = o + (2 * rs)

                if p <= cont_target:
                    self.bar["high"] = max(self.bar["high"], o)
                    self.bar["low"] = min(self.bar["low"], cont_target)
                    self.bar["close"] = cont_target

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            self.bar["open"],
                            self.bar["high"],
                            self.bar["low"],
                            self.bar["close"],
                            self.bar["volume"],
                        )
                    )

                    new_open = cont_target
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                if p >= rev_target:
                    rev_open = o + rs
                    rev_close = o + (2 * rs)
                    high_ = max(self.bar["high"], rev_close)
                    low_ = min(self.bar["low"], o)

                    self._emit(
                        _make_bar(
                            self.bar["time"],
                            rev_open,
                            high_,
                            low_,
                            rev_close,
                            self.bar["volume"],
                        )
                    )

                    self.trend = 1
                    new_open = rev_close
                    self.bar = {
                        "time": ts,
                        "open": new_open,
                        "high": new_open,
                        "low": new_open,
                        "close": new_open,
                        "volume": 0.0,
                    }
                    continue

                self.bar["high"] = max(self.bar["high"], p)
                self.bar["low"] = min(self.bar["low"], p)
                self.bar["close"] = p
                break

    def reset(self) -> None:
        """Full reset — clears all bars and state."""
        self.trend = 0
        self.bar = None
        self.bars.clear()
        self._last_emitted_ts = None
        self.total_ticks = 0
        self.total_bars_emitted = 0


# =============================================================================
# MT5 Connector
# =============================================================================

def _import_mt5():
    """Lazy import — fails clearly if MetaTrader5 is not installed."""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


def init_mt5() -> Tuple[bool, str]:
    """
    Initialize MT5 terminal connection.

    Uses whatever MT5 terminal is installed/running on this machine.
    Does NOT specify path, login, server, or password.
    """
    mt5 = _import_mt5()

    if mt5 is None:
        return False, "MetaTrader5 package not installed. pip install MetaTrader5"

    if not mt5.initialize():
        err = mt5.last_error()
        return False, f"MT5 initialize() failed: {err}"

    info = mt5.terminal_info()

    if info is None:
        return False, "MT5 terminal_info() returned None."

    account = mt5.account_info()
    acct_str = ""

    if account:
        acct_str = f" | account={account.login} broker={account.company}"

    print(f"[MT5] Connected: {info.name}{acct_str}")
    return True, "ok"


def shutdown_mt5() -> None:
    mt5 = _import_mt5()

    if mt5:
        mt5.shutdown()


def fetch_historical_ticks(
    symbol: str,
    lookback_value: int,
    lookback_unit: str,
) -> Tuple[Optional[list], str]:
    """
    Fetch historical ticks from MT5.

    Returns:
        (list_of_tick_dicts, "ok") on success
        (None, error_message) on failure

    Each tick dict:
        {"ts": int, "price": float, "volume": float}
    """
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

    print(
        f"[MT5] Fetching ticks: {symbol} "
        f"from {from_time.isoformat()} to {now.isoformat()}"
    )

    ticks = mt5.copy_ticks_range(symbol, from_time, now, mt5.COPY_TICKS_ALL)

    if ticks is None or len(ticks) == 0:
        err = mt5.last_error()
        return None, f"No ticks returned for {symbol}. MT5 error: {err}"

    result = []

    for tick in ticks:
        price = tick.bid if tick.bid > 0 else (tick.last if tick.last > 0 else tick.ask)

        if price <= 0:
            continue

        result.append(
            {
                "ts": int(tick.time),
                "price": float(price),
                "volume": float(tick.volume) if tick.volume else 0.0,
            }
        )

    print(f"[MT5] Got {len(result)} ticks for {symbol}")
    return result, "ok"


def stream_live_ticks(symbol: str, poll_interval: float = 0.05):
    """
    Generator that yields new ticks by polling MT5.

    Yields:
        {"ts": int, "price": float, "volume": float}
    """
    mt5 = _import_mt5()

    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed.")

    cursor_time = datetime.now(timezone.utc)
    last_tick_time = 0

    while True:
        ticks = mt5.copy_ticks_from(symbol, cursor_time, 1000, mt5.COPY_TICKS_ALL)

        if ticks is not None and len(ticks) > 0:
            for tick in ticks:
                if tick.time_msc <= last_tick_time:
                    continue

                last_tick_time = tick.time_msc

                price = tick.bid if tick.bid > 0 else (
                    tick.last if tick.last > 0 else tick.ask
                )

                if price <= 0:
                    continue

                yield {
                    "ts": int(tick.time),
                    "price": float(price),
                    "volume": float(tick.volume) if tick.volume else 0.0,
                }

            last_tick = ticks[-1]
            cursor_time = datetime.fromtimestamp(last_tick.time, tz=timezone.utc)

        time.sleep(poll_interval)


class _MT5ConnectorFacade:
    """
    Compatibility facade.

    Keeps StrategyRunner logic close to the old version where it called:
        mt5_connector.init_mt5()
        mt5_connector.fetch_historical_ticks()
        mt5_connector.stream_live_ticks()
        mt5_connector.shutdown_mt5()
    """

    init_mt5 = staticmethod(init_mt5)
    shutdown_mt5 = staticmethod(shutdown_mt5)
    fetch_historical_ticks = staticmethod(fetch_historical_ticks)
    stream_live_ticks = staticmethod(stream_live_ticks)


mt5_connector = _MT5ConnectorFacade()


# =============================================================================
# Strategy Loader
# =============================================================================

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
            available = [key for key in dir(module) if not key.startswith("_")]
            return None, f"Class '{class_name}' not found. Available: {available}"

        instance = klass()

        if not hasattr(instance, "on_bar"):
            return None, f"Class '{class_name}' has no on_bar() method."

        print(f"[LOADER] Strategy loaded: {class_name} (id={strategy_id})")
        return instance, None

    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[LOADER] Failed to load strategy: {exc}\n{tb}")
        return None, f"{type(exc).__name__}: {exc}"


def _ensure_base_importable():
    """
    Make BaseStrategy importable under common import paths.

    Supported strategy imports:
        from base_strategy import BaseStrategy
        from worker.base_strategy import BaseStrategy
        from backend.strategies.base import BaseStrategy

    Since this is now combined into worker/mainWorker.py, all paths point
    to this current module.
    """
    current_module = sys.modules[__name__]

    # Direct old local import path
    sys.modules["base_strategy"] = current_module

    # Worker package old import path
    sys.modules["worker.base_strategy"] = current_module

    # Backend-style import path used by uploaded strategies
    if "backend" not in sys.modules:
        backend_module = types.ModuleType("backend")
        backend_module.__path__ = []
        sys.modules["backend"] = backend_module

    if "backend.strategies" not in sys.modules:
        strategies_module = types.ModuleType("backend.strategies")
        strategies_module.__path__ = []
        sys.modules["backend.strategies"] = strategies_module

    sys.modules["backend.strategies.base"] = current_module


# =============================================================================
# Strategy Runner
# =============================================================================

class StrategyRunner:
    """
    Full lifecycle runner for a single deployment on a worker.

    Phases:
        1. load strategy from source
        2. init MT5
        3. fetch historical ticks and generate initial bars
        4. warm up strategy
        5. live loop
    """

    def __init__(self, deployment_config: dict, status_callback=None):
        self.config = deployment_config
        self._status_callback = status_callback

        self.deployment_id: str = deployment_config["deployment_id"]
        self.strategy_id: str = deployment_config["strategy_id"]
        self.class_name: str = deployment_config.get("strategy_class_name", "")
        self.source_code: str = deployment_config.get("strategy_file_content", "")
        self.symbol: str = deployment_config["symbol"]
        self.tick_lookback_value: int = deployment_config.get("tick_lookback_value", 30)
        self.tick_lookback_unit: str = deployment_config.get(
            "tick_lookback_unit",
            "minutes",
        )
        self.bar_size_points: float = deployment_config["bar_size_points"]
        self.max_bars: int = deployment_config.get("max_bars_in_memory", 500)
        self.lot_size: float = deployment_config.get("lot_size", 0.01)
        self.strategy_parameters: dict = deployment_config.get(
            "strategy_parameters",
            {},
        )

        self._strategy = None
        self._ctx: Optional[StrategyContext] = None
        self._bar_engine: Optional[RangeBarEngine] = None
        self._runner_state: str = "idle"
        self._last_signal: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._started_at: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._bar_index: int = 0

    # -------------------------------------------------------------------------
    # Status Reporting
    # -------------------------------------------------------------------------

    def _report_status(self):
        """Push current runner status via callback."""
        if not self._status_callback:
            return

        status = {
            "deployment_id": self.deployment_id,
            "strategy_id": self.strategy_id,
            "strategy_name": getattr(self._strategy, "name", None)
            if self._strategy
            else None,
            "symbol": self.symbol,
            "runner_state": self._runner_state,
            "bar_size_points": self.bar_size_points,
            "max_bars_in_memory": self.max_bars,
            "current_bars_count": self._bar_engine.current_bars_count
            if self._bar_engine
            else 0,
            "last_signal": self._last_signal,
            "last_error": self._last_error,
            "started_at": self._started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self._status_callback(status)
        except Exception as exc:
            print(f"[RUNNER] Status report failed: {exc}")

    def _set_state(self, state: str, error: str = None):
        self._runner_state = state

        if error:
            self._last_error = error

        print(
            f"[RUNNER] {self.deployment_id} → {state}"
            + (f" (error: {error})" if error else "")
        )

        self._report_status()

    # -------------------------------------------------------------------------
    # Bar Callback
    # -------------------------------------------------------------------------

    def _on_new_bar(self, bar: dict):
        """Called by RangeBarEngine when a bar completes."""
        if self._stop_event.is_set():
            return

        if self._strategy is None or self._ctx is None:
            return

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list
        self._ctx.index = len(bars_list) - 1
        self._bar_index = self._ctx.index

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        if self._ctx.index < min_lb:
            return

        try:
            signal = self._strategy.on_bar(self._ctx)
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[RUNNER] on_bar() error: {exc}\n{tb}")
            self._set_state("failed", f"on_bar error: {exc}")
            self._stop_event.set()
            return

        self._handle_signal(signal)

    def _handle_signal(self, signal: Optional[dict]):
        """Process signal returned by strategy."""
        if signal is None:
            return

        action = signal.get("signal")

        if action not in VALID_SIGNALS:
            print(f"[RUNNER] Invalid signal: {action}")
            return

        if action == SIGNAL_HOLD:
            if "update_sl" in signal or "update_tp" in signal:
                self._last_signal = signal
                print(f"[RUNNER] SL/TP update: {signal}")
            return

        self._last_signal = signal
        print(
            f"[RUNNER] Signal: {action} | "
            f"symbol={self.symbol} | details={signal}"
        )

        if action in (SIGNAL_BUY, SIGNAL_SELL):
            print(
                f"[RUNNER] {action} signal detected. "
                "Execution layer not implemented — signal logged only."
            )
        elif action == SIGNAL_CLOSE:
            print(
                "[RUNNER] CLOSE signal detected. "
                "Execution layer not implemented — signal logged only."
            )

        self._report_status()

    # -------------------------------------------------------------------------
    # Main Lifecycle
    # -------------------------------------------------------------------------

    def start(self):
        """Start runner in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the runner to stop."""
        self._stop_event.set()
        self._set_state("stopped")

        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        """Full lifecycle: load → ticks → bars → live loop."""
        self._started_at = datetime.now(timezone.utc).isoformat()

        # Phase 1: Load Strategy
        self._set_state("loading_strategy")

        strategy_instance, load_error = load_strategy_from_source(
            self.source_code,
            self.class_name,
            self.strategy_id,
        )

        if load_error:
            self._set_state("failed", f"Strategy load failed: {load_error}")
            return

        self._strategy = strategy_instance

        params = self._strategy.validate_parameters(self.strategy_parameters)

        self._ctx = StrategyContext(bars=[], params=params)

        try:
            self._strategy.on_init(self._ctx)
        except Exception as exc:
            self._set_state("failed", f"on_init() failed: {exc}")
            return

        # Phase 2: Init MT5
        ok, msg = mt5_connector.init_mt5()

        if not ok:
            self._set_state("failed", f"MT5 init failed: {msg}")
            return

        # Phase 3: Fetch Historical Ticks
        self._set_state("fetching_ticks")

        ticks, tick_err = mt5_connector.fetch_historical_ticks(
            self.symbol,
            self.tick_lookback_value,
            self.tick_lookback_unit,
        )

        if ticks is None:
            self._set_state("failed", f"Tick fetch failed: {tick_err}")
            mt5_connector.shutdown_mt5()
            return

        if len(ticks) == 0:
            self._set_state("failed", "No ticks returned from MT5.")
            mt5_connector.shutdown_mt5()
            return

        print(f"[RUNNER] Fetched {len(ticks)} historical ticks for {self.symbol}")

        # Phase 4: Generate Initial Bars
        self._set_state("generating_initial_bars")

        self._bar_engine = RangeBarEngine(
            bar_size_points=self.bar_size_points,
            max_bars=self.max_bars,
            on_bar=None,
        )

        for tick in ticks:
            self._bar_engine.process_tick(
                tick["ts"],
                tick["price"],
                tick["volume"],
            )

        initial_count = self._bar_engine.current_bars_count

        print(
            f"[RUNNER] Initial bars generated: {initial_count} "
            f"(from {len(ticks)} ticks)"
        )

        if initial_count == 0:
            self._set_state(
                "failed",
                "No bars generated from historical ticks. Check bar_size_points.",
            )
            mt5_connector.shutdown_mt5()
            return

        # Phase 5: Warm Up Strategy
        self._set_state("warming_up")

        bars_list = list(self._bar_engine.bars)
        self._ctx._bars = bars_list

        min_lb = getattr(self._strategy, "min_lookback", 0) or 0

        for i in range(len(bars_list)):
            if self._stop_event.is_set():
                return

            self._ctx.index = i
            self._bar_index = i

            if i < min_lb:
                continue

            try:
                signal = self._strategy.on_bar(self._ctx)

                if signal and signal.get("signal") in (
                    SIGNAL_BUY,
                    SIGNAL_SELL,
                    SIGNAL_CLOSE,
                ):
                    print(
                        f"[RUNNER] Warmup signal at bar {i}: "
                        f"{signal.get('signal')} (not acted upon)"
                    )
            except Exception as exc:
                print(f"[RUNNER] Warmup on_bar error at bar {i}: {exc}")

        print("[RUNNER] Warmup complete. Strategy ready.")

        # Phase 6: Live Tick Loop
        self._set_state("running")

        self._bar_engine._on_bar = self._on_new_bar

        try:
            for tick in mt5_connector.stream_live_ticks(self.symbol):
                if self._stop_event.is_set():
                    break

                self._bar_engine.process_tick(
                    tick["ts"],
                    tick["price"],
                    tick["volume"],
                )

        except Exception as exc:
            if not self._stop_event.is_set():
                tb = traceback.format_exc()
                print(f"[RUNNER] Live loop error: {exc}\n{tb}")
                self._set_state("failed", f"Live loop error: {exc}")

        finally:
            mt5_connector.shutdown_mt5()

            if not self._stop_event.is_set():
                self._set_state("stopped")
```
