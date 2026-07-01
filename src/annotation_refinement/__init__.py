"""Utilities for postprocessing model-generated annotations."""

from .config import RefinementConfig
from .filters import (
    apply_bbox_aspect_ratio_filter,
    apply_bbox_size_filter,
    apply_confidence_filter,
    apply_duplicate_overlap_filter,
    apply_osm_water_filter,
)
from .pipeline import refine_feature_collection
from .osm_water import WaterMatch, load_water_polygons, download_osm_water_polygons
from .raster_metadata import PixelSize, read_pixel_size_from_geotiff

__all__ = [
    "RefinementConfig",
    "apply_bbox_aspect_ratio_filter",
    "apply_bbox_size_filter",
    "apply_confidence_filter",
    "apply_duplicate_overlap_filter",
    "apply_osm_water_filter",
    "refine_feature_collection",
    "PixelSize",
    "read_pixel_size_from_geotiff",
    "WaterMatch",
    "load_water_polygons",
    "download_osm_water_polygons",
]
