# helpers.py
from typing import Tuple
import h3  # pip install h3

def bbox_to_h3(
    bbox: Tuple[float, float, float, float],
    res: int = 6,
) -> str:
    """
    Return the H3 cell ID (hex string) for the centre of the bounding-box.

    Parameters
    ----------
    bbox : (minx, miny, maxx, maxy) in lon/lat
    res  : H3 resolution (0–15). 6 ≈ 1 km² cells.

    Example
    -------
    >>> bbox_to_h3((-122.6, 37.5, -122.3, 37.9))
    '8928308280fffff'
    """
    minx, miny, maxx, maxy = bbox
    # centre latitude and longitude
    lat = (miny + maxy) / 2
    lon = (minx + maxx) / 2
    # Use h3-py’s geo_to_h3 (lat, lon, resolution)
    return h3.geo_to_h3(lat, lon, res)
