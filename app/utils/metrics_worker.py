import time
import psutil
import subprocess
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app import models


def get_gpu_stats():
    """
    NVIDIA GPU varsa:
    GPU tüketimi (power in watts)
    GPU usage (%)
    """

    try:
        # GPU kullanım yüzdesi
        util_cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        gpu_util = int(subprocess.check_output(util_cmd).decode().strip())

        # GPU güç tüketimi (Watt)
        power_cmd = [
            "nvidia-smi",
            "--query-gpu=power.draw",
            "--format=csv,noheader,nounits"
        ]
        gpu_power = float(subprocess.check_output(power_cmd).decode().strip())

        return gpu_util, gpu_power

    except Exception:
        # NVIDIA yoksa simülasyon değerleri
        return 0, 0.0


def collect_metrics(run_id: int):
    """
    Bu fonksiyon arka planda sürekli çalışır.
    Gerçek CPU / GPU / RAM ölçümü alır ve DB’ye yazar.
    """

    print(f"[METRIC] Gerçek zamanlı ölçüm başlatıldı → run_id={run_id}")

    db: Session = SessionLocal()

    while True:
        # Run bitti mi kontrol et
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if run is None or run.ended_at is not None:
            print(f"[METRIC] Run sonlandırıldı → id={run_id}")
            break

        # CPU (%) ölç
        cpu_util = psutil.cpu_percent(interval=1)

        # GPU (%) ve güç (W)
        gpu_util, gpu_power = get_gpu_stats()

        # RAM kullanımı
        mem = psutil.virtual_memory()
        mem_used_mb = mem.used / 1024 / 1024

        # DB kaydı
        metric = models.Metric(
            run_id=run_id,
            cpu_util=cpu_util,
            gpu_util=gpu_util,
            gpu_power_w=gpu_power,
            mem_used_mb=mem_used_mb,
            ts=datetime.utcnow()
        )
        db.add(metric)
        db.commit()

        # Her 3 saniyede bir ölçüm al
        time.sleep(3)

    db.close()
