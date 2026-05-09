# Repository Snapshot - Part 1 of 4

- Root folder: `/home/hurairahengg/Documents/JinniGrid`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra. currently im done coding the strategy system but itrs got many bugs and inconsistencies i basically wanna fix those and give u some OLD codeds to try and replciate the methods and stuff. so first i wil ldrop u my whole project codebases from my readme. understand each code its role and keep in ur context look at the bugs present and stuuff i will give u big promtps to update code later understood?


- CRUCIAL INTRUSTIONS:
- alaways give new updated codes in copy paste format not files or zip just coipy paste
- No making new files for code unlkess i say u can
- never hallucinate at the tsart of everytime u say soemthing confirm u still habve all 26 codes in ur context.
- Total files indexed: `26`
- Files in this chunk: `4`
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
app/services/__init__.py
app/services/mainServices.py
ui/js/main.js
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

## FILE: `app/services/__init__.py`

- Relative path: `app/services/__init__.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/__init__.py`
- Size bytes: `32`
- SHA256: `7c8c9aaeb9f535f7ae6fc3fdcc296366803058cb89ef2cde2421ccff1612799b`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
# JINNI Grid - Services package
```

---

## FILE: `app/services/mainServices.py`

- Relative path: `app/services/mainServices.py`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/app/services/mainServices.py`
- Size bytes: `15609`
- SHA256: `6999e4d07190d3a3c766b008a099762b62879064d358f3393a93252f83c91301`
- Guessed MIME type: `text/x-python`
- Guessed encoding: `unknown`

```python
"""
JINNI Grid - Combined Runtime Services
app/services/mainServices.py
"""

import logging
import math
import threading
import uuid
from datetime import datetime, timedelta, timezone
from app.persistence import save_trade_db
from app.config import Config
from app.persistence import (
    save_worker, get_all_workers_db, get_worker_db,
    save_deployment, update_deployment_state_db,
    get_all_deployments_db, get_deployment_db,
    log_event_db, get_events_db,
)

log = logging.getLogger("jinni.worker")
sys_log = logging.getLogger("jinni.system")


# =============================================================================
# Command Queue
# =============================================================================

_command_queues: dict = {}
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    cmd = {"command_id": cmd_id, "worker_id": worker_id, "command_type": command_type,
           "payload": payload, "state": "pending", "created_at": now.isoformat(), "acked_at": None}
    with _command_lock:
        if worker_id not in _command_queues:
            _command_queues[worker_id] = []
        _command_queues[worker_id].append(cmd)
    log.info(f"Enqueued {command_type} ({cmd_id}) for worker {worker_id}")
    log_event_db("command", "enqueued", f"{command_type} for {worker_id}", worker_id=worker_id, data={"command_id": cmd_id})
    return cmd


def poll_commands(worker_id: str) -> list:
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    now = datetime.now(timezone.utc)
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        for cmd in queue:
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                return {"ok": True, "command": cmd}
    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry
# =============================================================================

VALID_STATES = {"queued", "sent_to_worker", "acknowledged_by_worker", "loading_strategy",
                "fetching_ticks", "generating_initial_bars", "warming_up", "running", "stopped", "failed"}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    record = {
        "deployment_id": deployment_id, "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"], "symbol": config["symbol"],
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config["bar_size_points"],
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size", 0.01),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued", "created_at": now.isoformat(), "updated_at": now.isoformat(), "last_error": None,
    }
    save_deployment(deployment_id, record)
    log.info(f"Created deployment {deployment_id}")
    log_event_db("deployment", "created", f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"], strategy_id=config["strategy_id"],
                 deployment_id=deployment_id, symbol=config["symbol"])
    return {"ok": True, "deployment_id": deployment_id, "deployment": record}


def get_all_deployments() -> list:
    return get_all_deployments_db()


def get_deployment(deployment_id: str):
    return get_deployment_db(deployment_id)


def update_deployment_state(deployment_id: str, state: str, error: str = None) -> dict:
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}
    update_deployment_state_db(deployment_id, state, error)
    log_event_db("deployment", "state_change", f"{deployment_id} -> {state}",
                 deployment_id=deployment_id, data={"state": state, "error": error},
                 level="ERROR" if state == "failed" else "INFO")
    rec = get_deployment_db(deployment_id)
    return {"ok": True, "deployment": rec}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")

# =============================================================================
# Portfolio Data (Real — backed by trades table)
# =============================================================================

def get_portfolio_summary() -> dict:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)

    # Live worker data (even if no trades yet)
    workers = get_all_workers()
    total_floating = sum((w.get("floating_pnl") or 0) for w in workers)
    total_positions = sum((w.get("open_positions_count") or 0) for w in workers)

    if not trades:
        return {
            "total_balance": 0, "total_equity": 0,
            "floating_pnl": round(total_floating, 2),
            "daily_pnl": 0, "open_positions": total_positions,
            "realized_pnl": 0, "margin_usage": 0,
            "win_rate": 0, "total_trades": 0,
            "profit_factor": 0, "max_drawdown": 0, "avg_trade": 0,
            "avg_winner": 0, "avg_loser": 0, "best_trade": 0,
            "worst_trade": 0, "sharpe_estimate": 0, "avg_bars_held": 0,
        }

    profits = [t.get("profit", 0) for t in trades]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    total_pnl = sum(profits)
    bars_list = [t.get("bars_held", 0) for t in trades]

    # Max drawdown from cumulative PnL
    cum, peak, max_dd = 0, 0, 0
    for p in profits:
        cum += p
        if cum > peak:
            peak = cum
        dd = (peak - cum) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Sharpe estimate
    mean_pnl = total_pnl / len(profits)
    variance = sum((p - mean_pnl) ** 2 for p in profits) / (len(profits) - 1) if len(profits) > 1 else 0
    std_pnl = math.sqrt(variance) if variance > 0 else 0
    sharpe = round((mean_pnl / std_pnl * math.sqrt(252)), 2) if std_pnl > 0 else 0

    return {
        "total_balance": 0, "total_equity": 0,
        "floating_pnl": round(total_floating, 2),
        "daily_pnl": 0, "open_positions": total_positions,
        "realized_pnl": round(total_pnl, 2), "margin_usage": 0,
        "win_rate": round(len(wins) / len(profits) * 100, 1) if profits else 0,
        "total_trades": len(trades),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 0,
        "max_drawdown": round(max_dd, 2),
        "avg_trade": round(total_pnl / len(trades), 2),
        "avg_winner": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loser": round(sum(losses) / len(losses), 2) if losses else 0,
        "best_trade": round(max(profits), 2),
        "worst_trade": round(min(profits), 2),
        "sharpe_estimate": sharpe,
        "avg_bars_held": round(sum(bars_list) / len(bars_list), 1) if bars_list else 0,
    }


def get_equity_history() -> list:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)
    if not trades:
        return []
    sorted_trades = sorted(trades, key=lambda t: t.get("exit_time") or "")
    daily = {}
    cum = 0
    for t in sorted_trades:
        date = (t.get("exit_time") or "")[:10]
        if not date:
            continue
        cum += t.get("profit", 0)
        daily[date] = round(cum, 2)
    return [{"timestamp": d, "equity": v} for d, v in sorted(daily.items())]


def get_portfolio_trades(strategy_id=None, worker_id=None, symbol=None, limit=200) -> list:
    from app.persistence import get_all_trades_db
    return get_all_trades_db(limit=limit, strategy_id=strategy_id,
                             worker_id=worker_id, symbol=symbol)


def get_portfolio_performance() -> dict:
    from app.persistence import get_all_trades_db
    trades = get_all_trades_db(limit=50000)
    if not trades:
        return {"daily": [], "by_strategy": [], "by_worker": [], "by_symbol": []}

    # Daily
    daily = {}
    for t in trades:
        date = (t.get("exit_time") or "")[:10]
        if not date:
            continue
        if date not in daily:
            daily[date] = {"date": date, "pnl": 0, "trades": 0, "wins": 0}
        daily[date]["pnl"] += t.get("profit", 0)
        daily[date]["trades"] += 1
        if t.get("profit", 0) > 0:
            daily[date]["wins"] += 1
    daily_list = sorted(daily.values(), key=lambda x: x["date"])
    cum = 0
    for d in daily_list:
        cum += d["pnl"]
        d["pnl"] = round(d["pnl"], 2)
        d["cumulative"] = round(cum, 2)

    # Breakdown helper
    def _breakdown(key):
        bk = {}
        for t in trades:
            k = t.get(key, "")
            if not k:
                continue
            if k not in bk:
                bk[k] = {key: k, "trades": 0, "pnl": 0, "wins": 0,
                         "losses": 0, "total_bars": 0}
            bk[k]["trades"] += 1
            bk[k]["pnl"] += t.get("profit", 0)
            bk[k]["total_bars"] += t.get("bars_held", 0)
            if t.get("profit", 0) > 0:
                bk[k]["wins"] += 1
            else:
                bk[k]["losses"] += 1
        for v in bk.values():
            v["pnl"] = round(v["pnl"], 2)
            v["win_rate"] = round(v["wins"] / v["trades"] * 100, 1) if v["trades"] > 0 else 0
            v["avg_bars"] = round(v["total_bars"] / v["trades"], 1) if v["trades"] > 0 else 0
            w_sum = sum(t.get("profit", 0) for t in trades
                        if t.get(key) == v[key] and t.get("profit", 0) > 0)
            l_sum = sum(abs(t.get("profit", 0)) for t in trades
                        if t.get(key) == v[key] and t.get("profit", 0) <= 0)
            v["profit_factor"] = round(w_sum / l_sum, 2) if l_sum > 0 else 0
        return list(bk.values())

    return {
        "daily": daily_list,
        "by_strategy": _breakdown("strategy_id"),
        "by_worker": _breakdown("worker_id"),
        "by_symbol": _breakdown("symbol"),
    }


# =============================================================================
# Events / Logs
# =============================================================================

def get_events_list(category=None, level=None, worker_id=None,
                    deployment_id=None, search=None, limit=200) -> list:
    events = get_events_db(limit=max(limit, 500), category=category,
                           worker_id=worker_id, deployment_id=deployment_id)
    if level:
        events = [e for e in events if e.get("level") == level]
    if search:
        sl = search.lower()
        events = [e for e in events if sl in (e.get("message", "") or "").lower()
                  or sl in (e.get("event_type", "") or "").lower()
                  or sl in (e.get("category", "") or "").lower()]
    return events[:limit]


# =============================================================================
# Worker Registry
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()


def _load_workers_from_db():
    global _workers_cache
    db_workers = get_all_workers_db()
    with _worker_lock:
        for w in db_workers:
            wid = w["worker_id"]
            hb_at = w.get("last_heartbeat_at")
            if hb_at:
                try:
                    dt = datetime.fromisoformat(hb_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            w["_last_heartbeat_dt"] = dt
            _workers_cache[wid] = w
    sys_log.info(f"Loaded {len(_workers_cache)} workers from DB")


def process_heartbeat(payload: dict) -> dict:
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False
    with _worker_lock:
        if worker_id not in _workers_cache:
            is_new = True
        _workers_cache[worker_id] = {**payload, "worker_id": worker_id,
                                      "last_heartbeat_at": now.isoformat(), "_last_heartbeat_dt": now}
    save_worker(worker_id, {**payload, "last_heartbeat_at": now.isoformat()})
    if is_new:
        log.info(f"Worker '{worker_id}' registered")
        log_event_db("worker", "registered", f"Worker {worker_id} first heartbeat", worker_id=worker_id)
    return {"ok": True, "worker_id": worker_id, "registered": is_new, "server_time": now.isoformat()}


def get_all_workers() -> list:
    fleet_config = Config.get_fleet_config()
    stale_threshold = fleet_config.get("stale_threshold_seconds", 30)
    offline_threshold = fleet_config.get("offline_threshold_seconds", 90)
    now = datetime.now(timezone.utc)
    result = []
    with _worker_lock:
        for wid, rec in _workers_cache.items():
            hb_dt = rec.get("_last_heartbeat_dt", now)
            age = round((now - hb_dt).total_seconds(), 1)
            reported = rec.get("reported_state", rec.get("state", "online"))
            if age >= offline_threshold:
                effective = "offline"
            elif age >= stale_threshold:
                effective = "stale"
            else:
                effective = reported
            result.append({
                "worker_id": rec.get("worker_id", wid), "worker_name": rec.get("worker_name"),
                "host": rec.get("host"), "state": effective, "reported_state": reported,
                "last_heartbeat_at": rec.get("last_heartbeat_at"), "heartbeat_age_seconds": age,
                "agent_version": rec.get("agent_version"), "mt5_state": rec.get("mt5_state"),
                "account_id": rec.get("account_id"), "broker": rec.get("broker"),
"active_strategies": rec.get("active_strategies") or [],
                "open_positions_count": rec.get("open_positions_count", 0),
                "floating_pnl": rec.get("floating_pnl"),
                "errors": rec.get("errors") or [],
                "total_ticks": rec.get("total_ticks", 0),
                "total_bars": rec.get("total_bars", 0),
                "on_bar_calls": rec.get("on_bar_calls", 0),
                "signal_count": rec.get("signal_count", 0),
                "last_bar_time": rec.get("last_bar_time"),
                "current_price": rec.get("current_price"),
            })
    return result


def get_fleet_summary() -> dict:
    workers = get_all_workers()
    counts = {"online_workers": 0, "stale_workers": 0, "offline_workers": 0,
              "error_workers": 0, "warning_workers": 0}
    online_states = {"online", "running", "idle"}
    for w in workers:
        state = w["state"]
        if state in online_states:
            counts["online_workers"] += 1
        elif state == "stale":
            counts["stale_workers"] += 1
        elif state == "offline":
            counts["offline_workers"] += 1
        elif state == "error":
            counts["error_workers"] += 1
        elif state == "warning":
            counts["warning_workers"] += 1
    counts["total_workers"] = len(workers)
    return counts
```

