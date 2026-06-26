from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PixelSize:
    x_m: float
    y_m: float
    source_crs: str | None = None


_TIFF_TYPE_SIZES = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 1,
    7: 1,
    8: 2,
    9: 4,
    10: 8,
    11: 4,
    12: 8,
    16: 8,
    17: 8,
    18: 8,
}


def read_pixel_size_from_geotiff(path: str | Path) -> PixelSize:
    """Read approximate meter-per-pixel size from a GeoTIFF.

    Projected rasters are assumed to store ModelPixelScale in meters. For
    EPSG:4326 rasters, degree pixels are converted to meters at the raster's
    tiepoint latitude.
    """

    tags = _read_first_ifd_tags(path)
    pixel_scale = tags.get(33550)
    if not pixel_scale or len(pixel_scale) < 2:
        raise ValueError(f"No ModelPixelScaleTag found in {path}")

    scale_x = abs(float(pixel_scale[0]))
    scale_y = abs(float(pixel_scale[1]))
    epsg = _read_projected_or_geographic_epsg(tags.get(34735))

    if epsg == 4326:
        latitude = _read_tiepoint_latitude(tags.get(33922))
        if latitude is None:
            raise ValueError("EPSG:4326 raster has no tiepoint latitude for meter conversion")

        return PixelSize(
            x_m=scale_x * _meters_per_degree_lon(latitude),
            y_m=scale_y * _meters_per_degree_lat(latitude),
            source_crs="EPSG:4326",
        )

    return PixelSize(x_m=scale_x, y_m=scale_y, source_crs=f"EPSG:{epsg}" if epsg else None)


def _read_first_ifd_tags(path: str | Path) -> dict[int, Any]:
    with Path(path).open("rb") as file:
        header = file.read(16)
        if header[:2] == b"II":
            endian = "<"
        elif header[:2] == b"MM":
            endian = ">"
        else:
            raise ValueError(f"Not a TIFF file: {path}")

        magic = struct.unpack(endian + "H", header[2:4])[0]
        if magic == 43:
            first_ifd_offset = struct.unpack(endian + "Q", header[8:16])[0]
            return _read_bigtiff_ifd(file, endian, first_ifd_offset)
        if magic == 42:
            first_ifd_offset = struct.unpack(endian + "I", header[4:8])[0]
            return _read_classic_tiff_ifd(file, endian, first_ifd_offset)

        raise ValueError(f"Unsupported TIFF magic number {magic} in {path}")


def _read_bigtiff_ifd(file: Any, endian: str, offset: int) -> dict[int, Any]:
    file.seek(offset)
    entry_count = struct.unpack(endian + "Q", file.read(8))[0]
    tags = {}

    for _ in range(entry_count):
        entry = file.read(20)
        tag, value_type = struct.unpack(endian + "HH", entry[:4])
        count = struct.unpack(endian + "Q", entry[4:12])[0]
        value_or_offset = entry[12:20]
        tags[tag] = _decode_tiff_value(file, endian, value_type, count, value_or_offset, 8)

    return tags


def _read_classic_tiff_ifd(file: Any, endian: str, offset: int) -> dict[int, Any]:
    file.seek(offset)
    entry_count = struct.unpack(endian + "H", file.read(2))[0]
    tags = {}

    for _ in range(entry_count):
        entry = file.read(12)
        tag, value_type = struct.unpack(endian + "HH", entry[:4])
        count = struct.unpack(endian + "I", entry[4:8])[0]
        value_or_offset = entry[8:12]
        tags[tag] = _decode_tiff_value(file, endian, value_type, count, value_or_offset, 4)

    return tags


def _decode_tiff_value(
    file: Any,
    endian: str,
    value_type: int,
    count: int,
    value_or_offset: bytes,
    offset_size: int,
) -> Any:
    type_size = _TIFF_TYPE_SIZES.get(value_type)
    if type_size is None:
        return None

    byte_count = type_size * count
    if byte_count <= len(value_or_offset):
        data = value_or_offset[:byte_count]
    else:
        offset_format = "Q" if offset_size == 8 else "I"
        value_offset = struct.unpack(endian + offset_format, value_or_offset[:offset_size])[0]
        current = file.tell()
        file.seek(value_offset)
        data = file.read(byte_count)
        file.seek(current)

    if value_type == 3:
        return list(struct.unpack(endian + "H" * count, data))
    if value_type == 4:
        return list(struct.unpack(endian + "I" * count, data))
    if value_type == 12:
        return list(struct.unpack(endian + "d" * count, data))
    if value_type == 16:
        return list(struct.unpack(endian + "Q" * count, data))
    if value_type == 2:
        return data.split(b"\x00")[0].decode("ascii", errors="replace")

    return data


def _read_projected_or_geographic_epsg(geo_key_directory: Any) -> int | None:
    if not geo_key_directory or len(geo_key_directory) < 4:
        return None

    key_count = int(geo_key_directory[3])
    entries = geo_key_directory[4 : 4 + key_count * 4]

    for index in range(0, len(entries), 4):
        key_id, tag_location, count, value_offset = entries[index : index + 4]
        if tag_location == 0 and count == 1 and key_id in {2048, 3072}:
            return int(value_offset)

    return None


def _read_tiepoint_latitude(model_tiepoint: Any) -> float | None:
    if model_tiepoint and len(model_tiepoint) >= 5:
        return float(model_tiepoint[4])
    return None


def _meters_per_degree_lat(latitude: float) -> float:
    radians = math.radians(latitude)
    return (
        111132.92
        - 559.82 * math.cos(2 * radians)
        + 1.175 * math.cos(4 * radians)
        - 0.0023 * math.cos(6 * radians)
    )


def _meters_per_degree_lon(latitude: float) -> float:
    radians = math.radians(latitude)
    return (
        111412.84 * math.cos(radians)
        - 93.5 * math.cos(3 * radians)
        + 0.118 * math.cos(5 * radians)
    )
