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

from strategyWorker import StrategyRunner


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

        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

    # ── Heartbeat ───────────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        diag = runner.get_diagnostics() if runner else {}

        # Determine worker-level state from runner state
        runner_state = diag.get("runner_state", "idle")
        if runner_state in ("idle", "running", "warming_up"):
            worker_state = "online"
        elif runner_state in ("failed",):
            worker_state = "error"
        elif runner_state in ("stopped",):
            worker_state = "online"
        else:
            worker_state = runner_state if runner else "online"

        active_strategies = []
        if diag.get("strategy_id"):
            active_strategies = [diag["strategy_id"]]

        errors = []
        if diag.get("last_error"):
            errors = [diag["last_error"]]

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": worker_state,
            "agent_version": self.agent_version,
            # MT5 info — from runner diagnostics
            "mt5_state": diag.get("mt5_state"),
            "account_id": diag.get("account_id"),
            "broker": diag.get("broker"),
            "active_strategies": active_strategies,
            "open_positions_count": 0,
            "floating_pnl": diag.get("mt5_equity"),
            "errors": errors,
            # Pipeline diagnostics
            "total_ticks": diag.get("total_ticks", 0),
            "total_bars": diag.get("total_bars", 0),
            "on_bar_calls": diag.get("on_bar_calls", 0),
            "signal_count": diag.get("signal_count", 0),
            "last_bar_time": str(diag["last_bar_time"]) if diag.get("last_bar_time") else None,
            "current_price": diag.get("current_price"),
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
            pass
        except Exception as e:
            print(f"[ERROR] Command poll: {type(e).__name__}: {e}")

    def _handle_command(self, cmd: dict):
        cmd_type = cmd.get("command_type")
        cmd_id = cmd.get("command_id")
        payload = cmd.get("payload", {})

        print(f"[COMMAND] Received: {cmd_type} ({cmd_id})")

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

from __future__ import annotations

import os
import sys
import time
import socket
import threading
from typing import Optional

import yaml
import requests


# =============================================================================
# Import Path Bootstrap
# =============================================================================
# Supports both:
#   python -m worker.worker_agent       from project root
#   cd worker && python worker_agent.py
#
# Required because StrategyRunner now lives in:
#   worker/mainWorker.py
# =============================================================================

_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)


# =============================================================================
# Updated combined worker runtime import
# =============================================================================
# OLD:
#   from worker.old.strategy_runner import StrategyRunner
#
# NEW:
#   from worker.mainWorker import StrategyRunner
# =============================================================================

from worker.strategyWorker import StrategyRunner


# =============================================================================
# Config / Host Helpers
# =============================================================================

def load_config() -> dict:
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config.yaml",
    )

    if not os.path.exists(config_path):
        print(f"[ERROR] config.yaml not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data:
        print(f"[ERROR] config.yaml is empty or invalid at {config_path}")
        sys.exit(1)

    return data


def detect_host() -> str:
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname} ({ip})"
    except Exception:
        return socket.gethostname()


# =============================================================================
# Worker Agent
# =============================================================================

