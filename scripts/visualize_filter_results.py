from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

try:
    import rasterio
    from rasterio.windows import from_bounds
except ImportError as exc:
    rasterio = None
    from_bounds = None
    rasterio_import_error = exc

from annotation_refinement import (
    RefinementConfig,
    download_osm_water_polygons,
    refine_feature_collection,
)
from annotation_refinement.geojson_io import load_geojson


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize refined detections on a GeoTIFF with keep/reject colors.",
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument("tif", help="Path to the GeoTIFF image file.")
    parser.add_argument(
        "--osm-water",
        dest="osm_water_geojson",
        default=None,
        help="Optional OSM water polygons GeoJSON file.",
    )
    parser.add_argument(
        "--download-osm-water",
        action="store_true",
        help="Download OSM water polygons for the detection bounding box.",
    )
    parser.add_argument(
        "--osm-buffer",
        type=float,
        default=8.0,
        help="Boundary safety buffer for OSM water filtering in meters.",
    )
    parser.add_argument(
        "--crop",
        nargs=4,
        type=float,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="Crop window in coordinate space (min_lon min_lat max_lon max_lat).",
    )
    parser.add_argument(
        "--pad",
        type=float,
        default=0.0,
        help="Padding around the crop window in coordinate units.",
    )
    parser.add_argument(
        "--output",
        default="data/visualizations/filter.png",
        help="Output path for the rendered figure. Default: data/visualizations/filter.png",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the figure interactively after rendering.",
    )
    return parser.parse_args()


def _bbox_from_feature_collection(feature_collection: dict[str, Any]) -> tuple[float, float, float, float] | None:
    coordinates: list[tuple[float, float]] = []
    for feature in feature_collection.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Polygon":
            continue
        for ring in geometry.get("coordinates", []):
            for lon, lat, *_ in ring:
                coordinates.append((float(lon), float(lat)))

    if not coordinates:
        return None

    lons = [lon for lon, _ in coordinates]
    lats = [lat for _, lat in coordinates]
    return (min(lons), min(lats), max(lons), max(lats))


def _apply_pad(bbox: tuple[float, float, float, float], pad: float) -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad)


def _feature_bbox(feature: dict[str, Any]) -> tuple[float, float, float, float] | None:
    geometry = feature.get("geometry", {})
    if geometry.get("type") != "Polygon":
        return None

    coords = geometry.get("coordinates", [])
    if not coords:
        return None

    points = [(float(x), float(y)) for x, y, *_ in coords[0]]
    lons = [lon for lon, _ in points]
    lats = [lat for _, lat in points]
    return (min(lons), min(lats), max(lons), max(lats))


def _bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    a_min_lon, a_min_lat, a_max_lon, a_max_lat = a
    b_min_lon, b_min_lat, b_max_lon, b_max_lat = b
    return not (
        a_max_lon < b_min_lon
        or a_min_lon > b_max_lon
        or a_max_lat < b_min_lat
        or a_min_lat > b_max_lat
    )


def _feature_rejection_reason(feature: dict[str, Any]) -> str:
    refinement = feature.get("properties", {}).get("refinement", {})
    keep = refinement.get("keep", True)
    reasons = refinement.get("reasons", [])

    if keep:
        return "kept"

    if isinstance(reasons, list) and reasons:
        return reasons[0]
    if reasons:
        return str(reasons)
    return "rejected"


def _plot_window(image: np.ndarray, extent: tuple[float, float, float, float], features: list[dict[str, Any]]) -> None:
    fig, ax = plt.subplots(figsize=(12, 10))

    if image.ndim == 3:
        if image.shape[0] >= 3:
            image = np.transpose(image[:3], (1, 2, 0))
        elif image.shape[0] == 2:
            image = np.transpose(np.concatenate([image, image[:1]], axis=0), (1, 2, 0))
        else:
            image = np.stack([image[0]] * 3, axis=-1)
    elif image.ndim == 2:
        image = np.stack([image] * 3, axis=-1)

    image = np.nan_to_num(image, nan=0.0)
    if image.dtype != np.uint8:
        image = image.astype(np.float64)
        image = (image - image.min()) / max(1.0, image.max() - image.min())

    if image.dtype == np.float64:
        image = np.clip(image, 0.0, 1.0)

    ax.imshow(image, extent=extent, origin="upper")

    legend_handles: dict[str, Any] = {}
    reason_colors = {
        "kept": "lime",
        "osm_water_forbidden_area": "red",
        "low_confidence": "orange",
        "missing_score": "purple",
        "duplicate_overlap": "magenta",
        "rejected": "gray",
    }

    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Polygon":
            continue

        coords = geometry.get("coordinates", [])
        if not coords:
            continue
        exterior = coords[0]
        xs = [float(x) for x, y, *_ in exterior]
        ys = [float(y) for x, y, *_ in exterior]

        reason = _feature_rejection_reason(feature)
        color = reason_colors.get(reason, "gray")
        keep = reason == "kept"
        linestyle = "solid" if keep else "dashed"

        patch = ax.plot(xs, ys, color=color, linestyle=linestyle, linewidth=0.8, alpha=0.9)[0]
        legend_handles.setdefault(reason, patch)

    if legend_handles:
        ax.legend(legend_handles.values(), legend_handles.keys(), fontsize=8, loc="upper right")

    ax.set_title("Filtered detections overlay")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.tight_layout()


def _read_raster_window(tif_path: str | Path, bbox: tuple[float, float, float, float]) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    with rasterio.open(tif_path) as dataset:
        window = from_bounds(*bbox, dataset.transform)
        window = window.round_offsets().round_lengths()
        data = dataset.read(window=window)
        window_transform = dataset.window_transform(window)

        left, top = window_transform * (0, 0)
        right, bottom = window_transform * (data.shape[2], data.shape[1])
        extent = (left, right, bottom, top)

    return data, extent


def main() -> None:
    args = parse_args()

    feature_collection = load_geojson(args.geojson)
    osm_water_path = None
    if args.download_osm_water:
        bbox = _bbox_from_feature_collection(feature_collection)
        if bbox is None:
            raise ValueError("Cannot determine bounding box from detections for OSM download.")
        osm_water_path = download_osm_water_polygons("data/water-polygons-split-4326.geojson", bbox=bbox)
    elif args.osm_water_geojson:
        osm_water_path = args.osm_water_geojson

    config = RefinementConfig()
    config = replace(config, drop_rejected=False)
    config = replace(config, osm_water_boundary_buffer_m=args.osm_buffer)

    refined = refine_feature_collection(
        feature_collection,
        config=config,
        raster_path=args.tif,
        osm_water_path=osm_water_path,
    )

    if rasterio is None:
        raise ImportError(
            "rasterio is required to read the GeoTIFF and display the image. "
            "Install it in your environment before running this script."
        ) from rasterio_import_error

    if args.crop:
        crop_bbox = tuple(args.crop)
    else:
        crop_bbox = _bbox_from_feature_collection(feature_collection)
        if crop_bbox is None:
            raise ValueError("Cannot determine crop extent from detections.")
    crop_bbox = _apply_pad(crop_bbox, args.pad)

    image, extent = _read_raster_window(args.tif, crop_bbox)
    plot_features = [
        feature
        for feature in refined.get("features", [])
        if (bbox := _feature_bbox(feature)) is not None and _bbox_intersects(bbox, crop_bbox)
    ]
    _plot_window(image, extent, plot_features)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        print(f"Saved figure to {output_path}")
    if args.show or args.output is None:
        plt.show()


if __name__ == "__main__":
    main()
