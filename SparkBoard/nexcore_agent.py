#!/usr/bin/env python3
"""
NexCore :: Device Agent
=======================
Runs on any device (Pi 5, gaming desktop - Linux or Windows).
Collects local metrics every 5 seconds and POSTs them to the CM4 hub.

DEPENDENCIES:
    pip install psutil requests

── LINUX SETUP (Pi 5 / Desktop) ──────────────────────────────────────────
Create /etc/systemd/system/nexcore-agent.service:

    [Unit]
    Description=NexCore Device Agent
    After=network.target

    [Service]
    ExecStart=/usr/bin/python3 /home/<user>/nexcore_agent.py
    Restart=always
    User=<user>
    Environment=HUB_IP=192.168.1.XXX

    [Install]
    WantedBy=multi-user.target

Then: sudo systemctl enable --now nexcore-agent

── WINDOWS SETUP (Gaming Desktop) ────────────────────────────────────────
Option A — Startup folder (simple):
  Press Win+R → shell:startup
  Create a shortcut to:  pythonw.exe C:\\path\\to\\nexcore_agent.py

Option B — Task Scheduler:
  Action: Start a program
  Program: pythonw.exe
  Arguments: C:\\path\\to\\nexcore_agent.py
  Trigger: At log on

Set HUB_IP below or as an environment variable.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import time
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    raise SystemExit("psutil not found. Run: pip install psutil")

try:
    import urllib.request as _req
    def _post(url: str, data: bytes) -> None:
        req = _req.Request(url, data=data,
                           headers={"Content-Type": "application/json"})
        with _req.urlopen(req, timeout=5):
            pass
except Exception:
    pass

# ── Config ────────────────────────────────────────────────────────────────
# Set HUB_IP to your CM4's local IP address.
# Find it by running: hostname -I   on the CM4.
HUB_IP       = os.environ.get("HUB_IP", "192.168.1.XXX")   # ← change this
HUB_PORT     = 9500
PUSH_INTERVAL = 5   # seconds between pushes
DEVICE_NAME  = os.environ.get("NEXCORE_NAME", socket.gethostname())


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _cpu_temp() -> Optional[float]:
    """Return CPU temp in °C if available, else None."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Try common sensor names across platforms
        for key in ("coretemp", "cpu_thermal", "cpu-thermal", "k10temp", "acpitz"):
            if key in temps:
                entries = temps[key]
                if entries:
                    return round(entries[0].current, 1)
        # Fall back to first available
        for entries in temps.values():
            if entries:
                return round(entries[0].current, 1)
    except Exception:
        pass
    return None


def _disks() -> list[dict]:
    """Return all mounted real disk partitions with usage stats."""
    results = []
    for part in psutil.disk_partitions(all=False):
        # Skip optical drives and pseudo-filesystems
        if part.fstype in ("", "tmpfs", "devtmpfs", "squashfs", "overlay"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            results.append({
                "mount":   part.mountpoint,
                "device":  part.device,
                "fstype":  part.fstype,
                "total_gb": round(usage.total / 1e9, 1),
                "used_gb":  round(usage.used  / 1e9, 1),
                "free_gb":  round(usage.free  / 1e9, 1),
                "percent":  usage.percent,
            })
        except PermissionError:
            pass
    return results


def _net_stats() -> dict:
    """Return per-interface network counters."""
    counters = psutil.net_io_counters(pernic=True)
    result   = {}
    for iface, c in counters.items():
        # Skip loopback and virtual interfaces
        if iface.startswith(("lo", "veth", "docker", "br-")):
            continue
        result[iface] = {
            "bytes_sent":   c.bytes_sent,
            "bytes_recv":   c.bytes_recv,
            "packets_sent": c.packets_sent,
            "packets_recv": c.packets_recv,
            "errin":        c.errin,
            "errout":       c.errout,
            "dropin":       c.dropin,
            "dropout":      c.dropout,
        }
    return result


def _top_processes(n: int = 5) -> list[dict]:
    """Return top N processes by CPU usage."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append({
                "pid":    p.info["pid"],
                "name":   p.info["name"],
                "cpu":    round(p.info["cpu_percent"] or 0.0, 1),
                "mem":    round(p.info["memory_percent"] or 0.0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(procs, key=lambda x: x["cpu"], reverse=True)[:n]


def collect() -> dict:
    """Collect a full snapshot of this device's metrics."""
    vm  = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)

    return {
        "hostname":    DEVICE_NAME,
        "platform":    platform.system(),        # 'Linux' or 'Windows'
        "timestamp":   _now(),
        "cpu_percent": cpu,
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used  / 1e9, 2),
        "ram_total_gb":round(vm.total / 1e9, 2),
        "cpu_temp_c":  _cpu_temp(),
        "disks":       _disks(),
        "network":     _net_stats(),
        "top_procs":   _top_processes(5),
    }


def push(payload: dict) -> bool:
    url  = f"http://{HUB_IP}:{HUB_PORT}/metrics"
    body = json.dumps(payload).encode()
    try:
        _post(url, body)
        return True
    except Exception as exc:
        print(f"[{_now()}] Push failed: {exc}")
        return False


if __name__ == "__main__":
    if HUB_IP == "192.168.1.XXX":
        print("WARNING: HUB_IP is not set. Edit nexcore_agent.py or set HUB_IP env var.")

    print(f"NexCore agent starting on {DEVICE_NAME} → {HUB_IP}:{HUB_PORT}")
    # First cpu_percent call always returns 0.0 — call it once to prime
    psutil.cpu_percent(interval=None)

    while True:
        data = collect()
        ok   = push(data)
        status = "✓" if ok else "✗"
        print(f"[{data['timestamp']}] {status} cpu={data['cpu_percent']}% "
              f"ram={data['ram_percent']}%")
        time.sleep(PUSH_INTERVAL)
