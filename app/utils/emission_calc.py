import math


# Türkiye için ortalama elektrik karışımı (kg CO2 / kWh)
CO2_FACTOR_TR = 0.42


def power_to_kwh(power_watts: float, duration_seconds: float) -> float:
    """
    Basit enerji hesabı: (Watt * saniye) → kWh
    1 kWh = 1000 Watt * 3600 saniye
    """
    if power_watts <= 0 or duration_seconds <= 0:
        return 0.0

    kwh = (power_watts * duration_seconds) / (1000 * 3600)
    return kwh


def calculate_emission(kwh: float, region: str = "TR") -> float:
    """
    kWh → CO2 (kg)
    Şimdilik sadece Türkiye için hesaplama yapıyoruz.
    """
    if kwh <= 0:
        return 0.0

    if region == "TR":
        return kwh * CO2_FACTOR_TR

    # İleride farklı bölgeler eklenebilir
    return kwh * CO2_FACTOR_TR


def compute_run_energy_and_emission(metrics: list, region: str = "TR"):
    """
    Bir run'a ait tüm metriklerden enerji & karbon hesabı yapar.

    Formül:
        Her ölçümün GPU gücü (gpu_power_w) 3 saniyelik tüketim olarak kabul edilir.
        Total_energy_kWh = Σ(power * 3s)
        CO2 = Total_energy_kWh * CO2_FACTOR
    """

    if not metrics or len(metrics) == 0:
        return 0.0, 0.0

    total_energy_kwh = 0.0

    # Her metric 3 saniyelik aralıkla geliyor
    INTERVAL_SECONDS = 3

    for m in metrics:
        power = m.gpu_power_w or 0
        total_energy_kwh += power_to_kwh(power, INTERVAL_SECONDS)

    emission_kg = calculate_emission(total_energy_kwh, region)

    return total_energy_kwh, emission_kg
