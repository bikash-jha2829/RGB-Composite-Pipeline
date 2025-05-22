# sentinel2_parallel.py  (deployment via .serve())
from pathlib import Path
from typing import List, Tuple

import dask
from prefect import flow, task
from prefect.logging import get_run_logger
from prefect_dask.task_runners import DaskTaskRunner

from config.config import DATA_DIR, RESOLUTION, EPSG, API_URL, DERIVED_CATALOG_DIR, RAW_CATALOG_DIR
from pipeline import geo_tasks
from pipeline.generate_stac_catalog import create_derived_catalog, create_raw_catalog


@task(retries=2, log_prints=True)
def stac_search(api_url, bbox, toi):
    logger = get_run_logger()
    logger.info(f"STAC search {bbox} {toi}")
    return geo_tasks.search_items(api_url, bbox, toi)


@task
def build_raw_catalog(items, bbox):
    """
    Submits the create_raw_catalog delayed task and computes it.
    Returns the path to catalog.json.
    """
    task = create_raw_catalog(
        items=items,
        aoi_bbox=bbox,
        catalog_dir=RAW_CATALOG_DIR,
    )
    # run on the Dask cluster
    (path,) = dask.compute(task)
    return path


@task(retries=2)
def band_stack(items, bbox, bands):
    return geo_tasks.band_stack(items, bbox=bbox, epsg=EPSG,
                                assets=bands, resolution=RESOLUTION)


@task
def composite(xarr):
    return geo_tasks.monthly_median_rgb(xarr)


@task
def build_derived_catalog(monthly_rgb, bbox):
    """
    Submits the create_derived_catalog delayed task and computes it.
    Returns the path to catalog.json.
    """
    task = create_derived_catalog(
        monthly_rgb=monthly_rgb,
        aoi_bbox=bbox,
        epsg=EPSG,
        catalog_dir=DERIVED_CATALOG_DIR,
    )
    (path,) = dask.compute(task)
    return path


@task(log_prints=True)
def write_cogs(rgb, bbox) -> List[Path]:
    logger = get_run_logger()
    files = geo_tasks.save_monthly_cogs(rgb, bbox=bbox, out_dir=DATA_DIR)
    logger.info(f"wrote {len(files)} → {DATA_DIR}")
    return files


# flow
@flow(name="eo_monthly_mosaic",
      task_runner=DaskTaskRunner(cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}))
def sentinel2_parallel(
        bboxes: List[Tuple[float, float, float, float]],
        toi: str,
        bands: List[str],
):
    futures = []
    for bbox in bboxes:
        items = stac_search.submit(API_URL, bbox, toi)
        raw_cat = build_raw_catalog.submit(items, bbox)
        stk = band_stack.submit(items, bbox, bands)
        rgb = composite.submit(stk)
        cogs = write_cogs.submit(rgb, bbox)
        derived_cat = build_derived_catalog.submit(rgb, bbox)

        futures.append({"raw_catalog": raw_cat,
                        "cogs": cogs,
                        "derived_catalog": derived_cat})
    return [
        {
            "raw_catalog": r["raw_catalog"].result(),
            "cogs": r["cogs"].result(),
            "derived_catalog": r["derived_catalog"].result(),
        }
        for r in futures
    ]


# quick local deployment
if __name__ == "__main__":
    # register deployment + start polling worker in ONE process
    sentinel2_parallel.serve(name="eo_monthly_mosaic")
