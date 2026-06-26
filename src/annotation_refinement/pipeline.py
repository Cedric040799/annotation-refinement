from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import RefinementConfig
from .filters import (
    apply_bbox_aspect_ratio_filter,
    apply_bbox_size_filter,
    apply_confidence_filter,
    apply_duplicate_overlap_filter,
    apply_osm_water_filter,
)
from .osm_water import load_water_polygons
from .raster_metadata import read_pixel_size_from_geotiff

FeatureCollection = dict[str, Any]


def refine_feature_collection(
    feature_collection: FeatureCollection,
    config: RefinementConfig | None = None,
    raster_path: str | Path | None = None,
    osm_water_path: str | Path | None = None,
) -> FeatureCollection:
    """Run refinement steps on a GeoJSON feature collection.

    If raster_path is provided, the pixel size is read from that GeoTIFF and
    size-based filtering is applied in meters.
    """

    config = config or RefinementConfig()
    refined = apply_confidence_filter(feature_collection, config)

    if raster_path is not None:
        pixel_size = read_pixel_size_from_geotiff(raster_path)
        config = replace(
            config,
            pixel_size_x_m=pixel_size.x_m,
            pixel_size_y_m=pixel_size.y_m,
        )
        refined = apply_bbox_size_filter(refined, config)
        refined = apply_bbox_aspect_ratio_filter(refined, config)
        refined = apply_duplicate_overlap_filter(refined, config)

    if osm_water_path is not None:
        water_polygons = load_water_polygons(osm_water_path)
        refined = apply_osm_water_filter(refined, water_polygons, config)

    return refined
