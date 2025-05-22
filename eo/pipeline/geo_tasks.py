"""
Reusable, single-purpose tasks for the Sentinel-2 monthly RGB pipeline.
All functions are **pure** (no global state, no side effects except where
explicitly documented), so they’re easy to unit-test or plug into other DAG
orchestration tools later.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence, Tuple, List, Any

import numpy as np
import pystac
import xarray as xr
import pystac_client
import stackstac
from dask import delayed
from rasterio.enums import Resampling
import rioxarray  # noqa: F401  – needed for the .rio accessor
from dask.diagnostics import ProgressBar

from config.config import EPSG, RESOLUTION, COLLECTION, DATA_DIR
from utils.bbox_to_h3 import bbox_to_h3
from utils.fsspec_copy import _copy_file

logger = logging.getLogger(__name__)


# 1. Search & fetch STAC metadata
def search_items(
    api_url: str,
    bbox: Tuple[float, float, float, float],
    time_range: str,
    max_cloud_pct: int | float = None,
    collection: str = None,
) -> List[pystac.Item]:
    """
    Query an open-STAC endpoint and return an in-memory ItemCollection.

    Parameters
    ----------
    api_url : str
    bbox : (west, south, east, north)
    time_range : ISO-8601 interval
    max_cloud_pct : keep scenes where eo:cloud_cover < this
    collection : STAC collection ID

    Returns
    -------
    List of pystac.Item
    """
    catalog = pystac_client.Client.open(api_url)
    search_args = {
        "collections": COLLECTION,
        "bbox": bbox,
        "datetime": time_range,
    }
    if max_cloud_pct is not None:
        search_args["query"] = {"eo:cloud_cover": {"lt": max_cloud_pct}}

    search = catalog.search(**{k: v for k, v in search_args.items() if v is not None})
    items = search.item_collection()
    if not items:
        raise ValueError("Search returned no scenes – check your criteria.")
    return items


# 2. Stack assets into a Dask-backed xarray.DataArray
def band_stack(
    items: Sequence[pystac.Item],
    bbox: Tuple[float, float, float, float],
    epsg: int = EPSG,
    assets: Sequence[str] = (),
    resolution: float = RESOLUTION,
    resampling: Resampling = Resampling.bilinear,
) -> xr.DataArray:
    """
    Convert an ItemCollection to a lazily-evaluated xarray stack.

    The result dims are (time, band, y, x).
    """
    stack = stackstac.stack(
        items,
        bounds_latlon=bbox,
        epsg=epsg,
        assets=assets,
        resolution=resolution,
        resampling=resampling,
    )
    # Replace numeric band names with common names when available

    stack = stack.assign_coords(
        band=stack.common_name.fillna(stack.band).rename("band")
    )
    return stack


# 3. Build monthly median composites
def monthly_median_rgb(stack: xr.DataArray) -> xr.DataArray:
    """
    Slice the stack to RGB and compute a *median* mosaic for every month.

    Returns an xr.DataArray with dims (time="monthly", band="rgb", y, x),
    with CRS declared from the config.
    """
    rgb = stack.sel(band=["red", "green", "blue"])
    monthly = rgb.resample(time="MS").median(dim="time")
    # Declare CRS so .rio works later
    return monthly.rio.write_crs(stack.rio.crs or f"EPSG:{EPSG}")


# 4. Persist each monthly composite to disk as Cloud-Optimized GeoTIFF
def save_monthly_cogs(
    monthly_rgb: xr.DataArray,
    bbox: Any,
    out_dir: str | Path,
    compress: str = "deflate",
) -> List[Path]:
    """
    Write each monthly composite to `<out_dir>/monthly_rgb_<h3>_<YYYY-MM>.tif`.

    Returns the list of written file paths.
    """
    out_dir = Path(DATA_DIR) / "cogs"
    out_dir.mkdir(parents=True, exist_ok=True)
    aoi_id = bbox_to_h3(bbox, res=10)

    written: List[Path] = []
    with ProgressBar():
        for ts in monthly_rgb.time.values:
            tstr = np.datetime_as_string(ts, unit="M")
            da = monthly_rgb.sel(time=ts).transpose("band", "y", "x")
            out_path = out_dir / f"monthly_rgb_{aoi_id}_{tstr}.tif"
            da.rio.to_raster(out_path, driver="COG", compress=compress)
            written.append(out_path)

    return written


# 5. Download raw assets (optional)
def download_raw_assets(
    items: List[pystac.Item],
    assets: List[str],
    out_dir: str | Path,
) -> delayed:
    """
    Delayed task to fetch raw files for each item/asset.
    """
    out_dir = str(Path(DATA_DIR) / "derived_cogs")

    @delayed(pure=False)
    def _download_all() -> List[Path]:
        logger.info("Downloading %d scenes, assets %s", len(items), assets)
        written: List[Path] = []
        for item in items:
            for name in assets:
                asset = item.assets.get(name)
                if asset is None:
                    logger.debug("%s missing asset %s", item.id, name)
                    continue

                suffix = Path(asset.href).suffix or ".tif"
                dst = out_dir / f"{item.id}_{name}{suffix}"
                logger.debug("Queue %s → %s", asset.href, dst)
                written.append(_copy_file(asset.href, dst))
        logger.info("Downloaded %d files", len(written))
        return written

    return _download_all()
