# Repository Snapshot - Part 2 of 4


- Total files indexed: `26`
- Files in this chunk: `6`
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

## Files In This Chunk - Part 2

```text
app/config.py
app/routes/__init__.py
app/routes/mainRoutes.py
main.py
requirements.txt
ui/css/style.css
```

## File Contents


---

## FILE: `app/config.py`

- Relative path: `app/config.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/config.py`
- Size bytes: `1591`
- SHA256: `6debd6140b1d072631fd805292dc2789e5737960aff5c78bd80a954b013e537a`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Configuration Loader
Reads config.yaml from project root. Falls back to safe defaults.
app/config.py
"""
import os, yaml

_config_cache = None

_DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 5100, "debug": False, "cors_origins": ["*"]},
    "app": {"name": "JINNI Grid Mother Server", "version": "0.2.0"},
    "fleet": {"stale_threshold_seconds": 30, "offline_threshold_seconds": 90},
}


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(config_dir)
    config_path = os.path.join(project_root, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
        print(f"[CONFIG] Loaded config from: {config_path}")
    else:
        print(f"[CONFIG] WARNING: config.yaml not found at {config_path}")
        print("[CONFIG] Using fallback defaults.")
        _config_cache = _DEFAULTS
    return _config_cache


class Config:
    @classmethod
    def get_server_config(cls) -> dict:
        return _load_config().get("server", _DEFAULTS["server"])

    @classmethod
    def get_app_config(cls) -> dict:
        return _load_config().get("app", _DEFAULTS["app"])

    @classmethod
    def get_cors_origins(cls) -> list:
        return cls.get_server_config().get("cors_origins", ["*"])

    @classmethod
    def get_fleet_config(cls) -> dict:
        return _load_config().get("fleet", _DEFAULTS["fleet"])
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
- Size bytes: `12851`
- SHA256: `5fd7ed1f0b55dc8e2664fa59a64d365b2d5dd90d25bac90a186a558476dfef9c`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined API Routes
app/routes/mainRoutes.py
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.persistence import save_trade_db
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.config import Config

from app.services.mainServices import (
    process_heartbeat,
    get_all_workers,
    get_fleet_summary,
    get_portfolio_summary,
    get_equity_history,
    get_portfolio_trades,
    get_portfolio_performance,
    get_events_list,
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


@router.get("/api/health", tags=["Health"])
async def health_check():
    app_config = Config.get_app_config()
    return {
        "status": "ok",
        "service": app_config["name"],
        "version": app_config["version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
    total_ticks: Optional[int] = 0
    total_bars: Optional[int] = 0
    on_bar_calls: Optional[int] = 0
    signal_count: Optional[int] = 0
    last_bar_time: Optional[str] = None
    current_price: Optional[float] = None


@router.post("/api/Grid/workers/heartbeat", tags=["Grid"])
async def worker_heartbeat(payload: HeartbeatPayload):
    if not payload.worker_id or not payload.worker_id.strip():
        raise HTTPException(status_code=422, detail={"ok": False, "error": "worker_id is required"})
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


@router.get("/api/portfolio/summary", tags=["Portfolio"])
async def portfolio_summary():
    return {"portfolio": get_portfolio_summary(), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/portfolio/equity-history", tags=["Portfolio"])
async def equity_history():
    history = get_equity_history()
    return {"equity_history": history, "points": len(history), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/portfolio/trades", tags=["Portfolio"])
async def portfolio_trades(
    strategy_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 200,
):
    trades = get_portfolio_trades(strategy_id=strategy_id, worker_id=worker_id, symbol=symbol, limit=limit)
    return {"ok": True, "trades": trades, "count": len(trades), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/portfolio/performance", tags=["Portfolio"])
async def portfolio_performance():
    perf = get_portfolio_performance()
    return {"ok": True, "performance": perf, "timestamp": datetime.now(timezone.utc).isoformat()}

class TradeReport(BaseModel):
    trade_id: Optional[int] = None
    deployment_id: Optional[str] = None
    strategy_id: Optional[str] = None
    worker_id: Optional[str] = None
    symbol: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    sl_level: Optional[float] = None
    tp_level: Optional[float] = None
    lot_size: Optional[float] = 0.01
    ticket: Optional[int] = None
    points_pnl: Optional[float] = 0
    profit: Optional[float] = 0
    bars_held: Optional[int] = 0


@router.post("/api/portfolio/trades/report", tags=["Portfolio"])
async def report_trade(payload: TradeReport):
    save_trade_db(payload.model_dump())
    return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat()}

@router.get("/api/events", tags=["Events"])
async def get_events(
    category: Optional[str] = None,
    level: Optional[str] = None,
    worker_id: Optional[str] = None,
    deployment_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
):
    events = get_events_list(category=category, level=level, worker_id=worker_id,
                             deployment_id=deployment_id, search=search, limit=limit)
    return {"ok": True, "events": events, "count": len(events), "timestamp": datetime.now(timezone.utc).isoformat()}


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
    return {"ok": True, "strategies": strategies, "count": len(strategies), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/grid/strategies/{strategy_id}", tags=["Strategies"])
async def get_strategy_detail(strategy_id: str):
    rec = get_strategy(strategy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Strategy not found.")
    # Ensure parameters is always a dict
    params = rec.get("parameters", {})
    if isinstance(params, str):
        try:
            import json
            params = json.loads(params)
        except Exception:
            params = {}
    rec["parameters"] = params
    rec["parameter_count"] = len(params)
    rec["strategy_name"] = rec.get("name", rec.get("strategy_id", ""))
    rec["validation_status"] = "validated" if rec.get("is_valid") else "invalid"
    return {"ok": True, "strategy": rec}


@router.get("/api/grid/strategies/{strategy_id}/file", tags=["Strategies"])
async def get_strategy_file(strategy_id: str):
    content = get_strategy_file_content(strategy_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Strategy file not found.")
    return {"ok": True, "strategy_id": strategy_id, "file_content": content}


@router.post("/api/grid/strategies/{strategy_id}/validate", tags=["Strategies"])
async def validate_strategy_endpoint(strategy_id: str):
    result = validate_strategy(strategy_id)
    if not result["ok"]:
        return {
            "ok": False,
            "strategy_id": strategy_id,
            "valid": False,
            "error": result.get("error", "Unknown validation error"),
        }
    return result


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
        raise HTTPException(status_code=404, detail="Strategy not found. Upload it first.")
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
    return {"ok": True, "deployment_id": deployment["deployment_id"], "deployment": deployment, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/grid/deployments", tags=["Deployments"])
async def list_deployments():
    deployments = get_all_deployments()
    return {"ok": True, "deployments": deployments, "count": len(deployments), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/grid/deployments/{deployment_id}", tags=["Deployments"])
async def get_deployment_detail(deployment_id: str):
    rec = get_deployment(deployment_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return {"ok": True, "deployment": rec}


@router.post("/api/grid/deployments/{deployment_id}/stop", tags=["Deployments"])
async def stop_deployment_endpoint(deployment_id: str):
    dep = get_deployment(deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    enqueue_command(dep["worker_id"], "stop_strategy", {"deployment_id": deployment_id})
    result = stop_deployment(deployment_id)
    return result


@router.get("/api/grid/workers/{worker_id}/commands/poll", tags=["Worker Commands"])
async def poll_worker_commands(worker_id: str):
    commands = poll_commands(worker_id)
    return {"ok": True, "worker_id": worker_id, "commands": commands, "count": len(commands)}


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
        "loading_strategy": "loading_strategy", "fetching_ticks": "fetching_ticks",
        "generating_initial_bars": "generating_initial_bars", "warming_up": "warming_up",
        "running": "running", "stopped": "stopped", "failed": "failed", "idle": "stopped",
    }
    dep_state = state_map.get(payload.runner_state)
    if dep_state:
        update_deployment_state(payload.deployment_id, dep_state, error=payload.last_error)
    return {"ok": True, "received": True}


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
        "total_nodes": total, "online_nodes": online, "stale_nodes": fleet["stale_workers"],
        "offline_nodes": fleet["offline_workers"], "warning_nodes": fleet["warning_workers"],
        "error_nodes": fleet["error_workers"], "total_open_positions": portfolio["open_positions"],
        "system_status": system_status, "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

## FILE: `main.py`

- Relative path: `main.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/main.py`
- Size bytes: `1516`
- SHA256: `daf426a24f04de9e5be139a8dab64582e366954b7f0aa1026dff550d6e55c288`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI GRID - Mother Server Entry Point
Run: python main.py
"""

