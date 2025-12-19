# app/routes/monitor.py
from __future__ import annotations

import threading
import time
import subprocess
from typing import Optional, Dict, Any

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# -----------------------------
# Ayarlar (istersen sonra config'e alırız)
# -----------------------------
GRID_KG_PER_KWH = 0.42          # TR için kaba değer (seninkiyle aynı)
BASE_W = 8.0                    # laptop boşta taban güç (yaklaşık)
CPU_TDP_W = 45.0                # laptop CPU için yaklaşık (istersen modele göre düzeltiriz)
RAM_W_PER_GB = 0.35             # yaklaşık

SAMPLE_PERIOD_S = 1.0           # GERÇEK 1 saniyelik ölçüm döngüsü

# -----------------------------
# NVML (öncelikli kaynak)
# -----------------------------
_NVML_OK = False
_NVML_ERR: Optional[str] = None
_GPU_HANDLE = None
_GPU_NAME: Optional[str] = None

try:
    from pynvml import (  # type: ignore
        nvmlInit,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetName,
        nvmlDeviceGetUtilizationRates,
        nvmlDeviceGetPowerUsage,      # milliWatt döner
        nvmlDeviceGetMemoryInfo,
    )

    try:
        nvmlInit()
        _GPU_HANDLE = nvmlDeviceGetHandleByIndex(0)
        name = nvmlDeviceGetName(_GPU_HANDLE)
        _GPU_NAME = name.decode("utf-8", "ignore") if isinstance(name, (bytes, bytearray)) else str(name)
        _NVML_OK = True
    except Exception as e:
        _NVML_OK = False
        _NVML_ERR = str(e)

except Exception as e:
    _NVML_OK = False
    _NVML_ERR = f"pynvml import failed: {e}"

def _read_gpu_nvml() -> Dict[str, Any]:
    """
    NVML'den GPU kullanımını okur.
    Kısa süreli spike'larda 0 görmemek için 2 ölçüm alıp maksimumunu kullanır.
    """
    if not _NVML_OK or _GPU_HANDLE is None:
        return {"ok": False, "err": _NVML_ERR or "NVML not available"}

    try:
        import pynvml

        # 1. örnek
        util1  = float(pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE).gpu)
        power1 = float(pynvml.nvmlDeviceGetPowerUsage(_GPU_HANDLE)) / 1000.0  # mW -> W
        mem1   = float(pynvml.nvmlDeviceGetMemoryInfo(_GPU_HANDLE).used) / (1024 * 1024)

        # Çok kısa bir bekleme (50ms)
        time.sleep(0.05)

        # 2. örnek
        util2  = float(pynvml.nvmlDeviceGetUtilizationRates(_GPU_HANDLE).gpu)
        power2 = float(pynvml.nvmlDeviceGetPowerUsage(_GPU_HANDLE)) / 1000.0
        mem2   = float(pynvml.nvmlDeviceGetMemoryInfo(_GPU_HANDLE).used) / (1024 * 1024)

        util    = max(util1, util2)
        power_w = max(power1, power2)
        mem_mb  = max(mem1, mem2)

        return {
            "ok": True,
            "util": util,
            "power_w": power_w,
            "mem_mb": mem_mb,
            "name": _GPU_NAME or "NVIDIA GPU",
            "err": None,
        }
    except Exception as e:
        return {"ok": False, "err": str(e)}


def _read_gpu_nvidia_smi() -> Dict[str, Any]:
    """
    NVML kullanılamıyorsa yedek olarak nvidia-smi çıktısını okuyarak
    GPU kullanımını döndürür.
    """
    try:
        # utilization.gpu: yüzde
        # power.draw: Watt
        # memory.used: MiB
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,power.draw,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1.0,
        )

        if result.returncode != 0:
            return {"ok": False, "err": result.stderr.strip() or "nvidia-smi failed"}

        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]

        if len(parts) < 3:
            return {"ok": False, "err": f"unexpected nvidia-smi output: {line!r}"}

        util = float(parts[0])        # %
        power_w = float(parts[1])     # W
        mem_mb = float(parts[2])      # MiB ~ MB

        return {
            "ok": True,
            "util": util,
            "power_w": power_w,
            "mem_mb": mem_mb,
            "name": _GPU_NAME or "NVIDIA GPU",
            "err": None,
        }

    except Exception as e:
        return {"ok": False, "err": str(e)}


# -----------------------------
# Arka plan sampler state (cache)
# -----------------------------
_lock = threading.Lock()

