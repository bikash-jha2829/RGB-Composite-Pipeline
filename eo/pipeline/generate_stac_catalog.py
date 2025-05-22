
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence, Tuple

import numpy as np
import pystac
from dask import delayed
from shapely.geometry import box

from config.config import DERIVED_CATALOG_JSON, RAW_CATALOG_JSON, DERIVED_CATALOG_DESCRIPTION, DERIVED_CATALOG_ID, \
    DERIVED_CATALOG_DIR, RAW_CATALOG_DESCRIPTION, RAW_CATALOG_ID, RAW_CATALOG_DIR, DATA_DIR


def create_raw_catalog(
    items: Sequence[pystac.Item],
    aoi_bbox: Tuple[float, float, float, float],
    catalog_dir: str | Path = RAW_CATALOG_DIR,
    catalog_id: str = RAW_CATALOG_ID,
    title: str = RAW_CATALOG_DESCRIPTION,
) -> delayed:
    """
    Build & write a STAC Catalog grouped by acquisition date.

    Writes:
      <catalog_dir>/catalog.json
      <catalog_dir>/<YYYY-MM-DD>/collection.json + item.json
    Returns the path to the catalog.json (uses RAW_CATALOG_JSON).
    """
    catalog_dir = Path(catalog_dir)
    items_by_date: dict[str, list[pystac.Item]] = defaultdict(list)
    for item in items:
        date_str = item.datetime.strftime("%Y-%m-%d")
        items_by_date[date_str].append(item)

    geom = box(*aoi_bbox).__geo_interface__

    @delayed(pure=False)
    def _write() -> str:
        # root catalog
        root = pystac.Catalog(
            id=catalog_id,
            title=title,
            description=title,
            href=str(catalog_dir),
        )

        # one collection per date
        for date_str, day_items in sorted(items_by_date.items()):
            day_start = datetime.fromisoformat(date_str)
            day_end = day_start + timedelta(days=1)

            coll = pystac.Collection(
                id=f"{catalog_id}-{date_str}",
                title=f"Scenes for {date_str}",
                description=f"Sentinel-2 L2A scenes on {date_str}",
                extent=pystac.Extent(
                    spatial=pystac.SpatialExtent([list(aoi_bbox)]),
                    temporal=pystac.TemporalExtent([[day_start, day_end]]),
                ),
                license="proprietary",
                href=str(catalog_dir / date_str),
            )

            for it in day_items:
                coll.add_item(it)

            root.add_child(coll)

        # write out
        root.normalize_hrefs(str(catalog_dir))
        root.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
        return RAW_CATALOG_JSON

    return _write()


def create_derived_catalog(
    monthly_rgb,  # xr.DataArray
    aoi_bbox: Tuple[float, float, float, float],
    epsg: int,
    catalog_dir: str | Path = DERIVED_CATALOG_DIR,
    catalog_id: str = DERIVED_CATALOG_ID,
    title: str = DERIVED_CATALOG_DESCRIPTION,
) -> delayed:
    """
    Build & write a self-contained STAC Catalog of monthly COGs.

    Expects COGs in ./data/derived_cogs/monthly_composite_<YYYY-MM>.tif
    Returns the path to the catalog.json (uses DERIVED_CATALOG_JSON).
    """
    catalog_dir = Path(catalog_dir)
    geom = box(*aoi_bbox).__geo_interface__

    @delayed(pure=False)
    def _write() -> str:
        catalog = pystac.Catalog(
            id=catalog_id,
            title=title,
            description=title,
            href=str(catalog_dir),
        )

        for ts in monthly_rgb.time.values:
            month_str = np.datetime_as_string(ts, unit="M")
            cog_filename = f"monthly_composite_{month_str}.tif"
            cog_href = str(Path(DATA_DIR) / "cogs" / cog_filename)

            item = pystac.Item(
                id=f"{catalog_id}-{month_str}",
                geometry=geom,
                bbox=list(aoi_bbox),
                datetime=np.datetime64(ts).astype("datetime64[ms]").tolist(),
                properties={},
            )
            item.add_asset(
                "visual",
                pystac.Asset(
                    href=cog_href,
                    media_type=pystac.MediaType.COG,
                    roles=["data", "visual"],
                    title=f"RGB composite {month_str}",
                ),
            )
            catalog.add_item(item)

        catalog.normalize_hrefs(str(catalog_dir))
        catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
        return DERIVED_CATALOG_JSON

    return _write()
