"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner management.

Usage:
    1. Edit config.yaml
    2. python -m worker.worker_agent   (from project root)
       OR: cd worker && python worker_agent.py
       worker/worker_agent.py
"""
import os
import sys
import time
import socket
import threading
import yaml
import requests

# Ensure worker package is importable when run directly
_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)
if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from worker.old.strategy_runner import StrategyRunner


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if not os.path.exists(config_path):
        print(f"[ERROR] config.yaml not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_host():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname} ({ip})"
    except Exception:
        return socket.gethostname()


class WorkerAgent:
    def __init__(self, config: dict):
        self.worker_id = config["worker"]["worker_id"]
        self.worker_name = config["worker"].get("worker_name", self.worker_id)
        self.mother_url = config["mother_server"]["url"].rstrip("/")
        self.heartbeat_interval = config["heartbeat"].get("interval_seconds", 10)
        self.agent_version = config["agent"].get("version", "0.1.0")
        self.host = detect_host()

        # Active runner (one deployment at a time for now)
        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

    # ── Heartbeat ───────────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        active_strategies = []
        runner_state = "idle"
        floating_pnl = None
        open_positions = 0
        errors = []

        if runner:
            runner_state = runner._runner_state
            if runner._strategy:
                active_strategies = [runner.strategy_id]
            if runner._last_error:
                errors = [runner._last_error]

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": "online" if runner_state in ("idle", "running", "warming_up") else runner_state,
            "agent_version": self.agent_version,
            "mt5_state": None,
            "account_id": None,
            "broker": None,
            "active_strategies": active_strategies,
            "open_positions_count": open_positions,
            "floating_pnl": floating_pnl,
            "errors": errors,
        }

    def send_heartbeat(self):
        endpoint = f"{self.mother_url}/api/Grid/workers/heartbeat"
        payload = self._build_heartbeat_payload()
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            data = resp.json()
            status = "REGISTERED" if data.get("registered") else "OK"
            print(f"[HEARTBEAT] {status} | worker={self.worker_id}")
        except requests.exceptions.ConnectionError:
            print(f"[WARNING] Could not reach Mother Server at {self.mother_url}")
        except Exception as e:
            print(f"[ERROR] Heartbeat: {type(e).__name__}: {e}")

    # ── Command Polling ─────────────────────────────────────────

    def poll_commands(self):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/poll"
        try:
            resp = requests.get(endpoint, timeout=10)
            data = resp.json()
            commands = data.get("commands", [])
            for cmd in commands:
                self._handle_command(cmd)
        except requests.exceptions.ConnectionError:
            pass  # Mother unreachable — silent, heartbeat already warns
        except Exception as e:
            print(f"[ERROR] Command poll: {type(e).__name__}: {e}")

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get("command_type")
        cmd_id = cmd.get("command_id")
        payload = cmd.get("payload", {})

        print(f"[COMMAND] Received: {cmd_type} ({cmd_id})")

        # Acknowledge immediately
        self._ack_command(cmd_id)

        if cmd_type == "deploy_strategy":
            self._handle_deploy(payload)
        elif cmd_type == "stop_strategy":
            self._handle_stop(payload)
        else:
            print(f"[COMMAND] Unknown command type: {cmd_type}")

    def _ack_command(self, command_id: str):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/ack"
        try:
            requests.post(endpoint, json={"command_id": command_id}, timeout=10)
            print(f"[COMMAND] Ack sent: {command_id}")
        except Exception as e:
            print(f"[ERROR] Ack failed: {e}")

    # ── Runner Status Callback ──────────────────────────────────

    def _report_runner_status(self, status: dict):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/runner-status"
        try:
            requests.post(endpoint, json=status, timeout=10)
        except Exception as e:
            print(f"[ERROR] Runner status report failed: {e}")

    # ── Deploy / Stop Handlers ──────────────────────────────────

    def _handle_deploy(self, payload: dict):
        with self._runner_lock:
            # Stop existing runner if any
            if self._runner:
                print("[RUNNER] Stopping existing runner before new deployment.")
                self._runner.stop()
                self._runner = None

            runner = StrategyRunner(
                deployment_config=payload,
                status_callback=self._report_runner_status,
            )
            self._runner = runner
            runner.start()

    def _handle_stop(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                dep_id = payload.get("deployment_id")
                if dep_id and self._runner.deployment_id != dep_id:
                    print(f"[COMMAND] Stop ignored — deployment_id mismatch.")
                    return
                self._runner.stop()
                self._runner = None
                print(f"[RUNNER] Stopped deployment {dep_id}")
            else:
                print("[COMMAND] Stop received but no active runner.")

    # ── Main Loop ───────────────────────────────────────────────

    def run(self):
        print("")
        print("=" * 56)
        print("  JINNI Grid Worker Agent")
        print("=" * 56)
        print(f"  Worker ID:    {self.worker_id}")
        print(f"  Worker Name:  {self.worker_name}")
        print(f"  Host:         {self.host}")
        print(f"  Mother URL:   {self.mother_url}")
        print(f"  Heartbeat:    {self.heartbeat_interval}s")
        print(f"  Agent:        v{self.agent_version}")
        print("=" * 56)
        print("")

        poll_counter = 0
        try:
            while True:
                self.send_heartbeat()

                # Poll commands every heartbeat
                self.poll_commands()

                poll_counter += 1
                time.sleep(self.heartbeat_interval)

        except KeyboardInterrupt:
            print("")
            print(f"[SHUTDOWN] Stopping worker agent '{self.worker_id}'...")
            with self._runner_lock:
                if self._runner:
                    self._runner.stop()
            sys.exit(0)


def main():
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()