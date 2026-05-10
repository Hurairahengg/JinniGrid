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
