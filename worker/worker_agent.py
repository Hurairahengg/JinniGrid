"""
JINNI Grid - Worker Agent
Sends heartbeat to the Mother Server at a configured interval.

Usage:
    1. Edit config.yaml (set mother_server url to your Mother Server IP:port)
    2. python worker_agent.py
"""

import os
import sys
import time
import socket
import yaml
import requests


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if not os.path.exists(config_path):
        print(f"[ERROR] config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_host():
    """Auto-detect hostname and IP for the host field."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname} ({ip})"
    except Exception:
        return socket.gethostname()


def main():
    config = load_config()

    worker_id = config["worker"]["worker_id"]
    worker_name = config["worker"].get("worker_name", worker_id)
    mother_url = config["mother_server"]["url"].rstrip("/")
    interval = config["heartbeat"].get("interval_seconds", 5)
    agent_version = config["agent"].get("version", "0.1.0")
    host = detect_host()

    endpoint = f"{mother_url}/api/Grid/workers/heartbeat"

    payload = {
        "worker_id": worker_id,
        "worker_name": worker_name,
        "host": host,
        "state": "online",
        "agent_version": agent_version,
        "mt5_state": None,
        "account_id": None,
        "broker": None,
        "active_strategies": [],
        "open_positions_count": 0,
        "floating_pnl": None,
        "errors": [],
    }

    print("")
    print("=" * 50)
    print("  JINNI Grid Worker Agent")
    print("=" * 50)
    print(f"  Worker ID:    {worker_id}")
    print(f"  Worker Name:  {worker_name}")
    print(f"  Host:         {host}")
    print(f"  Mother URL:   {mother_url}")
    print(f"  Endpoint:     {endpoint}")
    print(f"  Interval:     {interval}s")
    print(f"  Agent:        v{agent_version}")
    print("=" * 50)
    print("")

    try:
        while True:
            try:
                resp = requests.post(endpoint, json=payload, timeout=10)
                data = resp.json()
                status = "REGISTERED" if data.get("registered") else "OK"
                print(f"[HEARTBEAT] {status} | worker={worker_id} | server_time={data.get('server_time', 'N/A')}")
            except requests.exceptions.ConnectionError:
                print(f"[WARNING] Could not reach Mother Server at {mother_url}")
            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("")
        print(f"[SHUTDOWN] Worker agent '{worker_id}' stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
