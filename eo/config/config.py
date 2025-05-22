import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, List

# 1. Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR       = os.path.join(BASE_DIR, 'data')
PARQUET_DIR    = os.path.join(DATA_DIR, 'parquet')
RAY_SPILL_DIR  = "./spill/"

# 2. Pipeline flags & chunking
UPDATE_STAC      = True
SUPPRESS_WARNINGS = True
CHUNK_SIZE       = {'time': 24, 'latitude': 720, 'longitude': 1440}

# 3. STAC catalog configuration
# Raw catalog
RAW_CATALOG_ID          = "sentinel-raw-catalog"
RAW_CATALOG_DESCRIPTION = "A STAC catalog for Raw Sentinel-2 Scenes"
RAW_CATALOG_DIR         = os.path.join(DATA_DIR, 'catalog', 'raw')
RAW_CATALOG_JSON        = os.path.join(RAW_CATALOG_DIR, 'catalog.json')

# Derived catalog
DERIVED_CATALOG_ID          = "sentinel-derived"
DERIVED_CATALOG_DESCRIPTION = "Monthly RGB Composites"
DERIVED_CATALOG_DIR         = os.path.join(DATA_DIR, 'catalog', 'derived')
DERIVED_CATALOG_JSON        = os.path.join(DERIVED_CATALOG_DIR, 'catalog.json')

# 4. Environment
ENVIRONMENT = "development"

# 5. Pipeline‐manager defaults (overrideable via CLI)
API_URL         = "https://earth-search.aws.element84.com/v1"
AOI_BBOX        = (-122.6, 37.5, -122.3, 37.9)
DEFAULT_TOI     = "2024-06-01/2024-06-30"

ASSETS          = ["B04", "B03", "B02"]
COMMON_ASSETS   = ["red", "green", "blue"]

EPSG            = 32610
RESOLUTION      = 100
OUT_DIR         = "../output_data"


COLLECTION=["sentinel-2-l2a"]