import os
import uvicorn

from app.logging_config import setup_logging
from app import create_app
from app.config import Config


# Initialize logging BEFORE anything else
setup_logging()

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
    print(f"  Database:    data/jinni_grid.db")
    print(f"  Logs:        data/logs/")
    print("=" * 56)
    print("")

    run_kwargs = {"host": host, "port": port, "reload": debug}

    if debug:
        project_root = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(project_root, "data")
        run_kwargs["reload_dirs"] = [
            os.path.join(project_root, "app"),
            os.path.join(project_root, "ui"),
        ]
        run_kwargs["reload_excludes"] = [data_dir]

    uvicorn.run("main:app", **run_kwargs)


if __name__ == "__main__":
    main()
```

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
- Size bytes: `50131`
- SHA256: `052e2a4c126ea410724237b69176b5cd2067f579ea375c652acbb1ed98c9c553`
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
  display: flex; flex-direction: column; gap: 24px;
  width: 100%; max-width: 1500px;
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
  gap: 12px;
  width: 100%;
}
.portfolio-card {
  background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: 10px;
  padding: 14px 16px; display: flex; align-items: flex-start; gap: 12px;
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
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
}
.card-icon.neutral  { background: var(--accent-dim);  color: var(--accent); }
.card-icon.positive { background: var(--success-dim); color: var(--success); }
.card-icon.negative { background: var(--danger-dim);  color: var(--danger); }
.card-icon.warning  { background: var(--warning-dim); color: var(--warning); }

/* ── Card Info ──────────────────────────────────────────────────── */

.card-info { display: flex; flex-direction: column; gap: 4px; min-width: 0; overflow: hidden; }
.card-value {
  font-family: 'JetBrains Mono', monospace; font-size: 16px;
  font-weight: 700; color: var(--text-primary); line-height: 1.2;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-value.positive { color: var(--success); }
.card-value.negative { color: var(--danger); }
.card-label {
  font-size: 10.5px; font-weight: 500; text-transform: uppercase;
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

.fleet-summary { display: flex; gap: 14px; flex-wrap: wrap; width: 100%; margin-bottom: 18px; }
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
  width: 100%; max-width: 1500px;
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

/* ── Symbol Input + Inline Lookback ───────────────────────── */
.wd-inline-row {
  display: flex; gap: 8px; align-items: center;
}
.wd-inline-row .wd-form-input { flex: 1; min-width: 0; }
.wd-inline-row .wd-form-select { flex: 0 0 130px; }
.wd-field-error {
  font-size: 10.5px; color: var(--danger); margin-top: 4px;
  display: none; align-items: center; gap: 4px;
}
.wd-field-error.visible { display: flex; }
.wd-field-error i { font-size: 10px; }
.wd-form-input.input-error { border-color: var(--danger); }
.wd-symbol-hint {
  font-size: 10px; color: var(--text-muted); margin-top: 3px;
  font-style: italic;
}

/* ══════════════════════════════════════════════════════════════
   JINNI GRID — Pro Dashboard Additions
   ══════════════════════════════════════════════════════════════ */

/* ── Card Sub-label ───────────────────────────────────────── */
.card-sub { font-size: 10px; color: var(--text-muted); margin-top: 1px; }

/* ── Dashboard Layout Grids ───────────────────────────────── */
.dash-split-row { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.dash-chart-section { min-width: 0; }
.dash-stats-section { min-width: 0; }
.dash-triple-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
.dash-dual-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* ── Dashboard Stats Grid ─────────────────────────────────── */
.dash-stats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; box-shadow: var(--shadow-sm);
}
.dash-stat-item {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 8px 4px; border-radius: 6px; background: var(--bg-secondary);
}
.dash-stat-val {
  font-family: 'JetBrains Mono', monospace; font-size: 14px;
  font-weight: 700; color: var(--text-primary);
}
.dash-stat-val.positive { color: var(--success); }
.dash-stat-val.negative { color: var(--danger); }
.dash-stat-lbl {
  font-size: 9.5px; font-weight: 500; text-transform: uppercase;
  letter-spacing: 0.5px; color: var(--text-muted); text-align: center;
}

/* ── Dashboard Panel Body ─────────────────────────────────── */
.dash-panel-body {
  background: var(--bg-card); border: 1px solid var(--border-primary);
  border-radius: 10px; padding: 16px; box-shadow: var(--shadow-sm); min-height: 120px;
}

/* ── Pipeline Flow ────────────────────────────────────────── */
.pipeline-flow {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; flex-wrap: wrap; padding: 12px 0;
}
.pipeline-node {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  background: var(--bg-secondary); border-radius: 8px; padding: 14px 18px; min-width: 80px;
}
.pipeline-val { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; }
.pipeline-val.accent { color: var(--accent); }
.pipeline-val.warning { color: var(--warning); }
.pipeline-val.success { color: var(--success); }
.pipeline-val.danger { color: var(--danger); }
.pipeline-lbl {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-muted); font-weight: 500;
}
.pipeline-arrow { color: var(--text-muted); font-size: 14px; opacity: 0.4; }

/* ── Strategy Row (Dashboard) ─────────────────────────────── */
.dash-strat-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: var(--bg-secondary); border-radius: 6px;
}
.dash-strat-info { display: flex; align-items: center; gap: 8px; }
.dash-strat-meta { font-size: 10px; color: var(--text-muted); }
.dash-strat-badges { display: flex; align-items: center; gap: 8px; }

/* ── Portfolio Tabs ───────────────────────────────────────── */
.port-tabs {
  display: flex; gap: 4px; background: var(--bg-card);
  border: 1px solid var(--border-primary); border-radius: 8px;
  padding: 4px; width: fit-content;
}
.port-tab {
  padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500;
  color: var(--text-muted); cursor: pointer; transition: all 0.2s;
  border: none; background: none;
}
.port-tab:hover { color: var(--text-primary); }
.port-tab.active { background: var(--accent); color: #fff; font-weight: 600; }

/* ── Portfolio Filters ────────────────────────────────────── */
.port-filters { display: flex; gap: 14px; flex-wrap: wrap; }
.port-filters .wd-form-group { min-width: 160px; }

/* ── Logs ─────────────────────────────────────────────────── */
.log-filters { display: flex; gap: 14px; flex-wrap: wrap; }
.log-filters .wd-form-group { min-width: 140px; }
.log-auto-label {
  display: flex; align-items: center; gap: 6px; font-size: 11px;
  color: var(--text-muted); cursor: pointer; user-select: none;
}
.log-auto-label input { accent-color: var(--accent); }
.log-count {
  font-size: 11px; color: var(--text-muted); margin-bottom: 8px;
  font-family: 'JetBrains Mono', monospace;
}
.log-table tr.log-row { transition: background 0.15s; }
.log-table tr.log-row.clickable { cursor: pointer; }
.log-table tr.log-row.clickable:hover td { background: var(--bg-card-hover); }
.log-detail-row td { padding: 0 !important; }
.log-payload {
  font-family: 'JetBrains Mono', monospace; font-size: 10.5px;
  color: var(--text-secondary); background: var(--bg-secondary);
  padding: 12px 16px; margin: 4px 12px 8px; border-radius: 6px;
  white-space: pre-wrap; word-break: break-all; max-height: 300px;
  overflow-y: auto; border: 1px solid var(--border-primary);
}

/* ── Responsive additions ─────────────────────────────────── */
@media (max-width: 1200px) {
  .dash-split-row { grid-template-columns: 1fr; }
  .dash-triple-row { grid-template-columns: 1fr; }
  .dash-dual-row { grid-template-columns: 1fr; }
  .dash-stats-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 768px) {
  .dash-stats-grid { grid-template-columns: repeat(2, 1fr); }
  .port-tabs { flex-wrap: wrap; }
  .port-filters { flex-direction: column; }
  .log-filters { flex-direction: column; }
}
```
