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
