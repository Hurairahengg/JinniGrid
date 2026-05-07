"""
JINNI Grid - Command Queue
Simple in-memory per-worker command queue.
Workers poll for pending commands, ack when received.
command_queue.py 
"""
import threading
import uuid
from datetime import datetime, timezone

_queues: dict = {}  # worker_id -> list of commands
_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    """Push a command for a specific worker."""
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    cmd = {
        "command_id": cmd_id,
        "worker_id": worker_id,
        "command_type": command_type,
        "payload": payload,
        "state": "pending",
        "created_at": now.isoformat(),
        "acked_at": None,
    }

    with _lock:
        if worker_id not in _queues:
            _queues[worker_id] = []
        _queues[worker_id].append(cmd)

    print(f"[COMMAND] Enqueued {command_type} ({cmd_id}) for worker {worker_id}")
    return cmd


def poll_commands(worker_id: str) -> list:
    """Return all pending commands for a worker."""
    with _lock:
        queue = _queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    """Mark a command as acknowledged."""
    now = datetime.now(timezone.utc)
    with _lock:
        queue = _queues.get(worker_id, [])
        for cmd in queue:
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                print(f"[COMMAND] Ack {command_id} from worker {worker_id}")
                return {"ok": True, "command": cmd}
    return {"ok": False, "error": "Command not found."}