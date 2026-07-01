from __future__ import annotations

import argparse
from dataclasses import replace

from annotation_refinement import RefinementConfig, apply_osm_water_filter, load_water_polygons, download_osm_water_polygons
from annotation_refinement.geojson_io import load_geojson

"""
Example usage + output:

PYTHONPATH=src python3 scripts/evaluate_osm_water_filter.py data/detections.geojson --buffers 0.0 5.0 8.0 10.0 15.0

Downloading OSM water polygons for bbox [23.41515, 37.71820, 23.45965, 37.77298]...
Water polygons saved to: data/water-polygons-split-4326.geojson
Total bounding boxes: 3894
Water polygons: 2

 buffer_m   rejected  rejected_%       kept   kept_%
      0.0         34       0.87%       3860   99.13%
      5.0         32       0.82%       3862   99.18%
      8.0         31       0.80%       3863   99.20%
     10.0         30       0.77%       3864   99.23%
     15.0         27       0.69%       3867   99.31%
"""


def _bbox_from_feature_collection(feature_collection: dict) -> tuple[float, float, float, float] | None:
    """Extract a lon/lat bounding box from GeoJSON features."""
    coordinates: list[tuple[float, float]] = []

    for feature in feature_collection.get("features", []):
        geometry = feature.get("geometry", {})
        geometry_type = geometry.get("type")
        if geometry_type != "Polygon":
            continue
        for ring in geometry.get("coordinates", []):
            for lon, lat in ring:
                coordinates.append((float(lon), float(lat)))

    if not coordinates:
        return None

    lons = [lon for lon, _ in coordinates]
    lats = [lat for _, lat in coordinates]
    return (min(lons), min(lats), max(lons), max(lats))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count how many boxes would be rejected as safely inside OSM water polygons.",
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument(
        "water_geojson",
        nargs="?",
        default=None,
        help="Path to OSM water polygons as GeoJSON. If not provided, will automatically download.",
    )
    parser.add_argument(
        "--buffers",
        nargs="+",
        type=float,
        default=[0.0, 5.0, 8.0, 10.0, 15.0],
        help="Boundary safety buffers in meters.",
    )
    parser.add_argument(
        "--water-output",
        default="data/water-polygons-split-4326.geojson",
        help="Where to save downloaded OSM water polygons (default: data/water-polygons-split-4326.geojson)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    feature_collection = load_geojson(args.geojson)
    
    # Determine water polygons path
    if args.water_geojson:
        water_geojson_path = args.water_geojson
    else:
        # Auto-download if not provided
        bbox = _bbox_from_feature_collection(feature_collection)
        water_geojson_path = download_osm_water_polygons(args.water_output, bbox=bbox)
    
    water_polygons = load_water_polygons(water_geojson_path)
    total = len(feature_collection.get("features", []))

    if total == 0:
        print("No features found.")
        return

    print(f"Total bounding boxes: {total}")
    print(f"Water polygons: {len(water_polygons)}")
    print()
    print(f"{'buffer_m':>9} {'rejected':>10} {'rejected_%':>11} {'kept':>10} {'kept_%':>8}")

    for buffer_m in args.buffers:
        config = replace(
            RefinementConfig(),
            osm_water_boundary_buffer_m=buffer_m,
            drop_rejected=False,
        )
        refined = apply_osm_water_filter(feature_collection, water_polygons, config)
        rejected = sum(
            not feature["properties"].get("refinement", {}).get("keep", True)
            for feature in refined.get("features", [])
        )
        kept = total - rejected
        rejected_percent = rejected / total * 100
        kept_percent = kept / total * 100

        print(
            f"{buffer_m:9.1f} {rejected:10d} {rejected_percent:10.2f}% "
            f"{kept:10d} {kept_percent:7.2f}%"
        )


if __name__ == "__main__":
    main()
