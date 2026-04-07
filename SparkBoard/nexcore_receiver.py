#!/usr/bin/env python3
"""
NexCore :: Hub Receiver
=======================
Runs on the CM4 hub. Listens for incoming metric payloads from
nexcore_agent.py running on remote devices, and writes them to
~/.nexcore/data/agent_data.json so sparkboard.py can read them.

SETUP (CM4 - run once):
    pip install psutil
    python3 nexcore_receiver.py &

Or as a systemd service — create /etc/systemd/system/nexcore-receiver.service:
    [Unit]
    Description=NexCore Hub Receiver
    After=network.target

    [Service]
    ExecStart=/usr/bin/python3 /home/pi/nexcore_receiver.py
    Restart=always
    User=pi

    [Install]
    WantedBy=multi-user.target

Then: sudo systemctl enable --now nexcore-receiver
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Config ────────────────────────────────────────────────────────────────
LISTEN_HOST = "0.0.0.0"   # accept from any device on the network
LISTEN_PORT = 9500         # agents POST to http://<CM4_IP>:9500/metrics
DATA_DIR    = os.path.join(os.path.expanduser("~"), ".nexcore", "data")
AGENT_FILE  = os.path.join(DATA_DIR, "agent_data.json")
STALE_SECS  = 60           # mark device offline after this many seconds


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ── Shared in-memory store (thread-safe via lock) ─────────────────────────
_lock   = threading.Lock()
_agents: dict[str, dict] = {}   # keyed by device hostname


def _load_existing() -> None:
    """Restore last-known state from disk on startup."""
    try:
        if os.path.exists(AGENT_FILE):
            with open(AGENT_FILE, "r") as f:
                data = json.load(f)
            with _lock:
                _agents.update(data)
    except Exception:
        pass


def _save() -> None:
    _ensure_dir()
    with _lock:
        snapshot = dict(_agents)
    with open(AGENT_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)


# ── HTTP handler ──────────────────────────────────────────────────────────

class MetricsHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress default noisy logging; errors still print
        pass

    def do_POST(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length  = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            host    = payload.get("hostname", self.client_address[0])

            payload["received_at"] = _now_str()
            payload["online"]      = True

            with _lock:
                _agents[host] = payload

            _save()

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def do_GET(self):
        """Allow sparkboard to also pull latest data via HTTP if needed."""
        if self.path == "/status":
            with _lock:
                data = dict(_agents)
            body = json.dumps(data, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


# ── Stale-device watchdog ─────────────────────────────────────────────────

def _watchdog() -> None:
    """Mark devices as offline if we haven't heard from them recently."""
    while True:
        time.sleep(15)
        now = datetime.now(timezone.utc)
        changed = False
        with _lock:
            for host, data in _agents.items():
                try:
                    last = datetime.strptime(
                        data["received_at"], "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                    if (now - last).total_seconds() > STALE_SECS:
                        if data.get("online", True):
                            data["online"] = False
                            changed = True
                except Exception:
                    pass
        if changed:
            _save()


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_dir()
    _load_existing()

    threading.Thread(target=_watchdog, daemon=True).start()

    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), MetricsHandler)
    print(f"NexCore receiver listening on {LISTEN_HOST}:{LISTEN_PORT}")
    print(f"Agent data → {AGENT_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
