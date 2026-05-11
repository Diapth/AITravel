from __future__ import annotations

from fastapi import FastAPI

from app.runtime_checks import check_runtime


app = FastAPI(title="ChinaTravel Planner", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return check_runtime()
