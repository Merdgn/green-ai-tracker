# app/routes/metrics.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


# =============================
# 1) MANUEL metric oluşturma
# =============================
@router.post("/", response_model=schemas.MetricResponse, status_code=status.HTTP_201_CREATED)
def create_metric(metric_in: schemas.MetricCreate, db: Session = Depends(get_db)):

    run = db.query(models.Run).filter(models.Run.id == metric_in.run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")

    metric = models.Metric(**metric_in.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


# =============================
# 2) Bir çalışma (run) için tüm metrikleri getir
# =============================
@router.get("/by_run/{run_id}", response_model=list[schemas.MetricResponse])
def get_metrics_for_run(run_id: int, db: Session = Depends(get_db)):

    metrics = (
        db.query(models.Metric)
        .filter(models.Metric.run_id == run_id)
        .order_by(models.Metric.ts.asc())
        .all()
    )
    return metrics


# =============================
# 3) GERÇEK ZAMANLI METRİK TOPLAMA
# =============================
import time
import random
from datetime import datetime


def collect_metrics(run_id: int):
    """
    Her 3 saniyede bir CPU/GPU/POWER/RAM metriklerini üretip veritabanına kaydeder.
    Run durana kadar çalışır (ended_at dolana kadar).
    """
    from app.database import SessionLocal

    db = SessionLocal()

    try:
        while True:
            # Run durdu mu kontrol
            run = db.query(models.Run).filter(models.Run.id == run_id).first()
            if not run or run.ended_at is not None:
                break

            # Sahte metrik üretimi (gerçek zamanlı)
            metric = models.Metric(
                run_id=run_id,
                ts=datetime.utcnow(),
                cpu_util=random.randint(10, 95),
                gpu_util=random.randint(10, 99),
                gpu_power_w=random.uniform(50, 250),
                mem_used_mb=random.uniform(3000, 8000)
            )

            db.add(metric)
            db.commit()

            time.sleep(3)

    finally:
        db.close()
