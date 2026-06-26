from __future__ import annotations

import argparse
from dataclasses import replace

from annotation_refinement import RefinementConfig, apply_osm_water_filter, load_water_polygons
from annotation_refinement.geojson_io import load_geojson


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count how many boxes would be rejected as safely inside OSM water polygons.",
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument("water_geojson", help="Path to OSM water polygons as GeoJSON.")
    parser.add_argument(
        "--buffers",
        nargs="+",
        type=float,
        default=[0.0, 5.0, 8.0, 10.0, 15.0],
        help="Boundary safety buffers in meters.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    feature_collection = load_geojson(args.geojson)
    water_polygons = load_water_polygons(args.water_geojson)
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
