import threading
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routes.metrics import collect_metrics
from app.utils.emission_calc import compute_run_energy_and_emission

router = APIRouter(
    prefix="/runs",
    tags=["Runs"]
)


# ============================
# 1) Çalışma Listesi
# ============================
@router.get("/", response_model=List[schemas.RunResponse])
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(models.Run).order_by(models.Run.id.asc()).all()
    return runs


# ============================
# 2) Yeni Çalışma Oluştur
# ============================
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_run(data: dict, db: Session = Depends(get_db)):
    model_name = data.get("model_name")

    if not model_name:
        raise HTTPException(status_code=400, detail="model_name gerekli")

    # Varsayılan kullanıcı ve cihaz
    default_user = db.query(models.User).first()
    default_device = db.query(models.Device).first()

    if not default_user or not default_device:
        raise HTTPException(status_code=400, detail="Varsayılan kullanıcı veya cihaz bulunamadı")

    run = models.Run(
        user_id=default_user.id,
        device_id=default_device.id,
        model_name=model_name,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {"id": run.id, "model_name": run.model_name}


# ============================
# 3) Belirli Çalışmayı Getir
# ============================
@router.get("/{run_id}", response_model=schemas.RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")
    return run


# ============================
# 4) Çalışmayı Sonlandır (ended_at doldur)
# ============================
@router.post("/{run_id}/stop", response_model=schemas.RunResponse)
def stop_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")

    if run.ended_at is not None:
        raise HTTPException(status_code=400, detail="Run zaten sonlandırılmış")

    # Run'ı şu an itibariyle bitir
    run.ended_at = datetime.utcnow()
    db.add(run)
    db.commit()
    db.refresh(run)

    # === ENERJİ & EMİSYON HESAPLAMA ===
    metrics = (
        db.query(models.Metric)
        .filter(models.Metric.run_id == run_id)
        .order_by(models.Metric.ts.asc())
        .all()
    )

    energy_kwh, emission_kg = compute_run_energy_and_emission(metrics, region="TR")

    emission_record = models.Emission(
        run_id=run_id,
        energy_kwh=energy_kwh,
        emission_kg=emission_kg,
        region_code="TR",
    )
    db.add(emission_record)
    db.commit()

    return run


# ============================
# 5) CANLI METRİK ENDPOINTİ
# ============================
@router.get("/{run_id}/live")
def get_live_metrics(run_id: int, db: Session = Depends(get_db)):

    metrics = (
        db.query(models.Metric)
        .filter(models.Metric.run_id == run_id)
        .order_by(models.Metric.ts.asc())
        .all()
    )

    run = db.query(models.Run).filter(models.Run.id == run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")

    return {
        "status": "running" if run.ended_at is None else "finished",
        "metrics": [
            {
                "time": m.ts.isoformat(),
                "cpu": m.cpu_util,
                "gpu": m.gpu_util,
                "ram": m.mem_used_mb,
                "power": m.gpu_power_w
            }
            for m in metrics
        ]
    }
