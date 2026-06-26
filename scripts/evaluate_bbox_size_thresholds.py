from __future__ import annotations

import argparse
from dataclasses import replace

from annotation_refinement import RefinementConfig, apply_bbox_size_filter
from annotation_refinement.geojson_io import load_geojson
from annotation_refinement.raster_metadata import read_pixel_size_from_geotiff

"""
Example usage + output:

PYTHONPATH=src python3 scripts/evaluate_bbox_size_thresholds.py data/detections.geojson   --raster data/Egina_PN.tif   --configs 1,30,2,500

Note: for configs, the order is min_side,max_side,min_area,max_area in meters / square meters.

Total bounding boxes: 3894
Pixel size: x=0.2379 m/px, y=0.2997 m/px
Pixel size source: EPSG:4326

 min_side  max_side  min_area  max_area   rejected  rejected_%       kept   kept_%
     1.00     30.00      2.00    500.00         55       1.41%       3839   98.59%
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Count how many bounding boxes would be rejected by real-world size thresholds. "
            "Each config is min_side,max_side,min_area,max_area in meters / square meters."
        ),
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument(
        "--raster",
        help="Matching GeoTIFF. Pixel size is read from this file.",
    )
    parser.add_argument(
        "--gsd",
        type=float,
        help="Manual ground sampling distance in meters per pixel. Overrides --raster.",
    )
    parser.add_argument(
        "--pixel-size-x",
        type=float,
        help="Manual pixel size in meters in x direction. Overrides --raster.",
    )
    parser.add_argument(
        "--pixel-size-y",
        type=float,
        help="Manual pixel size in meters in y direction. Overrides --raster.",
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        default=["0.5,30,1,500", "1,25,2,300", "1.5,20,4,200"],
        help=(
            "Threshold configs as min_side,max_side,min_area,max_area. "
            "Example: --configs 0.5,30,1,500 1,25,2,300"
        ),
    )
    return parser.parse_args()


def parse_config(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"Expected min_side,max_side,min_area,max_area, got: {value}"
        )
    return tuple(parts)  # type: ignore[return-value]


def resolve_pixel_size(args: argparse.Namespace) -> tuple[float, float, str | None]:
    if args.gsd is not None:
        return args.gsd, args.gsd, "manual --gsd"

    if args.pixel_size_x is not None or args.pixel_size_y is not None:
        if args.pixel_size_x is None or args.pixel_size_y is None:
            raise SystemExit("Use both --pixel-size-x and --pixel-size-y, or neither.")
        return args.pixel_size_x, args.pixel_size_y, "manual pixel size"

    if args.raster is None:
        raise SystemExit("Provide --raster, --gsd, or both --pixel-size-x and --pixel-size-y.")

    pixel_size = read_pixel_size_from_geotiff(args.raster)
    return pixel_size.x_m, pixel_size.y_m, pixel_size.source_crs


def main() -> None:
    args = parse_args()
    pixel_size_x, pixel_size_y, pixel_size_source = resolve_pixel_size(args)

    feature_collection = load_geojson(args.geojson)
    total = len(feature_collection.get("features", []))

    if total == 0:
        print("No features found.")
        return

    print(f"Total bounding boxes: {total}")
    print(f"Pixel size: x={pixel_size_x:.4f} m/px, y={pixel_size_y:.4f} m/px")
    if pixel_size_source:
        print(f"Pixel size source: {pixel_size_source}")
    print()
    print(
        f"{'min_side':>9} {'max_side':>9} {'min_area':>9} {'max_area':>9} "
        f"{'rejected':>10} {'rejected_%':>11} {'kept':>10} {'kept_%':>8}"
    )

    for raw_config in args.configs:
        min_side, max_side, min_area, max_area = parse_config(raw_config)
        config = replace(
            RefinementConfig(),
            pixel_size_x_m=pixel_size_x,
            pixel_size_y_m=pixel_size_y,
            min_bbox_side_m=min_side,
            max_bbox_side_m=max_side,
            min_bbox_area_m2=min_area,
            max_bbox_area_m2=max_area,
            drop_rejected=False,
        )
        refined = apply_bbox_size_filter(feature_collection, config)
        rejected = sum(
            not feature["properties"]["refinement"]["keep"]
            for feature in refined.get("features", [])
        )
        kept = total - rejected
        rejected_percent = rejected / total * 100
        kept_percent = kept / total * 100

        print(
            f"{min_side:9.2f} {max_side:9.2f} {min_area:9.2f} {max_area:9.2f} "
            f"{rejected:10d} {rejected_percent:10.2f}% {kept:10d} {kept_percent:7.2f}%"
        )


if __name__ == "__main__":
    main()
