from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 1) Sayılar
    total_users = db.query(models.User).count()
    total_devices = db.query(models.Device).count()
    total_runs = db.query(models.Run).count()
    total_metrics = db.query(models.Metric).count()

    # 2) Toplam karbon emisyonu
    total_emission = db.query(func.sum(models.Emission.emission_kg)).scalar() or 0

    # 3) Ortalama CPU ve GPU
    avg_cpu = db.query(func.avg(models.Metric.cpu_util)).scalar() or 0
    avg_gpu = db.query(func.avg(models.Metric.gpu_util)).scalar() or 0

    # 4) Son 5 run
    last_runs = (
        db.query(models.Run)
        .order_by(models.Run.started_at.desc())
        .limit(5)
        .all()
    )

    # 5) En çok kullanılan model
    popular_model = (
        db.query(models.Run.model_name, func.count(models.Run.id))
        .group_by(models.Run.model_name)
        .order_by(func.count(models.Run.id).desc())
        .first()
    )

    popular_model_name = popular_model[0] if popular_model else None
    popular_model_count = popular_model[1] if popular_model else 0

    # 6) En uzun run (bitişi olanlar arasından)
    longest_run = (
        db.query(models.Run)
        .filter(models.Run.ended_at.isnot(None))
        .order_by((models.Run.ended_at - models.Run.started_at).desc())
        .first()
    )

    return {
        "total_users": total_users,
        "total_devices": total_devices,
        "total_runs": total_runs,
        "total_metrics": total_metrics,

        "total_emission_kg": total_emission,
        "avg_cpu": avg_cpu,
        "avg_gpu": avg_gpu,

        "popular_model": {
            "name": popular_model_name,
            "count": popular_model_count,
        },

        "longest_run": {
            "id": longest_run.id if longest_run else None,
            "duration_sec": (
                (longest_run.ended_at - longest_run.started_at).total_seconds()
                if longest_run else 0
            ),
        },

        "recent_runs": [
            {
                "id": r.id,
                "model_name": r.model_name,
                "started_at": r.started_at,   # FastAPI bunu ISO string’e çevirir
                "ended_at": r.ended_at,       # ← BURAYI EKLEDİK
                "user_id": r.user_id,
            }
            for r in last_runs
        ],
    }
