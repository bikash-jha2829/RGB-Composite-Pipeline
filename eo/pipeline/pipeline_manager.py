# pipeline_manager.py
"""
Orchestrates the end-to-end flow using the reusable tasks in two phases:
1) Download raw tiles and build the raw STAC catalog
2) Build monthly RGB composites, COGs, and the derived STAC catalog
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import dask

from config.config import AOI_BBOX, DEFAULT_TOI, OUT_DIR, API_URL, RAW_CATALOG_DIR, COMMON_ASSETS, EPSG, RESOLUTION, \
    DERIVED_CATALOG_DIR, DATA_DIR
from pipeline import geo_tasks
from pipeline.generate_stac_catalog import create_raw_catalog, create_derived_catalog
from ray_dask_init import initialize_ray_and_dask


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sentinel-2 RGB monthly composite pipeline"
    )
    p.add_argument(
        "--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
        default=AOI_BBOX, help="AOI in lon/lat"
    )
    p.add_argument(
        "--toi", default=DEFAULT_TOI,
        help="Time-of-interest (ISO interval)"
    )
    p.add_argument(
        "--out-dir", default=DATA_DIR,
        help="Where to write raw tiles, COGs, and catalogs"
    )
    p.add_argument(
        "--debug", action="store_true",
        help="Verbose Dask/Ray logs"
    )
    return p.parse_args()


def run(args: argparse.Namespace | None = None) -> list[Path]:
    args = args or _parse_args()

    # 1. Initialize Ray + Dask
    client = initialize_ray_and_dask()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        print(f"Dask dashboard 🔗  {client.dashboard_link}")

    # 2. Fetch raw STAC Items
    items = geo_tasks.search_items(
        api_url=API_URL,
        bbox=tuple(args.bbox),
        time_range=args.toi,
        max_cloud_pct=None,      # or pull from config if you add STAC_MAX_CLOUD
        collection=None,         # likewise
    )
    print(f"Matched {len(items)} scenes")

    # ==== PHASE 1: Raw tiles + Raw STAC catalog ====
    raw_catalog_task = create_raw_catalog(
        items=items,
        aoi_bbox=tuple(args.bbox),
        catalog_dir=RAW_CATALOG_DIR,
    )
    (raw_cat_path,) = dask.compute(raw_catalog_task)
    print("\nPhase 1 complete — raw STAC catalog written to:")
    print(" ", raw_cat_path)  # should equal RAW_CATALOG_JSON

    # ==== PHASE 2: Monthly COGs + Derived STAC catalog ====
    # 3. Build lazy xarray stack and select RGB
    stack = geo_tasks.band_stack(
        items=items,
        bbox=tuple(args.bbox),
        epsg=EPSG,
        assets=COMMON_ASSETS,
        resolution=RESOLUTION,
    ).sel(band=COMMON_ASSETS)

    # 4. Compute monthly median RGB composites (lazy)
    monthly_rgb = geo_tasks.monthly_median_rgb(stack)

    # 5. Persist monthly composites as COGs
    cogs_out = Path(args.out_dir)
    cog_task = dask.delayed(geo_tasks.save_monthly_cogs)(
        monthly_rgb=monthly_rgb,
        bbox=tuple(args.bbox),
        out_dir=cogs_out,
    )

    # 6. Build derived STAC catalog
    derived_catalog_task = create_derived_catalog(
        monthly_rgb=monthly_rgb,
        aoi_bbox=tuple(args.bbox),
        epsg=EPSG,
        catalog_dir=DERIVED_CATALOG_DIR,
    )

    # 7. Execute Phase 2
    cog_paths, derived_cat_path = dask.compute(cog_task, derived_catalog_task)
    print("\nPhase 2 complete — monthly COGs and derived STAC catalog:")
    print("Wrote monthly COGs:")
    for p in cog_paths:
        print("  ", p)
    print("Derived STAC catalog:", derived_cat_path)  # should equal DERIVED_CATALOG_JSON

    return cog_paths