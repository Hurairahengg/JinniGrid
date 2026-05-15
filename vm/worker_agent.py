"""
JINNI Grid - Worker Agent
Heartbeat + Command polling + Strategy Runner + Validation Runner + Chart flush.
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

from core.strategy_worker import StrategyRunner
from core.validation_runner import ValidationRunner
from trading.portfolio import TradeLedger


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
        self.agent_version = config["agent"].get("version", "0.2.0")
        self.host = detect_host()

        self._runner: StrategyRunner | None = None
        self._runner_lock = threading.Lock()

        # Validation runners (can run multiple)
        self._validation_runners: dict = {}  # job_id -> ValidationRunner
        self._validation_lock = threading.Lock()

        # Local trade ledger for persistence
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
            "total_ticks": diag.get("total_ticks", 0),
            "total_bars": diag.get("total_bars", 0),
            "current_bars_in_memory": diag.get("current_bars_in_memory", 0),
            "on_bar_calls": diag.get("on_bar_calls", 0),
            "signal_count": diag.get("signal_count", 0),
            "last_bar_time": str(diag["last_bar_time"]) if diag.get("last_bar_time") else None,
            "current_price": diag.get("current_price"),
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

    # ── Trade Reporting ─────────────────────────────────────

    def _report_trade(self, report: dict):
        try:
            self._ledger.add_trade(
                report,
                deployment_id=report.get("deployment_id"),
                strategy_id=report.get("strategy_id"),
            )
        except Exception as e:
            print(f"[ERROR] Local trade save failed: {e}")

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
                print(f"[TRADE] Reported to Mother")
            else:
                print(f"[ERROR] Trade report HTTP {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Trade report failed: {e}")

    # ── Chart Data Flush ────────────────────────────────────

    def _flush_chart_data(self):
        """Drain bars + markers from runner and POST to Mother."""
        runner = self._runner
        if runner is None:
            return
        dep_id = runner.deployment_id

        # Drain bars
        bars = runner.drain_chart_bars()
        if bars:
            try:
                requests.post(
                    f"{self.mother_url}/api/charts/bars",
                    json={"deployment_id": dep_id, "bars": bars},
                    timeout=10,
                )
            except Exception as e:
                print(f"[CHART] Bar flush failed ({len(bars)} bars): {e}")

        # Drain markers
        markers = runner.drain_chart_markers()
        if markers:
            try:
                requests.post(
                    f"{self.mother_url}/api/charts/markers",
                    json={"deployment_id": dep_id, "markers": markers},
                    timeout=10,
                )
            except Exception as e:
                print(f"[CHART] Marker flush failed ({len(markers)} markers): {e}")

    # ── Validation Callbacks ────────────────────────────────

    def _validation_progress_cb(self, data: dict):
        endpoint = f"{self.mother_url}/api/validation/jobs/{data['job_id']}/progress"
        try:
            requests.post(endpoint, json=data, timeout=10)
        except Exception as e:
            print(f"[VALIDATION] Progress report failed: {e}")

    def _validation_results_cb(self, data: dict):
        endpoint = f"{self.mother_url}/api/validation/jobs/{data['job_id']}/results"
        try:
            resp = requests.post(endpoint, json=data, timeout=30)
            if resp.status_code == 200:
                print(f"[VALIDATION] Results sent for job {data['job_id']}")
            else:
                print(f"[VALIDATION] Results POST failed: {resp.status_code}")
        except Exception as e:
            print(f"[VALIDATION] Results send failed: {e}")

        # Cleanup runner
        with self._validation_lock:
            self._validation_runners.pop(data["job_id"], None)

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
        elif cmd_type == "run_validation":
            self._handle_validation(payload)
        elif cmd_type == "stop_validation":
            self._handle_stop_validation(payload)
        else:
            print(f"[COMMAND] Unknown command type: {cmd_type}")

    def _ack_command(self, command_id: str):
        endpoint = f"{self.mother_url}/api/grid/workers/{self.worker_id}/commands/ack"
        try:
            requests.post(endpoint, json={"command_id": command_id}, timeout=10)
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
                print(f"[WARNING] Replacing existing runner")
                self._runner.stop()
                self._runner = None
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

    # ── Validation ──────────────────────────────────────────

    def _handle_validation(self, payload: dict):
        job_id = payload.get("job_id")
        if not job_id:
            print("[VALIDATION] No job_id in payload")
            return

        with self._validation_lock:
            if job_id in self._validation_runners:
                print(f"[VALIDATION] Job {job_id} already running")
                return

            runner = ValidationRunner(
                job_config=payload,
                progress_callback=self._validation_progress_cb,
                results_callback=self._validation_results_cb,
            )
            self._validation_runners[job_id] = runner
            runner.start()
            print(f"[VALIDATION] Started job {job_id}")

    def _handle_stop_validation(self, payload: dict):
        job_id = payload.get("job_id")
        if not job_id:
            return
        with self._validation_lock:
            runner = self._validation_runners.pop(job_id, None)
            if runner:
                runner.stop()
                print(f"[VALIDATION] Stopped job {job_id}")

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
        print("=" * 56)
        print("")

        _loop_counter = 0
        try:
            while True:
                self.send_heartbeat()
                self.poll_commands()

                # ★ Flush chart data every loop (same cadence as heartbeat)
                self._flush_chart_data()

                _loop_counter += 1
                time.sleep(self.heartbeat_interval)

        except KeyboardInterrupt:
            print(f"\n[SHUTDOWN] Stopping worker agent '{self.worker_id}'...")
            with self._runner_lock:
                if self._runner:
                    self._runner.stop()
            with self._validation_lock:
                for r in self._validation_runners.values():
                    r.stop()
            sys.exit(0)


def main():
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()