# app/routes/emissions.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.utils.emission_calc import compute_run_energy_and_emission

router = APIRouter(
    prefix="/emissions",
    tags=["Emissions"],
)


@router.post("/recalc/{run_id}")
def recalc_emission_for_run(run_id: int, db: Session = Depends(get_db)):
    """
    İstersen Swagger'dan manuel olarak da bir run için
    enerji + emisyonu yeniden hesaplayıp kaydedebil.
    (Asıl hesap zaten stop_run içinde otomatik yapılıyor.)
    """

    # Run var mı?
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Metrikleri al
    metrics = (
        db.query(models.Metric)
        .filter(models.Metric.run_id == run_id)
        .order_by(models.Metric.ts.asc())
        .all()
    )

    if len(metrics) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough metrics to compute emission"
        )

    # Enerji + karbon hesabı
    energy_kwh, emission_kg = compute_run_energy_and_emission(metrics, region="TR")

    # Emission kaydı var mı, varsa güncelle; yoksa oluştur
    emission = (
        db.query(models.Emission)
        .filter(models.Emission.run_id == run_id)
        .first()
    )

    if emission is None:
        emission = models.Emission(
            run_id=run_id,
            energy_kwh=energy_kwh,
            emission_kg=emission_kg,
            region_code="TR",
        )
        db.add(emission)
    else:
        emission.energy_kwh = energy_kwh
        emission.emission_kg = emission_kg
        emission.region_code = "TR"

    db.commit()
    db.refresh(emission)

    return {
        "run_id": run_id,
        "energy_kwh": energy_kwh,
        "emission_kg": emission_kg,
        "region_code": emission.region_code,
    }
