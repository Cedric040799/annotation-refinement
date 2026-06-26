from dataclasses import dataclass


@dataclass(frozen=True)
class RefinementConfig:
    """Configuration for annotation refinement filters."""

    # Confidence filter:
    min_confidence: float = 0.33

    # BBox size and aspect-ratio filters:
    # (pixel sizes are usually filled from the matching GeoTIFF metadata but can be set manually if needed)
    pixel_size_x_m: float | None = None
    pixel_size_y_m: float | None = None
    min_bbox_side_m: float = 1.0
    max_bbox_side_m: float = 30.0
    min_bbox_area_m2: float = 2.0
    max_bbox_area_m2: float = 500.0
    max_bbox_aspect_ratio: float = 12.0

    # Duplicate-overlap filter:
    min_duplicate_containment: float = 0.99
    min_duplicate_score_delta: float = 0.10
    duplicate_grid_cell_size_px: float = 256.0

    # OSM water filter:
    osm_water_boundary_buffer_m: float = 8.0

    # Output behavior for all filters:
    drop_rejected: bool = False


