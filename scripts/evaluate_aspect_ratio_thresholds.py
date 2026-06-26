from __future__ import annotations

import argparse
from dataclasses import replace

from annotation_refinement import RefinementConfig, apply_bbox_aspect_ratio_filter
from annotation_refinement.geojson_io import load_geojson
from annotation_refinement.raster_metadata import read_pixel_size_from_geotiff

"""
Example usage + output:

PYTHONPATH=src python3 scripts/evaluate_aspect_ratio_thresholds.py data/detections.geojson   --raster data/Egina_PN.tif   --ratios 2 2.5 3 3.5 4 4.5 5 5.5 6 6.5 7 7.5 8

Total bounding boxes: 3894
Pixel size: x=0.2379 m/px, y=0.2997 m/px
Pixel size source: EPSG:4326

max_ratio   rejected  rejected_%       kept   kept_%
     2.00        660      16.95%       3234   83.05%
     2.50        208       5.34%       3686   94.66%
     3.00        115       2.95%       3779   97.05%
     3.50         77       1.98%       3817   98.02%
     4.00         51       1.31%       3843   98.69%
     4.50         36       0.92%       3858   99.08%
     5.00         25       0.64%       3869   99.36%
     5.50         15       0.39%       3879   99.61%
     6.00         11       0.28%       3883   99.72%
     6.50          8       0.21%       3886   99.79%
     7.00          4       0.10%       3890   99.90%
     7.50          3       0.08%       3891   99.92%
     8.00          0       0.00%       3894  100.00%
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count how many bounding boxes would be rejected by aspect-ratio thresholds.",
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument("--raster", help="Matching GeoTIFF. Pixel size is read from this file.")
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
        "--ratios",
        nargs="+",
        type=float,
        default=[8.0, 10.0, 12.0, 15.0],
        help="Maximum allowed longer-side / shorter-side ratios.",
    )
    return parser.parse_args()


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
    print(f"{'max_ratio':>9} {'rejected':>10} {'rejected_%':>11} {'kept':>10} {'kept_%':>8}")

    for max_ratio in args.ratios:
        config = replace(
            RefinementConfig(),
            pixel_size_x_m=pixel_size_x,
            pixel_size_y_m=pixel_size_y,
            max_bbox_aspect_ratio=max_ratio,
            drop_rejected=False,
        )
        refined = apply_bbox_aspect_ratio_filter(feature_collection, config)
        rejected = sum(
            not feature["properties"]["refinement"]["keep"]
            for feature in refined.get("features", [])
        )
        kept = total - rejected
        rejected_percent = rejected / total * 100
        kept_percent = kept / total * 100

        print(
            f"{max_ratio:9.2f} {rejected:10d} {rejected_percent:10.2f}% "
            f"{kept:10d} {kept_percent:7.2f}%"
        )


if __name__ == "__main__":
    main()
