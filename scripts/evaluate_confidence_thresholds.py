from __future__ import annotations

import argparse

from annotation_refinement.geojson_io import load_geojson

"""
Example usage + output:

PYTHONPATH=src python3 scripts/evaluate_confidence_thresholds.py data/detections.geojson --thresholds 0.30 0.31 0.32 0.33 0.34 0.35

Total bounding boxes: 3894

 threshold   rejected  rejected_%       kept   kept_%
     0.300          0       0.00%       3894  100.00%
     0.310         47       1.21%       3847   98.79%
     0.320         91       2.34%       3803   97.66%
     0.330        137       3.52%       3757   96.48%
     0.340        176       4.52%       3718   95.48%
     0.350        219       5.62%       3675   94.38%
"""

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count how many bounding boxes would be rejected by confidence thresholds.",
    )
    parser.add_argument("geojson", help="Path to a detections GeoJSON file.")
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.25, 0.5, 0.75],
        help="Confidence thresholds to evaluate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    feature_collection = load_geojson(args.geojson)
    features = feature_collection.get("features", [])
    total = len(features)

    if total == 0:
        print("No features found.")
        return

    print(f"Total bounding boxes: {total}")
    print()
    print(f"{'threshold':>10} {'rejected':>10} {'rejected_%':>11} {'kept':>10} {'kept_%':>8}")

    scores = [feature.get("properties", {}).get("score") for feature in features]

    for threshold in args.thresholds:
        rejected = sum(score is None or float(score) < threshold for score in scores)
        kept = total - rejected
        rejected_percent = rejected / total * 100
        kept_percent = kept / total * 100

        print(
            f"{threshold:10.3f} "
            f"{rejected:10d} "
            f"{rejected_percent:10.2f}% "
            f"{kept:10d} "
            f"{kept_percent:7.2f}%"
        )


if __name__ == "__main__":
    main()
