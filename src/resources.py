"""Fail closed on resource telemetry; observe only this job and system counters."""
import json
import re
import subprocess
import time
from pathlib import Path
import psutil

MIB = 1024 ** 2


def snapshot():
    pressure = subprocess.check_output(["memory_pressure", "-Q"], text=True, timeout=5)
    free = int(re.search(r"free percentage: (\d+)%", pressure).group(1))
    vm = subprocess.check_output(["vm_stat"], text=True, timeout=5)
    page_size = int(re.search(r"page size of (\d+) bytes", vm).group(1))
    swapouts = int(re.search(r"Swapouts:\s+(\d+)", vm).group(1)) * page_size
    swap = subprocess.check_output(["sysctl", "vm.swapusage"], text=True, timeout=5).strip()
    thermal = subprocess.check_output(["pmset", "-g", "therm"], text=True, timeout=5).strip()
    if "Failed" in thermal or "operation not permitted" in thermal:
        raise RuntimeError("Thermal telemetry unavailable in this execution environment")
    return {"time_unix": time.time(), "free_percent": free, "system_swapouts_bytes": swapouts,
            "swap_usage": swap, "thermal": thermal,
            "rss_mib": round(psutil.Process().memory_info().rss / MIB, 2)}


class Guard:
    def __init__(self, cfg, path, seconds):
        self.cfg, self.path, self.seconds = cfg, Path(path), seconds
        self.start = time.monotonic()
        self.initial = snapshot()
        self.last = 0
        self.record(self.initial)
        self.validate(self.initial)

    def record(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(data) + "\n")

    def validate(self, data):
        if data["free_percent"] < self.cfg["minimum_system_free_percent"]:
            raise RuntimeError("Stopped: system available-memory percentage below budget")
        if data["system_swapouts_bytes"] - self.initial["system_swapouts_bytes"] > self.cfg["max_system_swapout_growth_mib"] * MIB:
            raise RuntimeError("Stopped: system swap-outs grew beyond budget (global counter, not attributable to this process)")
        if data["rss_mib"] > self.cfg["max_process_rss_mib"]:
            raise RuntimeError("Stopped: process RSS exceeded budget")
        t = data["thermal"]
        for name in ["Thermal_Level", "CPU_Scheduler_Limit", "CPU_Speed_Limit"]:
            m = re.search(name + r"\s*=\s*(\d+)", t)
            if m and ((name == "Thermal_Level" and int(m.group(1)) > 0) or (name != "Thermal_Level" and int(m.group(1)) < 100)):
                raise RuntimeError("Stopped: recorded thermal/performance warning")

    def check(self, force=False):
        elapsed = time.monotonic() - self.start
        if elapsed > self.seconds:
            raise RuntimeError("Stopped: wall-clock budget exceeded")
        if force or elapsed - self.last >= 5:
            data = snapshot()
            data["elapsed_seconds"] = round(elapsed, 3)
            self.record(data)
            self.validate(data)
            self.last = elapsed


def cap_mlx(cfg):
    import mlx.core as mx
    mx.set_memory_limit(cfg["memory_limit_mib"] * MIB)
    mx.set_cache_limit(cfg["cache_limit_mib"] * MIB)
    mx.set_wired_limit(cfg["wired_limit_mib"] * MIB)
