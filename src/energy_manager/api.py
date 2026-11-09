"""FastAPI interface with SQLite persistence for validated meter samples."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from sqlalchemy import create_engine, text
import pandas as pd
from .core import Tariff, analyze, validate_frame

app = FastAPI(title="Smart Energy Management API", version="0.1.0", description="Synthetic or imported meter analytics; no hardware connection.")
engine = create_engine("sqlite:///energy.db", connect_args={"check_same_thread": False})
with engine.begin() as connection:
    connection.execute(text("CREATE TABLE IF NOT EXISTS readings (timestamp TEXT PRIMARY KEY, voltage_v REAL, current_a REAL, power_w REAL, power_factor REAL, data_origin TEXT NOT NULL)"))

@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite"}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")

@app.post("/readings")
def import_readings(rows: list[dict]):
    try:
        frame = validate_frame(pd.DataFrame(rows))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    records = frame.assign(data_origin="imported").to_dict("records")
    with engine.begin() as connection:
        connection.execute(text("INSERT OR REPLACE INTO readings VALUES (:timestamp,:voltage_v,:current_a,:power_w,:power_factor,:data_origin)"),
                           [{**row, "timestamp": row["timestamp"].isoformat()} for row in records])
    return {"inserted": len(records), "origin": "imported"}

@app.get("/analytics")
def analytics(tariff_eur_per_kwh: float = 0.30):
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT timestamp,voltage_v,current_a,power_w,power_factor FROM readings ORDER BY timestamp")).mappings().all()
    if not rows:
        return {"samples": 0, "energy_kwh": 0.0, "cost_eur": 0.0}
    try:
        return analyze(pd.DataFrame(rows), Tariff(tariff_eur_per_kwh))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
