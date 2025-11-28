from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


# ============================
# USERS
# ============================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    api_key_hash = Column(String, nullable=False)
    role = Column(String, default="user")

    runs = relationship("Run", back_populates="user")


# ============================
# DEVICES
# ============================
class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    gpu_name = Column(String)
    cpu_name = Column(String)
    tdp_w = Column(Float)
    driver_version = Column(String)
    cuda_version = Column(String)

    runs = relationship("Run", back_populates="device")


# ============================
# RUNS
# ============================
class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    device_id = Column(Integer, ForeignKey("devices.id"))
    model_name = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    user = relationship("User", back_populates="runs")
    device = relationship("Device", back_populates="runs")
    metrics = relationship("Metric", back_populates="run")
    emission = relationship("Emission", back_populates="run", uselist=False)


# ============================
# METRICS
# ============================
class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    ts = Column(DateTime, default=datetime.utcnow)
    cpu_util = Column(Float)
    gpu_util = Column(Float)
    gpu_power_w = Column(Float)
    mem_used_mb = Column(Float)

    run = relationship("Run", back_populates="metrics")


# ============================
# EMISSIONS
# ============================
class Emission(Base):
    __tablename__ = "emissions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"))

    energy_kwh = Column(Float)
    emission_kg = Column(Float)
    region_code = Column(String)

    # 🔥 Eksik olan ilişki — eklendi!
    run = relationship("Run", back_populates="emission")

