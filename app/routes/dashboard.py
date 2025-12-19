from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    # 1) Temel sayılar
    total_users = db.query(models.User).count()
    total_devices = db.query(models.Device).count()
    total_runs = db.query(models.Run).count()
    total_metrics = db.query(models.Metric).count()

    # 2) Toplam emisyon
    total_emission = (
        db.query(func.coalesce(func.sum(models.Emission.emission_kg), 0.0))
        .scalar()
        or 0.0
    )

    # 3) En popüler model
    popular = (
        db.query(models.Run.model_name, func.count(models.Run.id).label("cnt"))
        .group_by(models.Run.model_name)
        .order_by(func.count(models.Run.id).desc())
        .first()
    )
    popular_model = {
        "name": popular.model_name if popular else None,
        "count": int(popular.cnt) if popular else 0,
    }

    # 4) Model bazında enerji / emisyon istatistikleri
    model_stats = (
        db.query(
            models.Run.model_name.label("model_name"),
            func.avg(models.Emission.energy_kwh).label("avg_energy"),
            func.sum(models.Emission.energy_kwh).label("sum_energy"),
            func.sum(models.Emission.emission_kg).label("sum_emission"),
        )
        .join(models.Emission, models.Emission.run_id == models.Run.id)
        .group_by(models.Run.model_name)
        .all()
    )

    if model_stats:
        avg_energy_per_model_kwh = float(
            sum(row.avg_energy for row in model_stats) / len(model_stats)
        )
        top_model_row = max(model_stats, key=lambda row: row.sum_emission)
        top_emitter_model = {
            "name": top_model_row.model_name,
            "total_emission_kg": float(top_model_row.sum_emission),
        }
    else:
        avg_energy_per_model_kwh = 0.0
        top_emitter_model = {"name": None, "total_emission_kg": 0.0}

    # 5) Global CPU / GPU ortalamaları
    avg_cpu = (
        db.query(func.coalesce(func.avg(models.Metric.cpu_util), 0.0)).scalar() or 0.0
    )
    avg_gpu = (
        db.query(func.coalesce(func.avg(models.Metric.gpu_util), 0.0)).scalar() or 0.0
    )

    # 6) Son 5 run
    recent_runs = (
        db.query(models.Run)
        .order_by(models.Run.started_at.desc())
        .limit(5)
        .all()
    )
    recent_runs_data = [
        {
            "id": r.id,
            "model_name": r.model_name,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "user_id": r.user_id,
        }
        for r in recent_runs
    ]

    # Şimdilik zaman serisi grafikleri boş gönderelim,
    # index.html bunları kullanmıyor
    cpu_time_labels = []
    cpu_values = []
    gpu_time_labels = []
    gpu_values = []

    return {
        "total_users": total_users,
        "total_devices": total_devices,
        "total_runs": total_runs,
        "total_metrics": total_metrics,
        "total_emission_kg": float(total_emission),
        "popular_model": popular_model,
        "avg_energy_per_model_kwh": avg_energy_per_model_kwh,
        "top_emitter_model": top_emitter_model,
        "avg_cpu": float(avg_cpu),
        "avg_gpu": float(avg_gpu),
        "longest_run": None,  # istersen sonra tekrar eklersin
        "recent_runs": recent_runs_data,
        "cpu_time_labels": cpu_time_labels,
        "cpu_values": cpu_values,
        "gpu_time_labels": gpu_time_labels,
        "gpu_values": gpu_values,
    }
