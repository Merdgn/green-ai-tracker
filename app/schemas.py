# app/schemas.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict



# =========================
# USER SCHEMAS
# =========================
class UserBase(BaseModel):
    name: str
    email: str | None = None


class UserCreate(UserBase):
    api_key: str  # şimdilik düz, sonra hash'leriz


class UserResponse(UserBase):
    id: int
    role: str

    model_config = ConfigDict(from_attributes=True)



# =========================
# DEVICE SCHEMAS
# =========================
class DeviceBase(BaseModel):
    gpu_name: str | None = None
    cpu_name: str | None = None
    tdp_w: float | None = None
    driver_version: str | None = None
    cuda_version: str | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceResponse(DeviceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# =========================
# RUN SCHEMAS
# =========================
class RunBase(BaseModel):
    user_id: int
    device_id: int
    model_name: str
    notes: str | None = None


class RunCreate(RunBase):
    pass


class RunResponse(RunBase):
    id: int
    started_at: datetime
    ended_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# =========================
# METRIC SCHEMAS
# =========================
class MetricBase(BaseModel):
    run_id: int
    cpu_util: float | None = None
    gpu_util: float | None = None
    gpu_power_w: float | None = None
    mem_used_mb: float | None = None


class MetricCreate(MetricBase):
    """Ölçüm gönderirken kullanılacak schema."""
    pass


class MetricResponse(MetricBase):
    id: int
    ts: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================
# EMISSION SCHEMAS
# =========================
class EmissionBase(BaseModel):
    run_id: int
    energy_kwh: float
    emission_kg: float
    region_code: str


class EmissionCreate(EmissionBase):
    pass


class EmissionResponse(EmissionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

