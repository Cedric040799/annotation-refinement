from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import RefinementConfig
from .osm_water import Polygon, WaterMatch, match_points_in_water

Feature = dict[str, Any]
FeatureCollection = dict[str, Any]
BBoxDimensions = tuple[float, float, float]
BBox = tuple[float, float, float, float]


def apply_confidence_filter(
    feature_collection: FeatureCollection,
    config: RefinementConfig | None = None,
) -> FeatureCollection:
    """Annotate or remove features with confidence below the configured threshold."""

    config = config or RefinementConfig()
    refined = deepcopy(feature_collection)
    features = refined.get("features", [])
    kept_features: list[Feature] = []

    for feature in features:
        refined_feature = _annotate_confidence(feature, config.min_confidence)
        keep = refined_feature["properties"]["refinement"]["keep"]

        if keep or not config.drop_rejected:
            kept_features.append(refined_feature)

    refined["features"] = kept_features
    return refined


def apply_bbox_size_filter(
    feature_collection: FeatureCollection,
    config: RefinementConfig | None = None,
) -> FeatureCollection:
    """Annotate or remove boxes whose real-world size is implausible for road vehicles."""

    config = config or RefinementConfig()
    _require_pixel_size(config, "BBox size filtering")

    refined = deepcopy(feature_collection)
    features = refined.get("features", [])
    kept_features: list[Feature] = []

    for feature in features:
        refined_feature = _annotate_bbox_size(feature, config)
        keep = refined_feature["properties"]["refinement"]["keep"]

        if keep or not config.drop_rejected:
            kept_features.append(refined_feature)

    refined["features"] = kept_features
    return refined


def apply_bbox_aspect_ratio_filter(
    feature_collection: FeatureCollection,
    config: RefinementConfig | None = None,
) -> FeatureCollection:
    """Annotate or remove boxes whose longer side is too large relative to the shorter side."""

    config = config or RefinementConfig()
    _require_pixel_size(config, "BBox aspect-ratio filtering")

    refined = deepcopy(feature_collection)
    features = refined.get("features", [])
    kept_features: list[Feature] = []

    for feature in features:
        refined_feature = _annotate_bbox_aspect_ratio(feature, config)
        keep = refined_feature["properties"]["refinement"]["keep"]

        if keep or not config.drop_rejected:
            kept_features.append(refined_feature)

    refined["features"] = kept_features
    return refined


def apply_duplicate_overlap_filter(
    feature_collection: FeatureCollection,
    config: RefinementConfig | None = None,
) -> FeatureCollection:
    """Mark lower-confidence boxes that are almost contained in a larger box."""

    config = config or RefinementConfig()
    refined = deepcopy(feature_collection)
    features = refined.get("features", [])
    entries = _collect_overlap_entries(features)
    grid = _build_spatial_grid(entries, config.duplicate_grid_cell_size_px)
    duplicate_matches: dict[int, dict[str, float | int]] = {}

    for entry in entries:
        for candidate_index in _candidate_indices(entry["bbox"], grid, config.duplicate_grid_cell_size_px):
            candidate = entries[candidate_index]
            if entry["index"] >= candidate["index"]:
                continue

            match = _duplicate_match(entry, candidate, config)
            if match is None:
                continue

            rejected_index = int(match["rejected_index"])
            current = duplicate_matches.get(rejected_index)
            if current is None or match["containment"] > current["containment"]:
                duplicate_matches[rejected_index] = match

    kept_features: list[Feature] = []
    for index, feature in enumerate(features):
        refined_feature = feature
        if index in duplicate_matches:
            refined_feature = _annotate_duplicate_overlap(feature, duplicate_matches[index], config)

        keep = refined_feature.setdefault("properties", {}).setdefault("refinement", {}).get("keep", True)
        if keep or not config.drop_rejected:
            kept_features.append(refined_feature)

    refined["features"] = kept_features
    return refined


def apply_osm_water_filter(
    feature_collection: FeatureCollection,
    water_polygons: list[Polygon],
    config: RefinementConfig | None = None,
) -> FeatureCollection:
    """Mark boxes that are safely inside OSM water polygons."""

    config = config or RefinementConfig()
    refined = deepcopy(feature_collection)
    features = refined.get("features", [])
    kept_features: list[Feature] = []

    for feature in features:
        refined_feature = _annotate_osm_water(feature, water_polygons, config)
        keep = refined_feature.setdefault("properties", {}).setdefault("refinement", {}).get("keep", True)

        if keep or not config.drop_rejected:
            kept_features.append(refined_feature)

    refined["features"] = kept_features
    return refined