_state: Dict[str, Any] = {
    "ts": time.time(),
    "dt_s": 0.0,

    "cpu": 0.0,
    "ram": 0.0,

    "gpu": 0.0,
    "power_gpu_w": 0.0,
    "gpu_mem_used_mb": 0.0,
    "gpu_name": _GPU_NAME or "NVIDIA GPU",
    "source": "nvml" if _NVML_OK else "nvidia-smi",
    "err": None,

    "power_cpu_est_w": 0.0,
    "power_ram_est_w": 0.0,
    "power_base_w": BASE_W,
    "power_total_w": 0.0,

    "energy_kwh_total": 0.0,
    "energy_kwh_gpu": 0.0,
    "co2_total_kg": 0.0,
    "co2_gpu_kg": 0.0,
    "grid_kg_per_kwh": GRID_KG_PER_KWH,

    "nvml_status": {"ok": _NVML_OK, "err": _NVML_ERR},
}

_last_mono = time.monotonic()


def _sampler_loop():
    global _last_mono

    # cpu_percent'i “ısındır”
    psutil.cpu_percent(interval=None)

    while True:
        t0 = time.monotonic()
        dt = max(t0 - _last_mono, 1e-6)
        _last_mono = t0

        # CPU / RAM
        cpu = float(psutil.cpu_percent(interval=None))       # non-blocking
        ram_mb = float(psutil.virtual_memory().used) / (1024 * 1024)

        # -----------------------------
        # GPU: Önce NVML, hata alırsak nvidia-smi'ye düş
        # -----------------------------
        g: Dict[str, Any] = {"ok": False, "err": "no source"}
        source = "none"
        nvml_status = {"ok": _NVML_OK, "err": _NVML_ERR}

        if _NVML_OK:
            g_nvml = _read_gpu_nvml()
            nvml_status = {"ok": bool(g_nvml.get("ok")), "err": g_nvml.get("err")}
            if g_nvml.get("ok"):
                g = g_nvml
                source = "nvml"
            else:
                # NVML handle var ama ok=False (Unknown Error gibi) → yedek olarak nvidia-smi dene
                g = _read_gpu_nvidia_smi()
                source = "nvidia-smi"
        else:
            # Başta NVML hiç açılmadıysa direkt nvidia-smi kullan
            g = _read_gpu_nvidia_smi()
            source = "nvidia-smi"

        gpu_util    = float(g.get("util", 0.0)) if g.get("ok") else 0.0
        gpu_power_w = float(g.get("power_w", 0.0)) if g.get("ok") else 0.0
        gpu_mem_mb  = float(g.get("mem_mb", 0.0)) if g.get("ok") else 0.0
        gpu_name    = g.get("name") or (_GPU_NAME or "NVIDIA GPU")
        err         = None if g.get("ok") else g.get("err")

        # Basit güç tahmini (CPU/RAM): burada “yaklaşık” hesap yapıyoruz
        power_cpu_est = CPU_TDP_W * (cpu / 100.0)
        ram_gb        = ram_mb / 1024.0
        power_ram_est = RAM_W_PER_GB * ram_gb

        power_total = BASE_W + power_cpu_est + power_ram_est + gpu_power_w

        # Enerji entegrasyonu (kWh)
        energy_kwh_total_add = (power_total * dt) / 3600.0 / 1000.0
        energy_kwh_gpu_add   = (gpu_power_w * dt)   / 3600.0 / 1000.0

        with _lock:
            _state["ts"]      = time.time()
            _state["dt_s"]    = round(dt, 3)

            _state["cpu"]     = round(cpu, 2)
            _state["ram"]     = round(ram_mb, 2)

            _state["gpu"]          = round(gpu_util, 2)
            _state["power_gpu_w"]  = round(gpu_power_w, 2)
            _state["gpu_mem_used_mb"] = round(gpu_mem_mb, 2)
            _state["gpu_name"]     = gpu_name
            _state["source"]       = source
            _state["err"]          = err

            _state["power_cpu_est_w"] = round(power_cpu_est, 3)
            _state["power_ram_est_w"] = round(power_ram_est, 3)
            _state["power_base_w"]    = BASE_W
            _state["power_total_w"]   = round(power_total, 3)

            _state["energy_kwh_total"] += energy_kwh_total_add
            _state["energy_kwh_gpu"]   += energy_kwh_gpu_add

            _state["co2_total_kg"] = _state["energy_kwh_total"] * GRID_KG_PER_KWH
            _state["co2_gpu_kg"]   = _state["energy_kwh_gpu"]   * GRID_KG_PER_KWH

            _state["grid_kg_per_kwh"] = GRID_KG_PER_KWH
            _state["nvml_status"]     = nvml_status

        # Tam 1 saniyeye yakınla
        elapsed = time.monotonic() - t0
        sleep_s = max(0.0, SAMPLE_PERIOD_S - elapsed)
        time.sleep(sleep_s)


# Sampler thread'i başlat
_thread = threading.Thread(target=_sampler_loop, daemon=True)
_thread.start()


@router.get("/monitor")
def monitor_page(request: Request):
    return templates.TemplateResponse("monitor.html", {"request": request})


@router.get("/monitor/live")
def monitor_live():
    with _lock:
        return JSONResponse(dict(_state))