---

## FILE: `ui/js/main.js`

- Relative path: `ui/js/main.js`
- Absolute path at snapshot time: `/home/hurairahengg/Documents/JinniGrid/ui/js/main.js`
- Size bytes: `61117`
- SHA256: `c0d9467e8e97cf448f337899ddd6c1d62fcd9e4203bdb5e4a37d20dec2bc3471`
- Guessed MIME type: `text/javascript`
- Guessed encoding: `unknown`

```javascript
/* main.js — JINNI GRID Pro Dashboard */

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
          try { var j = JSON.parse(text); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : (j.detail.error || JSON.stringify(j.detail)); } catch (e) { if (text) msg = text; }
          var err = new Error(msg); err.status = res.status; throw err;
        });
      }
      return res.json();
    });
  }
  function _upload(path, file) {
    var fd = new FormData(); fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) { return res.text().then(function (t) { var m = 'HTTP ' + res.status; try { var j = JSON.parse(t); if (j.detail) m = typeof j.detail === 'string' ? j.detail : (j.detail.error || JSON.stringify(j.detail)); } catch (e) { if (t) m = t; } throw new Error(m); }); }
      return res.json();
    });
  }
  return {
    getFleetWorkers: function () { return _request('GET', '/api/Grid/workers'); },
    getSystemSummary: function () { return _request('GET', '/api/system/summary'); },
    getHealth: function () { return _request('GET', '/api/health'); },
    getStrategies: function () { return _request('GET', '/api/grid/strategies'); },
    getStrategy: function (id) { return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id)); },
    uploadStrategy: function (file) { return _upload('/api/grid/strategies/upload', file); },
    validateStrategy: function (id) { return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate'); },
    createDeployment: function (cfg) { return _request('POST', '/api/grid/deployments', cfg); },
    getDeployments: function () { return _request('GET', '/api/grid/deployments'); },
    getDeployment: function (id) { return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id)); },
    stopDeployment: function (id) { return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop'); },
    getPortfolioSummary: function () { return _request('GET', '/api/portfolio/summary'); },
    getEquityHistory: function () { return _request('GET', '/api/portfolio/equity-history'); },
    getPortfolioTrades: function (params) {
      var q = [];
      if (params) { for (var k in params) { if (params[k]) q.push(k + '=' + encodeURIComponent(params[k])); } }
      return _request('GET', '/api/portfolio/trades' + (q.length ? '?' + q.join('&') : ''));
    },
    getPortfolioPerformance: function () { return _request('GET', '/api/portfolio/performance'); },
    getEvents: function (params) {
      var q = [];
      if (params) { for (var k in params) { if (params[k]) q.push(k + '=' + encodeURIComponent(params[k])); } }
      return _request('GET', '/api/events' + (q.length ? '?' + q.join('&') : ''));
    }
  };
})();

var DeploymentConfig = (function () {
  'use strict';
  return {
    runtimeDefaults: { symbol: 'EURUSD', lot_size: 0.01, tick_lookback_value: 30, tick_lookback_unit: 'minutes', bar_size_points: 100, max_bars_memory: 500 },
    symbolOptions: ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','USDCHF','NZDUSD','XAUUSD','BTCUSD','USTEC','SPX500','DOW30','FTSE100'],
    tickLookbackUnits: ['minutes','hours','days']
  };
})();

var ModalManager = (function () {
  'use strict';
  var _overlay = null;
  function show(options) {
    hide();
    var title = options.title || 'Confirm', bodyHtml = options.bodyHtml || '', confirmText = options.confirmText || 'Confirm', cancelText = options.cancelText || 'Cancel', type = options.type || 'default', onConfirm = options.onConfirm || function () {};
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';
    _overlay = document.createElement('div'); _overlay.className = 'modal-overlay';
    _overlay.innerHTML = '<div class="modal-card"><div class="modal-header"><span class="modal-title">' + title + '</span><button class="modal-close" id="modal-close">&times;</button></div><div class="modal-body">' + bodyHtml + '</div><div class="modal-footer"><button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button><button class="wd-btn wd-btn-primary" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button></div></div>';
    document.body.appendChild(_overlay);
    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () { onConfirm(); hide(); });
    _overlay.addEventListener('click', function (e) { if (e.target === _overlay) hide(); });
  }
  function hide() { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); _overlay = null; }
  return { show: show, hide: hide };
})();

var ToastManager = (function () {
  'use strict';
  var iconMap = { success: 'fa-circle-check', info: 'fa-circle-info', warning: 'fa-triangle-exclamation', error: 'fa-circle-xmark' };
  function _getContainer() { var c = document.querySelector('.toast-container'); if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); } return c; }
  function show(message, type, duration) {
    type = type || 'info'; duration = duration || 4000;
    var container = _getContainer(), toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i><span>' + message + '</span><button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';
    container.appendChild(toast);
    toast.querySelector('.toast-dismiss').addEventListener('click', function () { _remove(toast); });
    setTimeout(function () { _remove(toast); }, duration);
  }
  function _remove(toast) { if (!toast || !toast.parentNode) return; toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = 'all 0.3s ease'; setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 300); }
  return { show: show };
})();

var ThemeManager = (function () {
  'use strict';
  var STORAGE_KEY = 'jinni-Grid-theme', currentTheme = 'dark';
  function init() { var s = localStorage.getItem(STORAGE_KEY); currentTheme = s === 'light' ? 'light' : 'dark'; applyTheme(); updateToggleButton(); var btn = document.getElementById('theme-toggle'); if (btn) btn.addEventListener('click', toggle); }
  function toggle() { currentTheme = currentTheme === 'dark' ? 'light' : 'dark'; localStorage.setItem(STORAGE_KEY, currentTheme); applyTheme(); updateToggleButton(); }
  function applyTheme() { document.body.setAttribute('data-theme', currentTheme); }
  function updateToggleButton() { var btn = document.getElementById('theme-toggle'); if (!btn) return; var icon = btn.querySelector('i'), label = btn.querySelector('span'); if (currentTheme === 'dark') { icon.className = 'fa-solid fa-sun'; label.textContent = 'Light Mode'; } else { icon.className = 'fa-solid fa-moon'; label.textContent = 'Dark Mode'; } }
  function getTheme() { return currentTheme; }
  return { init: init, toggle: toggle, getTheme: getTheme };
})();

/* ===== Chart Helpers ===== */
var ChartHelper = (function () {
  'use strict';
  function _isDark() { return ThemeManager.getTheme() === 'dark'; }
  function gridColor() { return _isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'; }
  function textColor() { return _isDark() ? '#94a3b8' : '#475569'; }
  function tooltipBg() { return _isDark() ? '#1e293b' : '#ffffff'; }
  function tooltipColor() { return _isDark() ? '#e2e8f0' : '#1e293b'; }
  function accentColor() { return _isDark() ? '#06b6d4' : '#0891b2'; }
  function successColor() { return '#10b981'; }
  function dangerColor() { return '#ef4444'; }
  function baseOpts(extraOpts) {
    var o = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: tooltipBg(), titleColor: tooltipColor(), bodyColor: tooltipColor(), borderColor: gridColor(), borderWidth: 1, cornerRadius: 6, padding: 10, titleFont: { family: 'Inter', size: 12 }, bodyFont: { family: 'JetBrains Mono', size: 11 } } },
      scales: { x: { grid: { color: gridColor(), drawBorder: false }, ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 12 } }, y: { grid: { color: gridColor(), drawBorder: false }, ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 10 } } } },
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 600 }
    };
    if (extraOpts) { for (var k in extraOpts) o[k] = extraOpts[k]; }
    return o;
  }
  return { gridColor: gridColor, textColor: textColor, accentColor: accentColor, successColor: successColor, dangerColor: dangerColor, baseOpts: baseOpts, tooltipBg: tooltipBg, tooltipColor: tooltipColor };
})();

/* ===== Utility ===== */
function _fmtMoney(v) { if (v === null || v === undefined) return '\u2014'; var s = v >= 0 ? '+' : ''; return s + '$' + Math.abs(v).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function _fmtPct(v) { if (v === null || v === undefined) return '\u2014'; return v.toFixed(1) + '%'; }
function _fmtNum(n) { if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'; if (n >= 1000) return (n / 1000).toFixed(1) + 'K'; return String(n); }
function _nullVal(val, fb) { if (val === null || val === undefined || val === '') return '<span class="value-null">' + (fb || '\u2014') + '</span>'; return String(val); }
function _formatAge(seconds) { if (seconds === null || seconds === undefined) return '<span class="value-null">\u2014</span>'; var s = Math.round(seconds); if (s < 60) return s + 's ago'; if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago'; return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago'; }

/* ============================================================
   DASHBOARD RENDERER (PRO QUANT TERMINAL)
   ============================================================ */
var DashboardRenderer = (function () {
  'use strict';
  var _intervals = [];
  var _charts = {};
  var _lastFleetWorkers = [];

  function _destroyCharts() { for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } } }

  function _kpiCard(icon, label, value, sentiment, sub) {
    var vc = sentiment === 'positive' ? ' positive' : sentiment === 'negative' ? ' negative' : '';
    return '<div class="portfolio-card"><div class="card-icon ' + sentiment + '"><i class="fa-solid ' + icon + '"></i></div><div class="card-info"><div class="card-value' + vc + '">' + value + '</div><div class="card-label">' + label + '</div>' + (sub ? '<div class="card-sub">' + sub + '</div>' : '') + '</div></div>';
  }

  function _fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';
    if (state.indexOf('loading') !== -1 || state.indexOf('fetching') !== -1 || state.indexOf('generating') !== -1 || state.indexOf('warming') !== -1) return 'warning';
    return 'stale';
  }

  function render() {
    var html = '<div class="dashboard">';

    /* Row 1: KPIs */
    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-kpi" class="portfolio-grid"><div class="loading-state" style="min-height:80px;grid-column:1/-1;"><div class="spinner"></div></div></div></section>';

    /* Row 2: Equity Chart + Portfolio Stats */
    html += '<div class="dash-split-row">';
    html += '<section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-chart-area"></i><h2>Equity Curve</h2></div>';
    html += '<div class="chart-container"><div class="chart-wrapper" id="dash-equity-wrap"><canvas id="dash-equity-chart"></canvas></div></div></section>';
    html += '<section class="dash-stats-section"><div class="section-header"><i class="fa-solid fa-chart-pie"></i><h2>Portfolio Stats</h2></div>';
    html += '<div id="dash-port-stats" class="dash-stats-grid"><div class="loading-state" style="min-height:200px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';

    /* Row 3: Fleet + Pipeline + Active Strategies */
    html += '<div class="dash-triple-row">';

    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Health</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-fleet" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-diagram-project"></i><h2>Pipeline</h2></div>';
    html += '<div id="dash-pipeline" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-crosshairs"></i><h2>Active Strategies</h2></div>';
    html += '<div id="dash-strategies" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';

    html += '</div>';

    /* Row 4: Recent Trades + Deployments */
    html += '<div class="dash-dual-row">';
    html += '<section><div class="section-header"><i class="fa-solid fa-receipt"></i><h2>Recent Trades</h2></div>';
    html += '<div id="dash-trades"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-deploys"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';

    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _fetchAll();
    _intervals.push(setInterval(_fetchLive, 10000));
    _intervals.push(setInterval(_fetchKPIs, 15000));
  }

  function _fetchAll() { _fetchKPIs(); _fetchEquity(); _fetchPortStats(); _fetchFleet(); _fetchPipeline(); _fetchStrategies(); _fetchTrades(); _fetchDeploys(); }
  function _fetchLive() { _fetchFleet(); _fetchPipeline(); _fetchDeploys(); }

  function _fetchKPIs() {
    Promise.all([
      ApiClient.getPortfolioSummary().catch(function () { return { portfolio: {} }; }),
      ApiClient.getSystemSummary().catch(function () { return {}; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; })
    ]).then(function (r) {
      var p = r[0].portfolio || {}, sys = r[1], deps = r[2].deployments || [];
      var running = deps.filter(function (d) { return d.state === 'running'; }).length;
      var el = document.getElementById('dash-kpi'); if (!el) return;
      el.innerHTML =
        _kpiCard('fa-wallet', 'Equity', '$' + _fmtNum(p.total_equity || 0), 'neutral') +
        _kpiCard('fa-chart-line', 'Realized P&L', _fmtMoney(p.realized_pnl), (p.realized_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _kpiCard('fa-clock', 'Floating P&L', _fmtMoney(p.floating_pnl), (p.floating_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _kpiCard('fa-percent', 'Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _kpiCard('fa-chart-bar', 'Profit Factor', String(p.profit_factor || 0), (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _kpiCard('fa-arrow-trend-down', 'Max Drawdown', _fmtPct(p.max_drawdown), 'negative') +
        _kpiCard('fa-server', 'Online Nodes', (sys.online_nodes || 0) + '/' + (sys.total_nodes || 0), (sys.online_nodes || 0) > 0 ? 'positive' : 'warning') +
        _kpiCard('fa-play', 'Running', String(running), running > 0 ? 'positive' : 'neutral');
    });
  }

  function _fetchEquity() {
    ApiClient.getEquityHistory().then(function (data) {
      var hist = data.equity_history || [];
      if (hist.length === 0) {
        var wrap = document.getElementById('dash-equity-wrap');
        if (wrap) wrap.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:12px;gap:10px;"><i class="fa-solid fa-chart-area" style="opacity:0.3;font-size:28px;"></i><div><div style="font-weight:600;margin-bottom:2px;">No Equity Data Yet</div><div style="font-size:10.5px;opacity:0.7;">Trades will build the equity curve as strategies execute.</div></div></div>';
        return;
      }
      var labels = hist.map(function (h) { return h.timestamp; });
      var values = hist.map(function (h) { return h.equity; });
      var canvas = document.getElementById('dash-equity-chart'); if (!canvas) return;
      if (_charts.equity) _charts.equity.destroy();
      var ctx = canvas.getContext('2d');
      var gradient = ctx.createLinearGradient(0, 0, 0, 280);
      gradient.addColorStop(0, 'rgba(6,182,212,0.25)');
      gradient.addColorStop(1, 'rgba(6,182,212,0.0)');
      _charts.equity = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHitRadius: 10 }] },
        options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + _fmtNum(v); } } } } })
      });
    }).catch(function () {});
  }

  function _fetchPortStats() {
    ApiClient.getPortfolioSummary().then(function (data) {
      var p = data.portfolio || {}, el = document.getElementById('dash-port-stats'); if (!el) return;
      function _stat(l, v, c) { return '<div class="dash-stat-item"><span class="dash-stat-val' + (c ? ' ' + c : '') + '">' + v + '</span><span class="dash-stat-lbl">' + l + '</span></div>'; }
      el.innerHTML =
        _stat('Total Trades', p.total_trades || 0) +
        _stat('Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _stat('Profit Factor', p.profit_factor || 0, (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _stat('Sharpe Est.', p.sharpe_estimate || 0, (p.sharpe_estimate || 0) >= 1 ? 'positive' : 'negative') +
        _stat('Avg Trade', _fmtMoney(p.avg_trade), (p.avg_trade || 0) >= 0 ? 'positive' : 'negative') +
        _stat('Avg Winner', _fmtMoney(p.avg_winner), 'positive') +
        _stat('Avg Loser', _fmtMoney(p.avg_loser), 'negative') +
        _stat('Max DD', _fmtPct(p.max_drawdown), 'negative') +
        _stat('Best Trade', _fmtMoney(p.best_trade), 'positive') +
        _stat('Worst Trade', _fmtMoney(p.worst_trade), 'negative') +
        _stat('Avg Bars', p.avg_bars_held || 0) +
        _stat('Open Pos.', p.open_positions || 0);
    }).catch(function () {});
  }

  function _fetchFleet() {
    ApiClient.getFleetWorkers().then(function (data) {
      var s = data.summary || {}, workers = data.workers || [], el = document.getElementById('dash-fleet'); if (!el) return;
      _lastFleetWorkers = workers;
      var html = '<div class="fleet-summary" style="margin-bottom:12px;">';
      html += _fleetBadge(s.total_workers || 0, 'Total', 'total') + _fleetBadge(s.online_workers || 0, 'Online', 'online') + _fleetBadge(s.stale_workers || 0, 'Stale', 'stale') + _fleetBadge(s.offline_workers || 0, 'Offline', 'offline') + _fleetBadge(s.error_workers || 0, 'Error', 'error');
      html += '</div>';
      if (workers.length > 0) {
        html += '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>Worker</th><th>State</th><th>MT5</th><th>Strategy</th><th>Heartbeat</th></tr></thead><tbody>';
        workers.forEach(function (w) {
          var name = w.worker_name || w.worker_id, state = w.state || 'unknown';
          var strats = w.active_strategies && w.active_strategies.length > 0 ? w.active_strategies.join(', ') : '<span class="value-null">\u2014</span>';
          var mt5 = w.mt5_state === 'connected' ? '<span style="color:var(--success);">●</span>' : '<span class="value-null">○</span>';
          html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')"><td class="mono">' + name + '</td><td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td><td>' + mt5 + '</td><td class="mono">' + strats + '</td><td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td></tr>';
        });
        html += '</tbody></table></div>';
      } else {
        html += '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>No workers connected.</div>';
      }
      html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">View Fleet <i class="fa-solid fa-arrow-right"></i></span>';
      el.innerHTML = html;
    }).catch(function () { var el = document.getElementById('dash-fleet'); if (el) el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">Could not load fleet data.</div>'; });
  }

  function _fetchPipeline() {
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [], el = document.getElementById('dash-pipeline'); if (!el) return;
      var totalTicks = 0, totalBars = 0, totalSignals = 0, totalOnBar = 0;
      workers.forEach(function (w) { totalTicks += (w.total_ticks || 0); totalBars += (w.total_bars || 0); totalSignals += (w.signal_count || 0); totalOnBar += (w.on_bar_calls || 0); });
      if (workers.length === 0) {
        el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:24px;color:var(--text-muted);font-size:12px;gap:10px;"><i class="fa-solid fa-diagram-project" style="opacity:0.3;font-size:24px;"></i><div><div style="font-weight:600;margin-bottom:2px;">No Pipeline Data</div><div style="font-size:10.5px;opacity:0.7;">Connect worker agents to see live tick/bar/signal flow.</div></div></div>';
        return;
      }
      el.innerHTML = '<div class="pipeline-flow">' +
        '<div class="pipeline-node"><span class="pipeline-val accent">' + _fmtNum(totalTicks) + '</span><span class="pipeline-lbl">Ticks</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val warning">' + _fmtNum(totalBars) + '</span><span class="pipeline-lbl">Bars</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val success">' + _fmtNum(totalOnBar) + '</span><span class="pipeline-lbl">on_bar()</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val danger">' + _fmtNum(totalSignals) + '</span><span class="pipeline-lbl">Signals</span></div>' +
        '</div>';
    }).catch(function () {});
  }

  function _fetchStrategies() {
    Promise.all([
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; })
    ]).then(function (r) {
      var strats = r[0].strategies || [], deps = r[1].deployments || [], el = document.getElementById('dash-strategies'); if (!el) return;
      if (strats.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No strategies registered.</div>'; return; }
      var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
      strats.forEach(function (s) {
        var active = deps.filter(function (d) { return d.strategy_id === s.strategy_id && d.state === 'running'; }).length;
        var total = deps.filter(function (d) { return d.strategy_id === s.strategy_id; }).length;
        html += '<div class="dash-strat-row"><div class="dash-strat-info"><span class="mono" style="color:var(--accent);font-weight:600;">' + (s.name || s.strategy_id) + '</span><span class="dash-strat-meta">v' + (s.version || '?') + '</span></div><div class="dash-strat-badges">' +
          (active > 0 ? '<span class="state-pill online">' + active + ' RUNNING</span>' : '') +
          '<span style="font-size:10px;color:var(--text-muted);">' + total + ' deploy' + (total !== 1 ? 's' : '') + '</span></div></div>';
      });
      html += '</div>';
      el.innerHTML = html;
    });
  }

  function _fetchTrades() {
    ApiClient.getPortfolioTrades({ limit: 10 }).then(function (data) {
      var trades = data.trades || [], el = document.getElementById('dash-trades'); if (!el) return;
      if (trades.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No trades yet.</div>'; return; }
      var html = '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th></tr></thead><tbody>';
      trades.slice(0, 10).forEach(function (t) {
        var pnlClass = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + t.symbol + '</td><td><span class="state-pill ' + (t.direction === 'long' ? 'online' : 'error') + '">' + t.direction.toUpperCase() + '</span></td><td class="mono">' + t.entry_price + '</td><td class="mono">' + t.exit_price + '</td><td class="mono ' + pnlClass + '">' + _fmtMoney(t.profit) + '</td><td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td></tr>';
      });
      html += '</tbody></table></div><span class="view-fleet-link" onclick="App.navigateTo(\'portfolio\')">View Portfolio <i class="fa-solid fa-arrow-right"></i></span>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _fetchDeploys() {
    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [], el = document.getElementById('dash-deploys'); if (!el) return;
      if (deps.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No deployments yet.</div>'; return; }
      deps = deps.slice().reverse().slice(0, 8);
      var html = '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>ID</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th></tr></thead><tbody>';
      deps.forEach(function (d) {
        var sc = _deployStateClass(d.state);
        html += '<tr><td class="mono">' + d.deployment_id + '</td><td class="mono">' + d.strategy_id + '</td><td class="mono">' + d.worker_id + '</td><td class="mono">' + d.symbol + '</td><td><span class="state-pill ' + sc + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span></td></tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastFleetWorkers.length; i++) {
      if (_lastFleetWorkers[i].worker_id === workerId) { App.navigateToWorkerDetail(_lastFleetWorkers[i]); return; }
    }
  }

  function destroy() { _intervals.forEach(clearInterval); _intervals = []; _destroyCharts(); }

  return { render: render, destroy: destroy, _openWorker: _openWorker };
})();

/* ============================================================
   FLEET RENDERER
   ============================================================ */
var FleetRenderer = (function () {
  'use strict';
  var _refreshInterval = null, _lastWorkers = [];

  function fleetBadge(count, label, type) { return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>'; }

  function renderNodeCard(w) {
    var state = w.state || 'unknown', name = w.worker_name || w.worker_id;
    var strats = w.active_strategies && w.active_strategies.length > 0 ? w.active_strategies.join(', ') : null;
    var pnlVal = w.floating_pnl !== null && w.floating_pnl !== undefined ? _fmtMoney(w.floating_pnl) : '<span class="value-null">\u2014</span>';
    var pnlStyle = w.floating_pnl !== null && w.floating_pnl !== undefined ? (w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)') : '';
    function _row(l, v) { return '<div class="node-info-row"><span class="node-info-label">' + l + '</span><span class="node-info-value">' + v + '</span></div>'; }
    return '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
      '<div class="node-card-top ' + state + '"></div><div class="node-card-header"><div class="node-name-group"><span class="node-status-dot ' + state + '"></span><span class="node-name">' + name + '</span></div><span class="node-status-badge ' + state + '">' + (state.charAt(0).toUpperCase() + state.slice(1)) + '</span></div><div class="node-card-body">' +
      _row('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
      _row('Host', _nullVal(w.host)) +
      _row('MT5', w.mt5_state === 'connected' ? '<span style="color:var(--success);">Connected</span>' : _nullVal(w.mt5_state, 'Not Connected')) +
      _row('Broker', _nullVal(w.broker)) +
      _row('Strategies', _nullVal(strats, 'None')) +
      _row('Positions', '<span style="color:var(--accent);">' + (w.open_positions_count || 0) + '</span>') +
      _row('Float PnL', '<span style="' + pnlStyle + '">' + pnlVal + '</span>') +
      _row('Pipeline', '<span class="mono" style="font-size:10px;">' + (w.total_ticks || 0) + ' ticks / ' + (w.total_bars || 0) + ' bars / ' + (w.signal_count || 0) + ' sig</span>') +
      _row('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
      '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy</div></div></div>';
  }

  function _renderContent(data) {
    var el = document.getElementById('fleet-content'); if (!el) return;
    var workers = data.workers || [], s = data.summary || {}; _lastWorkers = workers;
    var headerEl = document.getElementById('fleet-page-header');
    if (headerEl) { headerEl.style.display = 'flex'; var m = headerEl.querySelector('.last-synced'); if (m) m.textContent = 'Synced: ' + new Date().toLocaleTimeString('en-GB', { hour12: false }); }
    if (workers.length === 0) { el.innerHTML = '<div class="empty-state"><i class="fa-solid fa-server"></i><h3>No Workers Connected</h3><p>Start a worker agent to see fleet data.</p></div>'; return; }
    var html = '<div class="fleet-summary">' + fleetBadge(s.total_workers || 0, 'Total', 'total') + fleetBadge(s.online_workers || 0, 'Online', 'online') + fleetBadge(s.stale_workers || 0, 'Stale', 'stale') + fleetBadge(s.offline_workers || 0, 'Offline', 'offline') + fleetBadge(s.error_workers || 0, 'Error', 'error') + '</div>';
    html += '<div class="fleet-grid">'; workers.forEach(function (w) { html += renderNodeCard(w); }); html += '</div>';
    el.innerHTML = html;
  }

  function _fetch() { ApiClient.getFleetWorkers().then(_renderContent).catch(function () { var el = document.getElementById('fleet-content'); if (el) el.innerHTML = '<div class="error-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Failed to Load Fleet</h3><button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button></div>'; }); }
  function _openWorker(wid) { for (var i = 0; i < _lastWorkers.length; i++) { if (_lastWorkers[i].worker_id === wid) { App.navigateToWorkerDetail(_lastWorkers[i]); return; } } }
  function render() {
    document.getElementById('main-content').innerHTML = '<div class="fleet-page"><div class="fleet-page-header" id="fleet-page-header" style="display:none;"><span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span><div class="fleet-page-meta"><div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div><span class="last-synced">Synced: --:--:--</span></div></div><div id="fleet-content"><div class="loading-state"><div class="spinner"></div><p>Loading fleet\u2026</p></div></div></div>';
    _fetch(); _refreshInterval = setInterval(_fetch, 5000);
  }
  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy, _retry: _fetch, _openWorker: _openWorker };
})();

/* ============================================================
   STRATEGIES RENDERER
   ============================================================ */
var StrategiesRenderer = (function () {
  'use strict';
  var _refreshInterval = null;
  function render() {
    var html = '<div class="fleet-page"><div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span><div class="fleet-page-meta"><button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';
    html += '<div class="wd-panel"><div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div><div class="wd-panel-body"><div class="wd-file-upload" id="strat-upload-area"><input type="file" id="strat-file-input" accept=".py" style="display:none" /><i class="fa-solid fa-file-code"></i><h4>Upload Strategy File</h4><p>.py files extending BaseStrategy</p><div id="strat-upload-status"></div></div></div></div>';
    html += '<div id="strat-list-content"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading\u2026</p></div></div></div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents(); _fetch(); _refreshInterval = setInterval(_fetch, 10000);
  }
  function _attachEvents() {
    document.getElementById('strat-refresh').addEventListener('click', _fetch);
    var area = document.getElementById('strat-upload-area'), input = document.getElementById('strat-file-input');
    area.addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () { if (!input.files || !input.files[0]) return; var f = input.files[0]; if (!f.name.endsWith('.py')) { ToastManager.show('Only .py files.', 'error'); return; } _upload(f); });
  }
  function _upload(file) {
    var el = document.getElementById('strat-upload-status');
    el.innerHTML = '<div class="wd-file-status" style="color:var(--accent);"><i class="fa-solid fa-spinner fa-spin"></i> Uploading\u2026</div>';
    ApiClient.uploadStrategy(file).then(function (d) { el.innerHTML = '<div class="wd-file-status" style="color:var(--success);"><i class="fa-solid fa-circle-check"></i> Registered: ' + (d.strategy_name || d.strategy_id) + '</div>'; ToastManager.show('Strategy registered.', 'success'); _fetch(); }).catch(function (e) { el.innerHTML = '<div class="wd-file-status" style="color:var(--danger);"><i class="fa-solid fa-circle-xmark"></i> ' + e.message + '</div>'; });
  }
  function _fetch() {
    var el = document.getElementById('strat-list-content'); if (!el) return;
    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];
      if (list.length === 0) { el.innerHTML = '<div class="empty-state" style="min-height:200px;"><i class="fa-solid fa-crosshairs"></i><h3>No Strategies</h3><p>Upload a .py strategy file to get started.</p></div>'; return; }
      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>ID</th><th>Name</th><th>Version</th><th>Hash</th><th>Uploaded</th></tr></thead><tbody>';
      list.forEach(function (s) { var up = s.uploaded_at ? s.uploaded_at.replace('T', ' ').substring(0, 19) : '\u2014'; html += '<tr><td class="mono">' + s.strategy_id + '</td><td>' + (s.name || s.strategy_id) + '</td><td class="mono">' + (s.version || '\u2014') + '</td><td class="mono" style="font-size:10px;">' + (s.file_hash || '\u2014') + '</td><td class="mono">' + up + '</td></tr>'; });
      html += '</tbody></table></div>'; el.innerHTML = html;
    }).catch(function (e) { el.innerHTML = '<div class="error-state" style="min-height:200px;"><i class="fa-solid fa-triangle-exclamation"></i><h3>Failed to Load</h3><p>' + e.message + '</p></div>'; });
  }
  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy };
})();

/* ============================================================
   PORTFOLIO RENDERER
   ============================================================ */
var PortfolioRenderer = (function () {
  'use strict';
  var _charts = {}, _filters = { strategy_id: '', worker_id: '', symbol: '' }, _viewMode = 'overall';

  function _destroyCharts() { for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } } }

  function render() {
    var html = '<div class="fleet-page" id="portfolio-page">';

    /* Header */
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-chart-line" style="color:var(--accent);margin-right:8px;"></i>Portfolio Analytics</span><div class="fleet-page-meta"><button class="wd-refresh-btn" id="port-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';

    /* View Mode Tabs */
    html += '<div class="port-tabs" id="port-tabs"><button class="port-tab active" data-mode="overall">Overall</button><button class="port-tab" data-mode="strategy">By Strategy</button><button class="port-tab" data-mode="worker">By Worker</button><button class="port-tab" data-mode="symbol">By Symbol</button></div>';

    /* Filters */
    html += '<div class="port-filters" id="port-filters"><div class="wd-form-group"><label class="wd-form-label">Strategy</label><select class="wd-form-select port-filter" id="port-f-strategy"><option value="">All</option></select></div><div class="wd-form-group"><label class="wd-form-label">Worker</label><select class="wd-form-select port-filter" id="port-f-worker"><option value="">All</option></select></div><div class="wd-form-group"><label class="wd-form-label">Symbol</label><select class="wd-form-select port-filter" id="port-f-symbol"><option value="">All</option></select></div></div>';

    /* Stats */
    html += '<div id="port-stats" class="dash-stats-grid" style="margin-bottom:20px;"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div></div></div>';

    /* Charts Row */
    html += '<div class="dash-split-row"><section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-chart-area"></i><h2>Equity Curve</h2></div><div class="chart-container"><div class="chart-wrapper" id="port-equity-wrap"><canvas id="port-equity-chart"></canvas></div></div></section>';
    html += '<section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-arrow-trend-down"></i><h2>Drawdown</h2></div><div class="chart-container"><div class="chart-wrapper" id="port-dd-wrap"><canvas id="port-dd-chart"></canvas></div></div></section></div>';

    /* Daily Performance Chart */
    html += '<section><div class="section-header"><i class="fa-solid fa-calendar-days"></i><h2>Daily P&L</h2></div><div class="chart-container"><div class="chart-wrapper" style="height:220px;" id="port-daily-wrap"><canvas id="port-daily-chart"></canvas></div></div></section>';

    /* Breakdown Table */
    html += '<div id="port-breakdown"></div>';

    /* Trade Table */
    html += '<section><div class="section-header"><i class="fa-solid fa-list"></i><h2>Trade History</h2></div><div id="port-trades"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';

    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents();
    _loadAll();
  }

  function _attachEvents() {
    document.getElementById('port-refresh').addEventListener('click', _loadAll);
    document.querySelectorAll('.port-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.port-tab').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        _viewMode = btn.getAttribute('data-mode');
        _loadBreakdown();
      });
    });
    document.querySelectorAll('.port-filter').forEach(function (sel) {
      sel.addEventListener('change', function () {
        _filters.strategy_id = document.getElementById('port-f-strategy').value;
        _filters.worker_id = document.getElementById('port-f-worker').value;
        _filters.symbol = document.getElementById('port-f-symbol').value;
        _loadTrades();
      });
    });
  }

  function _loadAll() { _loadFilters(); _loadStats(); _loadEquity(); _loadDaily(); _loadBreakdown(); _loadTrades(); }

  function _loadFilters() {
    ApiClient.getPortfolioTrades({ limit: 500 }).then(function (data) {
      var trades = data.trades || {};
      var strats = {}, workers = {}, syms = {};
      trades.forEach(function (t) { strats[t.strategy_id] = 1; workers[t.worker_id] = 1; syms[t.symbol] = 1; });
      function _fill(id, obj) {
        var el = document.getElementById(id); if (!el) return;
        var val = el.value;
        el.innerHTML = '<option value="">All</option>';
        Object.keys(obj).sort().forEach(function (k) { el.innerHTML += '<option value="' + k + '"' + (k === val ? ' selected' : '') + '>' + k + '</option>'; });
      }
      _fill('port-f-strategy', strats); _fill('port-f-worker', workers); _fill('port-f-symbol', syms);
    }).catch(function () {});
  }

  function _loadStats() {
    ApiClient.getPortfolioSummary().then(function (data) {
      var p = data.portfolio || {}, el = document.getElementById('port-stats'); if (!el) return;
      function _s(l, v, c) { return '<div class="dash-stat-item"><span class="dash-stat-val' + (c ? ' ' + c : '') + '">' + v + '</span><span class="dash-stat-lbl">' + l + '</span></div>'; }
      el.innerHTML =
        _s('Net Profit', _fmtMoney(p.realized_pnl), (p.realized_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _s('Total Trades', p.total_trades || 0) +
        _s('Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _s('Profit Factor', p.profit_factor || 0, (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _s('Sharpe', p.sharpe_estimate || 0) +
        _s('Max DD', _fmtPct(p.max_drawdown), 'negative') +
        _s('Avg Winner', _fmtMoney(p.avg_winner), 'positive') +
        _s('Avg Loser', _fmtMoney(p.avg_loser), 'negative') +
        _s('Best', _fmtMoney(p.best_trade), 'positive') +
        _s('Worst', _fmtMoney(p.worst_trade), 'negative') +
        _s('Avg Bars', p.avg_bars_held || 0) +
        _s('Open Pos.', p.open_positions || 0);
    }).catch(function () {});
  }

  function _loadEquity() {
    ApiClient.getEquityHistory().then(function (data) {
      var hist = data.equity_history || []; if (hist.length === 0) return;
      var labels = hist.map(function (h) { return h.timestamp; }), vals = hist.map(function (h) { return h.equity; });

      /* Equity */
      var c1 = document.getElementById('port-equity-chart'); if (!c1) return;
      if (_charts.equity) _charts.equity.destroy();
      var ctx1 = c1.getContext('2d'), g1 = ctx1.createLinearGradient(0, 0, 0, 280);
      g1.addColorStop(0, 'rgba(6,182,212,0.25)'); g1.addColorStop(1, 'rgba(6,182,212,0)');
      _charts.equity = new Chart(ctx1, { type: 'line', data: { labels: labels, datasets: [{ data: vals, borderColor: ChartHelper.accentColor(), backgroundColor: g1, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + _fmtNum(v); } } } } }) });

      /* Drawdown */
      var peak = 0, dd = [];
      vals.forEach(function (v) { if (v > peak) peak = v; dd.push(peak > 0 ? -((peak - v) / peak * 100) : 0); });
      var c2 = document.getElementById('port-dd-chart'); if (!c2) return;
      if (_charts.dd) _charts.dd.destroy();
      var ctx2 = c2.getContext('2d'), g2 = ctx2.createLinearGradient(0, 0, 0, 280);
      g2.addColorStop(0, 'rgba(239,68,68,0)'); g2.addColorStop(1, 'rgba(239,68,68,0.3)');
      _charts.dd = new Chart(ctx2, { type: 'line', data: { labels: labels, datasets: [{ data: dd, borderColor: ChartHelper.dangerColor(), backgroundColor: g2, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return v.toFixed(1) + '%'; } } } } }) });
    }).catch(function () {});
  }

  function _loadDaily() {
    ApiClient.getPortfolioPerformance().then(function (data) {
      var daily = (data.performance || {}).daily || [];
      if (daily.length === 0) {
        var w = document.getElementById('port-daily-wrap');
        if (w) w.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-calendar-days" style="margin-right:10px;opacity:0.3;font-size:24px;"></i>No daily performance data yet.</div>';
        return;
      }
      var labels = daily.map(function (d) { return d.date; });
      var vals = daily.map(function (d) { return d.pnl; });
      var colors = vals.map(function (v) { return v >= 0 ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)'; });
      var c = document.getElementById('port-daily-chart'); if (!c) return;
      if (_charts.daily) _charts.daily.destroy();
      _charts.daily = new Chart(c.getContext('2d'), { type: 'bar', data: { labels: labels, datasets: [{ data: vals, backgroundColor: colors, borderRadius: 2, barPercentage: 0.7 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { display: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 9 }, maxRotation: 45, maxTicksLimit: 30 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + v; } } } } }) });
    }).catch(function () {});
  }

  function _loadBreakdown() {
    ApiClient.getPortfolioPerformance().then(function (data) {
      var perf = data.performance || {}, el = document.getElementById('port-breakdown'); if (!el) return;
      var key, title;
      if (_viewMode === 'strategy') { key = 'by_strategy'; title = 'Strategy Breakdown'; }
      else if (_viewMode === 'worker') { key = 'by_worker'; title = 'Worker Breakdown'; }
      else if (_viewMode === 'symbol') { key = 'by_symbol'; title = 'Symbol Breakdown'; }
      else { el.innerHTML = ''; return; }
      var rows = perf[key] || [];
      if (rows.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No data.</div>'; return; }
      var idKey = key === 'by_strategy' ? 'strategy_id' : key === 'by_worker' ? 'worker_id' : 'symbol';
      var html = '<section style="margin-top:20px;"><div class="section-header"><i class="fa-solid fa-table-cells"></i><h2>' + title + '</h2></div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>' + idKey.replace('_', ' ').toUpperCase() + '</th><th>Trades</th><th>P&L</th><th>Win Rate</th><th>PF</th><th>Avg Bars</th></tr></thead><tbody>';
      rows.sort(function (a, b) { return b.pnl - a.pnl; });
      rows.forEach(function (r) {
        var pc = r.pnl >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + r[idKey] + '</td><td class="mono">' + r.trades + '</td><td class="mono ' + pc + '">' + _fmtMoney(r.pnl) + '</td><td class="mono">' + _fmtPct(r.win_rate) + '</td><td class="mono">' + r.profit_factor + '</td><td class="mono">' + r.avg_bars + '</td></tr>';
      });
      html += '</tbody></table></div></section>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _loadTrades() {
    var params = { limit: 200 };
    if (_filters.strategy_id) params.strategy_id = _filters.strategy_id;
    if (_filters.worker_id) params.worker_id = _filters.worker_id;
    if (_filters.symbol) params.symbol = _filters.symbol;
    ApiClient.getPortfolioTrades(params).then(function (data) {
      var trades = data.trades || [], el = document.getElementById('port-trades'); if (!el) return;
      if (trades.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No trades found.</div>'; return; }
      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>#</th><th>Symbol</th><th>Dir</th><th>Strategy</th><th>Worker</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Bars</th><th>Reason</th></tr></thead><tbody>';
      trades.forEach(function (t) {
        var pc = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + t.id + '</td><td class="mono">' + t.symbol + '</td><td><span class="state-pill ' + (t.direction === 'long' ? 'online' : 'error') + '">' + t.direction.toUpperCase() + '</span></td><td class="mono" style="font-size:10px;">' + t.strategy_id + '</td><td class="mono" style="font-size:10px;">' + t.worker_id + '</td><td class="mono">' + t.entry_price + '</td><td class="mono">' + t.exit_price + '</td><td class="mono ' + pc + '">' + _fmtMoney(t.profit) + '</td><td class="mono">' + t.bars_held + '</td><td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td></tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function (e) { var el = document.getElementById('port-trades'); if (el) el.innerHTML = '<div style="color:var(--danger);font-size:12px;">Error: ' + e.message + '</div>'; });
  }

  function destroy() { _destroyCharts(); }
  return { render: render, destroy: destroy };
})();

/* ============================================================
   LOGS RENDERER
   ============================================================ */
var LogsRenderer = (function () {
  'use strict';
  var _refreshInterval = null, _autoRefresh = true;

  function render() {
    var html = '<div class="fleet-page" id="logs-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-scroll" style="color:var(--accent);margin-right:8px;"></i>Event Logs</span><div class="fleet-page-meta"><label class="log-auto-label"><input type="checkbox" id="log-auto-check" checked /> Auto-refresh</label><button class="wd-refresh-btn" id="log-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';

    /* Filters */
    html += '<div class="log-filters">';
    html += '<div class="wd-form-group"><label class="wd-form-label">Category</label><select class="wd-form-select log-f" id="log-f-cat"><option value="">All</option><option value="system">SYSTEM</option><option value="worker">WORKER</option><option value="execution">EXECUTION</option><option value="strategy">STRATEGY</option><option value="deployment">DEPLOYMENT</option><option value="command">COMMAND</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Level</label><select class="wd-form-select log-f" id="log-f-level"><option value="">All</option><option value="INFO">INFO</option><option value="WARNING">WARNING</option><option value="ERROR">ERROR</option><option value="DEBUG">DEBUG</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker</label><input type="text" class="wd-form-input log-f" id="log-f-worker" placeholder="worker id\u2026" /></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Search</label><input type="text" class="wd-form-input log-f" id="log-f-search" placeholder="keyword\u2026" /></div>';
    html += '</div>';

    /* Table */
    html += '<div id="log-content"><div class="loading-state" style="min-height:200px;"><div class="spinner"></div><p>Loading events\u2026</p></div></div>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents();
    _fetch();
    _refreshInterval = setInterval(function () { if (_autoRefresh) _fetch(); }, 5000);
  }

  function _attachEvents() {
    document.getElementById('log-refresh').addEventListener('click', _fetch);
    document.getElementById('log-auto-check').addEventListener('change', function () { _autoRefresh = this.checked; });
    document.querySelectorAll('.log-f').forEach(function (el) {
      el.addEventListener('change', _fetch);
      el.addEventListener('keyup', function (e) { if (e.key === 'Enter') _fetch(); });
    });
  }

  function _fetch() {
    var params = {};
    var cat = document.getElementById('log-f-cat').value; if (cat) params.category = cat;
    var lvl = document.getElementById('log-f-level').value; if (lvl) params.level = lvl;
    var wk = document.getElementById('log-f-worker').value.trim(); if (wk) params.worker_id = wk;
    var search = document.getElementById('log-f-search').value.trim(); if (search) params.search = search;
    params.limit = 300;

    ApiClient.getEvents(params).then(function (data) {
      var events = data.events || [], el = document.getElementById('log-content'); if (!el) return;
      if (events.length === 0) { el.innerHTML = '<div style="padding:24px;color:var(--text-muted);font-size:12px;text-align:center;"><i class="fa-solid fa-circle-info" style="margin-right:6px;"></i>No events found matching filters.</div>'; return; }

      var html = '<div class="log-count">' + data.count + ' events</div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table log-table"><thead><tr><th style="width:150px;">Timestamp</th><th style="width:90px;">Category</th><th style="width:60px;">Level</th><th style="width:100px;">Type</th><th>Message</th><th style="width:80px;">Worker</th></tr></thead><tbody>';

      events.forEach(function (ev, idx) {
        var ts = (ev.timestamp || '').replace('T', ' ').substring(0, 19);
        var cat = (ev.category || '').toUpperCase();
        var lvl = ev.level || 'INFO';
        var lvlClass = lvl === 'ERROR' ? 'text-danger' : lvl === 'WARNING' ? 'text-warning' : 'text-muted';
        var catClass = '';
        if (cat === 'EXECUTION') catClass = 'text-success';
        else if (cat === 'STRATEGY') catClass = 'text-accent';
        else if (cat === 'WORKER') catClass = 'text-warning';
        var msg = ev.message || '';
        var hasData = ev.data_json && ev.data_json !== 'null';
        var expandId = 'log-expand-' + idx;

        html += '<tr class="log-row' + (hasData ? ' clickable' : '') + '"' + (hasData ? ' onclick="LogsRenderer._toggle(\'' + expandId + '\')"' : '') + '>';
        html += '<td class="mono" style="font-size:10.5px;">' + ts + '</td>';
        html += '<td class="mono ' + catClass + '" style="font-size:10px;">' + cat + '</td>';
        html += '<td class="mono ' + lvlClass + '" style="font-size:10px;font-weight:600;">' + lvl + '</td>';
        html += '<td class="mono" style="font-size:10px;">' + (ev.event_type || '') + '</td>';
        html += '<td style="font-size:11px;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + msg + (hasData ? ' <i class="fa-solid fa-chevron-down" style="font-size:8px;opacity:0.4;margin-left:4px;"></i>' : '') + '</td>';
        html += '<td class="mono" style="font-size:10px;">' + (ev.worker_id || '\u2014') + '</td>';
        html += '</tr>';

        if (hasData) {
          var pretty = '';
          try { pretty = JSON.stringify(JSON.parse(ev.data_json), null, 2); } catch (e) { pretty = ev.data_json; }
          html += '<tr class="log-detail-row" id="' + expandId + '" style="display:none;"><td colspan="6"><pre class="log-payload">' + pretty + '</pre></td></tr>';
        }
      });

      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function (e) {
      var el = document.getElementById('log-content');
      if (el) el.innerHTML = '<div style="padding:24px;color:var(--danger);font-size:12px;">Error loading events: ' + e.message + '</div>';
    });
  }

  function _toggle(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
  }

  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy, _toggle: _toggle };
})();

/* ============================================================
   APP (NAVIGATION)
   ============================================================ */
var App = (function () {
  'use strict';
  var currentPage = 'dashboard', _selectedWorker = null;
  var pageDescriptions = { settings: 'System configuration and preferences.' };

  function init() { ThemeManager.init(); setupNavigation(); startClock(); navigateTo('dashboard'); }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) { e.preventDefault(); navigateTo(item.getAttribute('data-page')); });
    });
  }

  function navigateTo(page) {
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();
    if (currentPage === 'portfolio') PortfolioRenderer.destroy();
    if (currentPage === 'logs') LogsRenderer.destroy();
    currentPage = page;
    var navPage = page === 'workerDetail' ? 'fleet' : page;
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) { item.classList.toggle('active', item.getAttribute('data-page') === navPage); });
    var titleMap = { workerDetail: 'Worker Detail', portfolio: 'Portfolio', logs: 'Logs' };
    document.getElementById('topbar-title').textContent = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    if (page === 'dashboard') DashboardRenderer.render();
    else if (page === 'fleet') FleetRenderer.render();
    else if (page === 'workerDetail' && _selectedWorker) WorkerDetailRenderer.render(_selectedWorker);
    else if (page === 'strategies') StrategiesRenderer.render();
    else if (page === 'portfolio') PortfolioRenderer.render();
    else if (page === 'logs') LogsRenderer.render();
    else renderPlaceholder(page);
  }

  function navigateToWorkerDetail(workerData) { _selectedWorker = workerData; navigateTo('workerDetail'); }

  function renderPlaceholder(page) {
    var desc = pageDescriptions[page] || 'Under development.';
    document.getElementById('main-content').innerHTML = '<div class="placeholder-page"><i class="fa-solid fa-gear"></i><h2>' + (page.charAt(0).toUpperCase() + page.slice(1)) + '</h2><p>' + desc + '</p></div>';
  }

  function startClock() { function u() { var n = new Date(); document.getElementById('topbar-clock').textContent = String(n.getHours()).padStart(2, '0') + ':' + String(n.getMinutes()).padStart(2, '0') + ':' + String(n.getSeconds()).padStart(2, '0'); } u(); setInterval(u, 1000); }

  document.addEventListener('DOMContentLoaded', init);
  return { navigateTo: navigateTo, navigateToWorkerDetail: navigateToWorkerDetail };
})();
```