class WorkerAgent:
    def __init__(self, config: dict):
        self.worker_id = config["worker"]["worker_id"]
        self.worker_name = config["worker"].get("worker_name", self.worker_id)

        self.mother_url = config["mother_server"]["url"].rstrip("/")
        self.heartbeat_interval = config["heartbeat"].get("interval_seconds", 10)
        self.agent_version = config["agent"].get("version", "0.1.0")
        self.host = detect_host()

        # Active runner: one deployment at a time for now
        self._runner: Optional[StrategyRunner] = None
        self._runner_lock = threading.Lock()

    # -------------------------------------------------------------------------
    # Heartbeat
    # -------------------------------------------------------------------------

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner

        active_strategies = []
        runner_state = "idle"
        floating_pnl = None
        open_positions = 0
        errors = []

        if runner:
            runner_state = getattr(runner, "_runner_state", "idle")

            if getattr(runner, "_strategy", None):
                active_strategies = [runner.strategy_id]

            if getattr(runner, "_last_error", None):
                errors = [runner._last_error]

        if runner_state in ("idle", "running", "warming_up"):
            worker_state = "online"
        else:
            worker_state = runner_state

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "host": self.host,
            "state": worker_state,
            "agent_version": self.agent_version,
            "mt5_state": None,
            "account_id": None,
            "broker": None,
            "active_strategies": active_strategies,
            "open_positions_count": open_positions,
            "floating_pnl": floating_pnl,
            "errors": errors,
        }

    def send_heartbeat(self) -> None:
        endpoint = f"{self.mother_url}/api/Grid/workers/heartbeat"
        payload = self._build_heartbeat_payload()

        try:
            response = requests.post(endpoint, json=payload, timeout=10)

            try:
                data = response.json()
            except Exception:
                data = {}

            if response.status_code >= 400:
                print(
                    f"[ERROR] Heartbeat failed HTTP {response.status_code}: "
                    f"{response.text}"
                )
                return

            status = "REGISTERED" if data.get("registered") else "OK"
            print(f"[HEARTBEAT] {status} | worker={self.worker_id}")

        except requests.exceptions.ConnectionError:
            print(f"[WARNING] Could not reach Mother Server at {self.mother_url}")

        except Exception as exc:
            print(f"[ERROR] Heartbeat: {type(exc).__name__}: {exc}")

    # -------------------------------------------------------------------------
    # Command Polling
    # -------------------------------------------------------------------------

    def poll_commands(self) -> None:
        endpoint = (
            f"{self.mother_url}"
            f"/api/grid/workers/{self.worker_id}/commands/poll"
        )

        try:
            response = requests.get(endpoint, timeout=10)

            if response.status_code >= 400:
                print(
                    f"[ERROR] Command poll failed HTTP {response.status_code}: "
                    f"{response.text}"
                )
                return

            data = response.json()
            commands = data.get("commands", [])

            for command in commands:
                self._handle_command(command)

        except requests.exceptions.ConnectionError:
            # Mother unreachable — heartbeat already warns, so keep this quiet.
            pass

        except Exception as exc:
            print(f"[ERROR] Command poll: {type(exc).__name__}: {exc}")

    def _handle_command(self, command: dict) -> None:
        command_type = command.get("command_type")
        command_id = command.get("command_id")
        payload = command.get("payload", {}) or {}

        print(f"[COMMAND] Received: {command_type} ({command_id})")

        # Acknowledge immediately so Mother knows worker received it.
        if command_id:
            self._ack_command(command_id)

        if command_type == "deploy_strategy":
            self._handle_deploy(payload)

        elif command_type == "stop_strategy":
            self._handle_stop(payload)

        else:
            print(f"[COMMAND] Unknown command type: {command_type}")

    def _ack_command(self, command_id: str) -> None:
        endpoint = (
            f"{self.mother_url}"
            f"/api/grid/workers/{self.worker_id}/commands/ack"
        )

        try:
            response = requests.post(
                endpoint,
                json={"command_id": command_id},
                timeout=10,
            )

            if response.status_code >= 400:
                print(
                    f"[ERROR] Ack failed HTTP {response.status_code}: "
                    f"{response.text}"
                )
                return

            print(f"[COMMAND] Ack sent: {command_id}")

        except Exception as exc:
            print(f"[ERROR] Ack failed: {exc}")

    # -------------------------------------------------------------------------
    # Runner Status Callback
    # -------------------------------------------------------------------------

    def _report_runner_status(self, status: dict) -> None:
        endpoint = (
            f"{self.mother_url}"
            f"/api/grid/workers/{self.worker_id}/runner-status"
        )

        try:
            response = requests.post(endpoint, json=status, timeout=10)

            if response.status_code >= 400:
                print(
                    f"[ERROR] Runner status report failed HTTP "
                    f"{response.status_code}: {response.text}"
                )

        except Exception as exc:
            print(f"[ERROR] Runner status report failed: {exc}")

    # -------------------------------------------------------------------------
    # Deploy / Stop Handlers
    # -------------------------------------------------------------------------

    def _handle_deploy(self, payload: dict) -> None:
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

            print(
                f"[RUNNER] Started deployment "
                f"{payload.get('deployment_id')} | "
                f"strategy={payload.get('strategy_id')} | "
                f"symbol={payload.get('symbol')}"
            )

    def _handle_stop(self, payload: dict) -> None:
        with self._runner_lock:
            if self._runner:
                deployment_id = payload.get("deployment_id")

                if deployment_id and self._runner.deployment_id != deployment_id:
                    print("[COMMAND] Stop ignored — deployment_id mismatch.")
                    return

                self._runner.stop()
                self._runner = None

                print(f"[RUNNER] Stopped deployment {deployment_id}")

            else:
                print("[COMMAND] Stop received but no active runner.")

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------

    def run(self) -> None:
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

        try:
            while True:
                self.send_heartbeat()
                self.poll_commands()
                time.sleep(self.heartbeat_interval)

        except KeyboardInterrupt:
            print("")
            print(f"[SHUTDOWN] Stopping worker agent '{self.worker_id}'...")

            with self._runner_lock:
                if self._runner:
                    self._runner.stop()
                    self._runner = None

            sys.exit(0)


# =============================================================================
# Entrypoint
# =============================================================================

def main() -> None:
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()