def _annotate_osm_water(
    feature: Feature,
    water_polygons: list[Polygon],
    config: RefinementConfig,
) -> Feature:
    refined_feature = deepcopy(feature)
    properties = refined_feature.setdefault("properties", {})
    refinement = properties.setdefault("refinement", {})
    reasons = list(refinement.get("reasons", []))
    keep = bool(refinement.get("keep", True))

    if keep is False:
        return refined_feature

    sample_points = _feature_sample_points_lonlat(refined_feature)
    if not sample_points:
        return refined_feature

    match = match_points_in_water(
        sample_points,
        water_polygons,
        config.osm_water_boundary_buffer_m,
    )
    if match is None:
        return refined_feature

    reasons.append("osm_water_forbidden_area")
    refinement["keep"] = False
    refinement["reasons"] = reasons
    refinement["osm_water"] = {
        "matched_polygon_index": match.polygon_index,
        "sample_points_inside": len(sample_points),
        "min_boundary_distance_m": match.min_boundary_distance_m,
        "boundary_buffer_m": config.osm_water_boundary_buffer_m,
    }
    return refined_feature


def _feature_sample_points_lonlat(feature: Feature) -> list[tuple[float, float]] | None:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Polygon":
        return None

    coordinates = geometry.get("coordinates") or []
    if not coordinates:
        return None

    exterior = coordinates[0]
    points = [(float(x), float(y)) for x, y, *_ in exterior]
    if len(points) < 4:
        return None

    if points[0] == points[-1]:
        points = points[:-1]

    min_lon = min(point[0] for point in points)
    max_lon = max(point[0] for point in points)
    min_lat = min(point[1] for point in points)
    max_lat = max(point[1] for point in points)
    center = ((min_lon + max_lon) / 2, (min_lat + max_lat) / 2)
    corners = [
        (min_lon, min_lat),
        (min_lon, max_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
    ]
    return [center, *corners]


def _annotate_confidence(feature: Feature, min_confidence: float) -> Feature:
    refined_feature = deepcopy(feature)
    properties = refined_feature.setdefault("properties", {})
    refinement = properties.setdefault("refinement", {})
    reasons = list(refinement.get("reasons", []))

    score = properties.get("score")
    keep = bool(refinement.get("keep", True))

    if score is None:
        keep = False
        reasons.append("missing_score")
    elif float(score) < min_confidence:
        keep = False
        reasons.append("low_confidence")

    refinement["keep"] = keep
    refinement["reasons"] = reasons
    refinement["min_confidence"] = min_confidence
    return refined_feature


def _annotate_bbox_size(feature: Feature, config: RefinementConfig) -> Feature:
    refined_feature = deepcopy(feature)
    properties = refined_feature.setdefault("properties", {})
    refinement = properties.setdefault("refinement", {})
    reasons = list(refinement.get("reasons", []))
    keep = bool(refinement.get("keep", True))

    dimensions = _get_bbox_dimensions_m(properties.get("bounds_imcoords"), config)
    if dimensions is None:
        keep = False
        reasons.append("missing_bounds_imcoords")
        refinement["keep"] = keep
        refinement["reasons"] = reasons
        return refined_feature

    width_m, height_m, area_m2 = dimensions
    min_side_m = min(width_m, height_m)
    max_side_m = max(width_m, height_m)

    if min_side_m < config.min_bbox_side_m or area_m2 < config.min_bbox_area_m2:
        keep = False
        reasons.append("bbox_too_small")

    if max_side_m > config.max_bbox_side_m or area_m2 > config.max_bbox_area_m2:
        keep = False
        reasons.append("bbox_too_large")

    refinement["keep"] = keep
    refinement["reasons"] = reasons
    refinement["bbox_size_m"] = {
        "width": width_m,
        "height": height_m,
        "area": area_m2,
    }
    refinement["bbox_size_thresholds"] = {
        "min_side": config.min_bbox_side_m,
        "max_side": config.max_bbox_side_m,
        "min_area": config.min_bbox_area_m2,
        "max_area": config.max_bbox_area_m2,
        "pixel_size_x": config.pixel_size_x_m,
        "pixel_size_y": config.pixel_size_y_m,
    }
    return refined_feature


def _annotate_bbox_aspect_ratio(feature: Feature, config: RefinementConfig) -> Feature:
    refined_feature = deepcopy(feature)
    properties = refined_feature.setdefault("properties", {})
    refinement = properties.setdefault("refinement", {})
    reasons = list(refinement.get("reasons", []))
    keep = bool(refinement.get("keep", True))

    dimensions = _get_bbox_dimensions_m(properties.get("bounds_imcoords"), config)
    if dimensions is None:
        keep = False
        reasons.append("missing_bounds_imcoords")
        refinement["keep"] = keep
        refinement["reasons"] = reasons
        return refined_feature

    width_m, height_m, _ = dimensions
    shorter_side_m = min(width_m, height_m)
    longer_side_m = max(width_m, height_m)

    if shorter_side_m == 0:
        aspect_ratio = float("inf")
    else:
        aspect_ratio = longer_side_m / shorter_side_m

    if aspect_ratio > config.max_bbox_aspect_ratio:
        keep = False
        reasons.append("bbox_aspect_ratio_too_extreme")

    refinement["keep"] = keep
    refinement["reasons"] = reasons
    refinement["bbox_aspect_ratio"] = aspect_ratio
    refinement["bbox_aspect_ratio_threshold"] = config.max_bbox_aspect_ratio
    return refined_feature


def _annotate_duplicate_overlap(
    feature: Feature,
    match: dict[str, float | int],
    config: RefinementConfig,
) -> Feature:
    refined_feature = deepcopy(feature)
    properties = refined_feature.setdefault("properties", {})
    refinement = properties.setdefault("refinement", {})
    reasons = list(refinement.get("reasons", []))
    reasons.append("duplicate_overlap_lower_confidence")

    refinement["keep"] = False
    refinement["reasons"] = reasons
    refinement["duplicate_overlap"] = {
        "matched_feature_index": int(match["kept_index"]),
        "containment": float(match["containment"]),
        "iou": float(match["iou"]),
        "score_delta": float(match["score_delta"]),
        "rejected_score": float(match["rejected_score"]),
        "matched_score": float(match["kept_score"]),
        "min_containment": config.min_duplicate_containment,
        "min_score_delta": config.min_duplicate_score_delta,
    }
    return refined_feature


def _collect_overlap_entries(features: list[Feature]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, feature in enumerate(features):
        properties = feature.get("properties", {})
        refinement = properties.get("refinement", {})
        if refinement.get("keep") is False:
            continue

        bbox = _parse_bounds_imcoords(properties.get("bounds_imcoords"))
        score = properties.get("score")
        if bbox is None or score is None:
            continue

        area = _bbox_area(bbox)
        if area <= 0:
            continue

        entries.append(
            {
                "entry_index": len(entries),
                "index": index,
                "bbox": bbox,
                "area": area,
                "score": float(score),
            }
        )
    return entries


def _build_spatial_grid(
    entries: list[dict[str, Any]],
    cell_size: float,
) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = {}
    for entry in entries:
        for cell in _bbox_cells(entry["bbox"], cell_size):
            grid.setdefault(cell, []).append(entry["entry_index"])
    return grid


def _candidate_indices(
    bbox: BBox,
    grid: dict[tuple[int, int], list[int]],
    cell_size: float,
) -> set[int]:
    candidates: set[int] = set()
    for cell in _bbox_cells(bbox, cell_size):
        candidates.update(grid.get(cell, []))
    return candidates


def _bbox_cells(bbox: BBox, cell_size: float) -> list[tuple[int, int]]:
    min_x, min_y, max_x, max_y = bbox
    start_x = int(min_x // cell_size)
    end_x = int(max_x // cell_size)
    start_y = int(min_y // cell_size)
    end_y = int(max_y // cell_size)
    return [
        (cell_x, cell_y)
        for cell_x in range(start_x, end_x + 1)
        for cell_y in range(start_y, end_y + 1)
    ]


def _duplicate_match(
    first: dict[str, Any],
    second: dict[str, Any],
    config: RefinementConfig,
) -> dict[str, float | int] | None:
    smaller, larger = (first, second) if first["area"] <= second["area"] else (second, first)
    intersection = _intersection_area(smaller["bbox"], larger["bbox"])
    if intersection <= 0:
        return None

    containment = intersection / smaller["area"]
    if containment < config.min_duplicate_containment:
        return None

    score_delta = larger["score"] - smaller["score"]
    if score_delta < config.min_duplicate_score_delta:
        return None

    union = smaller["area"] + larger["area"] - intersection
    iou = intersection / union if union > 0 else 0.0
    return {
        "rejected_index": int(smaller["index"]),
        "kept_index": int(larger["index"]),
        "containment": containment,
        "iou": iou,
        "score_delta": score_delta,
        "rejected_score": float(smaller["score"]),
        "kept_score": float(larger["score"]),
    }


def _bbox_area(bbox: BBox) -> float:
    min_x, min_y, max_x, max_y = bbox
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _intersection_area(first: BBox, second: BBox) -> float:
    min_x = max(first[0], second[0])
    min_y = max(first[1], second[1])
    max_x = min(first[2], second[2])
    max_y = min(first[3], second[3])
    return max(0.0, max_x - min_x) * max(0.0, max_y - min_y)


def _get_bbox_dimensions_m(value: Any, config: RefinementConfig) -> BBoxDimensions | None:
    bounds = _parse_bounds_imcoords(value)
    if bounds is None:
        return None

    min_x, min_y, max_x, max_y = bounds
    width_px = abs(max_x - min_x)
    height_px = abs(max_y - min_y)
    width_m = width_px * config.pixel_size_x_m
    height_m = height_px * config.pixel_size_y_m
    area_m2 = width_m * height_m
    return width_m, height_m, area_m2


def _require_pixel_size(config: RefinementConfig, filter_name: str) -> None:
    if config.pixel_size_x_m is None or config.pixel_size_y_m is None:
        raise ValueError(
            f"{filter_name} requires pixel_size_x_m and pixel_size_y_m. "
            "Read them from the matching raster with read_pixel_size_from_geotiff()."
        )


def _parse_bounds_imcoords(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None

    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    else:
        parts = list(value)

    if len(parts) != 4:
        return None

    try:
        min_x, min_y, max_x, max_y = (float(part) for part in parts)
    except (TypeError, ValueError):
        return None

    return min(min_x, max_x), min(min_y, max_y), max(min_x, max_x), max(min_y, max_y)
