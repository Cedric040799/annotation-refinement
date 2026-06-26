from __future__ import annotations

import argparse
from dataclasses import replace

from annotation_refinement import RefinementConfig, apply_duplicate_overlap_filter
from annotation_refinement.geojson_io import load_geojson

"""
Example usage + output:

PYTHONPATH=src python3 scripts/evaluate_duplicate_overlap_thresholds.py data/detections.geojson   --configs 0.98,0.05 0.98,0.10 0.99,0.05 0.99,0.10

Total bounding boxes: 3894
Grid cell size: 256.0 px

  contain  score_d   rejected  rejected_%       kept   kept_%
     0.98     0.05         54       1.39%       3840   98.61%
     0.98     0.10         41       1.05%       3853   98.95%
     0.99     0.05         40       1.03%       3854   98.97%
     0.99     0.10         31       0.80%       3863   99.20%
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Count how many boxes would be rejected as lower-confidence duplicates "
            "mostly contained in larger boxes."
        ),
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument(
        "--configs",
        nargs="+",
        default=["0.90,0.05", "0.95,0.05", "0.95,0.10", "0.98,0.05"],
        help=(
            "Threshold configs as min_containment,min_score_delta. "
            "Example: --configs 0.90,0.05 0.95,0.10"
        ),
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        default=256.0,
        help="Spatial grid cell size in image pixels. Default: 256.",
    )
    return parser.parse_args()


def parse_config(value: str) -> tuple[float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"Expected min_containment,min_score_delta, got: {value}"
        )
    return tuple(parts)  # type: ignore[return-value]


def main() -> None:
    args = parse_args()
    feature_collection = load_geojson(args.geojson)
    total = len(feature_collection.get("features", []))

    if total == 0:
        print("No features found.")
        return

    print(f"Total bounding boxes: {total}")
    print(f"Grid cell size: {args.cell_size:.1f} px")
    print()
    print(
        f"{'contain':>9} {'score_d':>8} {'rejected':>10} "
        f"{'rejected_%':>11} {'kept':>10} {'kept_%':>8}"
    )

    for raw_config in args.configs:
        min_containment, min_score_delta = parse_config(raw_config)
        config = replace(
            RefinementConfig(),
            min_duplicate_containment=min_containment,
            min_duplicate_score_delta=min_score_delta,
            duplicate_grid_cell_size_px=args.cell_size,
            drop_rejected=False,
        )
        refined = apply_duplicate_overlap_filter(feature_collection, config)
        rejected = sum(
            not feature["properties"].get("refinement", {}).get("keep", True)
            for feature in refined.get("features", [])
        )
        kept = total - rejected
        rejected_percent = rejected / total * 100
        kept_percent = kept / total * 100

        print(
            f"{min_containment:9.2f} {min_score_delta:8.2f} {rejected:10d} "
            f"{rejected_percent:10.2f}% {kept:10d} {kept_percent:7.2f}%"
        )


if __name__ == "__main__":
    main()
