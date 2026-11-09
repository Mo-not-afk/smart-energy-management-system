"""Validated meter ingestion and reproducible energy analytics."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import pandas as pd

REQUIRED = {"timestamp", "voltage_v", "current_a", "power_w", "power_factor"}


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="raise")
    if data["timestamp"].isna().any():
        raise ValueError("timestamps cannot be missing")
    for col in REQUIRED - {"timestamp"}:
        data[col] = pd.to_numeric(data[col], errors="raise")
    if data.empty or data[list(REQUIRED - {"timestamp"})].isna().any().any():
        raise ValueError("meter data must be non-empty and finite")
    if not data[list(REQUIRED - {"timestamp"})].map(lambda x: math.isfinite(float(x))).all().all():
        raise ValueError("meter values must be finite")
    if (data["voltage_v"] <= 0).any() or (data["current_a"] < 0).any() or (data["power_w"] < 0).any():
        raise ValueError("voltage must be positive; current and power must be non-negative")
    if not data["power_factor"].between(0, 1).all():
        raise ValueError("power_factor must be between 0 and 1")
    data = data.sort_values("timestamp").reset_index(drop=True)
    if data["timestamp"].duplicated().any():
        raise ValueError("timestamps must be unique")
    return data


def load_csv(path: str | Path) -> pd.DataFrame:
    try:
        return validate_frame(pd.read_csv(path))
    except (OSError, pd.errors.ParserError) as exc:
        raise ValueError(f"cannot read meter CSV: {exc}") from exc


def add_energy(frame: pd.DataFrame) -> pd.DataFrame:
    """Add interval kWh by trapezoidal power integration; final row is zero."""
    data = validate_frame(frame)
    seconds = data.timestamp.diff().dt.total_seconds().fillna(0)
    previous = data.power_w.shift(1).fillna(data.power_w)
    data["energy_kwh"] = ((previous + data.power_w) / 2) * seconds / 3_600_000
    return data


@dataclass(frozen=True)
class Tariff:
    eur_per_kwh: float
    base_fee_eur: float = 0.0

    def cost(self, kwh: float) -> float:
        if not all(math.isfinite(float(x)) for x in (kwh, self.eur_per_kwh, self.base_fee_eur)) or kwh < 0 or self.eur_per_kwh < 0 or self.base_fee_eur < 0:
            raise ValueError("energy, tariff, and base fee must be non-negative")
        return kwh * self.eur_per_kwh + self.base_fee_eur


def analyze(frame: pd.DataFrame, tariff: Tariff, z_threshold: float = 3.0) -> dict:
    if z_threshold <= 0:
        raise ValueError("z_threshold must be positive")
    data = add_energy(frame)
    values = data.power_w
    sigma = float(values.std(ddof=0))
    z = (values - float(values.mean())) / sigma if sigma else values * 0
    energy = float(data.energy_kwh.sum())
    data["anomaly"] = z.abs() >= z_threshold
    hourly = data.set_index("timestamp").resample("1h").energy_kwh.sum().dropna()
    indexed = data.set_index("timestamp")
    periods = {rule: {k.isoformat(): float(v) for k, v in indexed.energy_kwh.resample(rule).sum().items()}
               for rule in ("D", "W", "MS")}
    return {"samples": int(len(data)), "energy_kwh": energy, "cost_eur": tariff.cost(energy),
            "mean_power_w": float(values.mean()), "peak_power_w": float(values.max()),
            "anomaly_count": int(data.anomaly.sum()), "hourly_kwh": {k.isoformat(): float(v) for k, v in hourly.items()},
            "daily_kwh": periods["D"], "weekly_kwh": periods["W"], "monthly_kwh": periods["MS"]}


def synthetic_readings(count: int = 96, seed: int = 7) -> pd.DataFrame:
    if count < 2:
        raise ValueError("count must be at least two")
    rng = __import__("numpy").random.default_rng(seed)
    import numpy as np
    ts = pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC")
    base = 300 + 180 * (1 + np.sin(np.arange(count) * 2 * np.pi / 96)) / 2
    power = np.maximum(10, base + rng.normal(0, 18, count))
    if count > 40:
        power[40] *= 2.2
    return pd.DataFrame({"timestamp": ts, "voltage_v": 230 + rng.normal(0, 1, count),
        "current_a": power / 230, "power_w": power, "power_factor": np.clip(.92 + rng.normal(0, .015, count), 0, 1), "data_origin": "simulated"})
