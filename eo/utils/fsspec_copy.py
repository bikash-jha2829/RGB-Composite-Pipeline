import logging
from pathlib import Path

from fsspec import url_to_fs

logger = logging.getLogger(__name__)


def _copy_file(
    src_url: str,
    dst: Path,
    *,
    block_size: str = "16MiB",
    overwrite: bool = False,
) -> Path:
    """
    Stream a remote asset straight to *dst* with no raster decoding/re-encoding.
    """
    if dst.exists() and not overwrite:
        logger.debug("Skipping existing file %s", dst)
        return dst

    logger.info("Starting download: %s → %s", src_url, dst)
    fs, path = url_to_fs(src_url)
    dst.parent.mkdir(parents=True, exist_ok=True)

    tmp = dst.with_suffix(dst.suffix + ".part")
    with fs.open(path, "rb", block_size=block_size) as src, \
         open(tmp, "wb") as out:
        out.write(src.read())
    tmp.rename(dst)
    logger.info("Finished download: %s", dst)
    return dst