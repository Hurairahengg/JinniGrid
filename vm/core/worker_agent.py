"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner management.
worker/worker_agent.py
"""
import os
import sys
import time
import socket
import threading
import yaml
import requests

_worker_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_worker_dir)
if _worker_dir not in sys.path:
    sys.path.insert(0, _worker_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from vm.core.strategy_worker import StrategyRunner
from vm.trading.portfolio import TradeLedger


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

        # Local trade ledger for persistence (Bug 18 fix)
        self._ledger = TradeLedger(self.worker_id)
        print(f"[AGENT] TradeLedger initialized for worker '{self.worker_id}'")

    # ── Heartbeat ───────────────────────────────────────────

    def _build_heartbeat_payload(self) -> dict:
        runner = self._runner
        diag = runner.get_diagnostics() if runner else {}

        runner_state = diag.get("runner_state", "idle")
        if runner_state in ("idle", "running", "warming_up"):
            worker_state = "online"
        elif runner_state == "failed":
            worker_state = "error"
        elif runner_state == "stopped":
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
            "mt5_state": diag.get("mt5_state"),
            "account_id": diag.get("account_id"),
            "broker": diag.get("broker"),
            "active_strategies": active_strategies,
            "open_positions_count": diag.get("open_positions_count", 0),
            "floating_pnl": diag.get("floating_pnl", 0.0),
            "errors": errors,
            # Pipeline
            "total_ticks": diag.get("total_ticks", 0),
            "total_bars": diag.get("total_bars", 0),
            "current_bars_in_memory": diag.get("current_bars_in_memory", 0),
            "on_bar_calls": diag.get("on_bar_calls", 0),
            "signal_count": diag.get("signal_count", 0),
            "last_bar_time": str(diag["last_bar_time"]) if diag.get("last_bar_time") else None,
            "current_price": diag.get("current_price"),
            # MT5 account data (for portfolio)
            "account_balance": diag.get("account_balance"),
            "account_equity": diag.get("account_equity"),
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

    # ── Trade Reporting (Bug 13/18/19 fix) ──────────────────

    def _report_trade(self, report: dict):
        """Report a closed trade to Mother server AND save to local ledger."""
        # 1. Save to local TradeLedger
        try:
            self._ledger.add_trade(
                report,
                deployment_id=report.get("deployment_id"),
                strategy_id=report.get("strategy_id"),
            )
            print(f"[TRADE] Saved locally: {report.get('direction')} "
                  f"{report.get('symbol')} profit={report.get('profit', 0):.2f}")
        except Exception as e:
            print(f"[ERROR] Local trade save failed: {e}")

        # 2. POST to Mother Server
        payload = {
            "trade_id": report.get("id"),
            "deployment_id": report.get("deployment_id"),
            "strategy_id": report.get("strategy_id"),
            "worker_id": report.get("worker_id"),
            "symbol": report.get("symbol", ""),
            "direction": report.get("direction", ""),
            "entry_price": report.get("entry_price", 0),
            "exit_price": report.get("exit_price"),
            "entry_time": str(report.get("entry_time", "")),
            "exit_time": str(report.get("exit_time", "")),
            "exit_reason": report.get("exit_reason"),
            "sl_level": report.get("sl_level"),
            "tp_level": report.get("tp_level"),
            "lot_size": report.get("lot_size", 0.01),
            "ticket": report.get("ticket"),
            "points_pnl": report.get("points_pnl", 0),
            "profit": report.get("profit", 0),
            "bars_held": report.get("bars_held", 0),
        }
        endpoint = f"{self.mother_url}/api/portfolio/trades/report"
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[TRADE] Reported to Mother: {payload.get('direction')} "
                      f"{payload.get('symbol')} profit={payload.get('profit', 0):.2f}")
            else:
                print(f"[ERROR] Trade report HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[ERROR] Trade report to Mother failed: {e}")

    # ── Command Polling ─────────────────────────────────────

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

    def _report_runner_status(self, status: dict):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/runner-status"
        try:
            requests.post(endpoint, json=status, timeout=10)
        except Exception as e:
            print(f"[ERROR] Runner status report failed: {e}")

    # ── Deploy / Stop ───────────────────────────────────────

    def _handle_deploy(self, payload: dict):
        with self._runner_lock:
            if self._runner:
                # Bug 20 fix: log clear warning when replacing existing runner
                print(f"[WARNING] Replacing existing runner "
                      f"(deployment={self._runner.deployment_id}) "
                      f"with new deployment {payload.get('deployment_id')}. "
                      f"Only one runner per worker is supported.")
                self._runner.stop()
                self._runner = None

            # Inject worker_id so StrategyRunner can include it in trade reports
            payload["worker_id"] = self.worker_id

            runner = StrategyRunner(
                deployment_config=payload,
                status_callback=self._report_runner_status,
                trade_callback=self._report_trade,
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

    # ── Main Loop ───────────────────────────────────────────

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
        print(f"  Trade Ledger: data/portfolio_{self.worker_id}.db")
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
            sys.exit(0)

