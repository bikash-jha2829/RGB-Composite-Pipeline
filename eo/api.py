"""
FastAPI ⇆ Prefect 3 — on-demand Sentinel / Landsat processing
POST /run     → queue a flow-run (one Dask cluster, all AOIs)
GET  /status  → fetch run state
"""
from __future__ import annotations

import datetime as dt
import os, re, uuid
from functools import lru_cache
from typing import List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from shapely.geometry import box
from shapely.errors import TopologicalError
from shapely.validation import explain_validity
from prefect import get_client
from prefect.exceptions import ObjectNotFound

from config.settings import PREFECT_API_URL

# Prefect settings 
os.environ.setdefault("PREFECT_API_URL", PREFECT_API_URL)
DEPLOYMENT = "eo_monthly_mosaic/eo_monthly_mosaic"   # ← copy from `prefect deployment ls`

app = FastAPI(title="EO on-demand")

# Band catalogue (STAC) ─────
_STAC_COLLECTIONS = {
    "sentinel-2-l2a": "https://earth-search.aws.element84.com/v1",
    "landsat-c2l2":   "https://landsatlook.usgs.gov/stac-server",
}

@lru_cache
def _load_band_names() -> set[str]:
    names: set[str] = set()
    with httpx.Client(timeout=8.0) as client:
        for cid, root in _STAC_COLLECTIONS.items():
            try:
                data  = client.get(f"{root}/collections/{cid}").json()
                bands = data.get("summaries", {}).get("eo:bands") or data.get("item_assets", {})
                for b in bands:
                    if isinstance(b, dict):
                        names.update({b.get("name","").lower(), b.get("common_name","").lower()})
                    elif isinstance(b, str):
                        names.add(b.lower())
            except Exception as exc:
                print(f"[band-catalog] warn: {cid} fetch failed: {exc}")
    if not names:                        # minimal fallback
        names.update({"blue","green","red","nir","swir1","swir2","b02","b03"})
    return {n for n in names if n}

BAND_CATALOG = _load_band_names()

# ISO-interval helper
class IsoInterval(str):
    _PAT = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$")
    @classmethod
    def __get_pydantic_core_schema__(cls, _src, handler):
        sch = handler(str); sch["after"] = cls._validate; return sch
    @classmethod
    def _validate(cls, v):
        if not cls._PAT.match(v):
            raise ValueError("interval must be 'YYYY-MM-DD/YYYY-MM-DD'")
        s, e = map(dt.date.fromisoformat, v.split("/"))
        if e < s:
            raise ValueError("interval end precedes start")
        return cls(v)

# Request model
class RunRequest(BaseModel):
    bboxes: List[Tuple[float, float, float, float]] = Field(
        ..., min_length=1,
        description="List of [minx, miny, maxx, maxy] lon/lat boxes",
        examples=[[[-122.6, 37.5, -122.3, 37.9]]],
    )
    toi: IsoInterval = Field(..., example="2024-06-01/2024-06-30")
    bands: List[str] = Field(
        ..., min_length=1,
        description="Band names or IDs recognised in Sentinel-2 / Landsat STAC",
        examples=[["red","nir"]],
    )
    out_dir: Optional[str] = None

    # validate every bbox in the list
    @field_validator("bboxes")
    @classmethod
    def _validate_bboxes(cls, v):
        for (minx, miny, maxx, maxy) in v:
            if maxx < minx:
                raise ValueError("maxx must be ≥ minx")
            if maxy < miny:
                raise ValueError("maxy must be ≥ miny")
            if not (-180 <= minx <= 180 and -180 <= maxx <= 180):
                raise ValueError("longitudes must be in [-180, 180]")
            if not (-90  <= miny <= 90  and -90  <= maxy <= 90):
                raise ValueError("latitudes must be in [-90, 90]")
            try:
                geom = box(minx, miny, maxx, maxy)
            except (ValueError, TopologicalError) as exc:
                raise ValueError(f"Invalid bbox – {exc}") from exc
            if not geom.is_valid:
                raise ValueError(f"Invalid bbox geometry – {explain_validity(geom)}")
        return v

    # band validation
    @field_validator("bands")
    @classmethod
    def _validate_bands(cls, v):
        bad = [b for b in v if b.lower() not in BAND_CATALOG]
        if bad:
            raise ValueError(f"unknown band(s): {', '.join(bad)}")
        return v

# routes 
@app.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_flow(req: RunRequest):
    async with get_client() as client:
        try:
            dep = await client.read_deployment_by_name(DEPLOYMENT)
        except ObjectNotFound:
            raise HTTPException(404, f"Deployment '{DEPLOYMENT}' not found")
        run = await client.create_flow_run_from_deployment(
            dep.id,
            parameters=req.model_dump(exclude_none=True),
            name=f"api-{uuid.uuid4().hex[:6]}",
        )
    return {"flow_run_id": str(run.id), "state": run.state.type.value}

@app.get("/status/{flow_run_id}")
async def status(flow_run_id: str):
    async with get_client() as client:
        try:
            run = await client.read_flow_run(flow_run_id)
        except ObjectNotFound:
            raise HTTPException(404, f"Run '{flow_run_id}' not found")
    return {"state": run.state.type.value, "updated": run.updated}
