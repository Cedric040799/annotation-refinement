import unittest

from annotation_refinement import count_refinement_results, drop_rejected_features


def feature(score: float | None = 0.5, keep: bool | None = None):
    refinement = {}
    if keep is not None:
        refinement["keep"] = keep
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]},
        "properties": {"score": score, "refinement": refinement},
    }


class FilterHelpersTest(unittest.TestCase):
    def test_count_refinement_results_counts_total_kept_and_rejected(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                feature(0.9, keep=True),
                feature(0.2, keep=False),
                feature(0.8, keep=True),
                feature(0.5, keep=None),
            ],
        }

        result = count_refinement_results(feature_collection)

        self.assertEqual(result["total"], 4)
        self.assertEqual(result["kept"], 3)
        self.assertEqual(result["rejected"], 1)

    def test_drop_rejected_features_removes_rejected_annotations(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                feature(0.9, keep=True),
                feature(0.2, keep=False),
                feature(0.8, keep=True),
            ],
        }

        reduced = drop_rejected_features(feature_collection)

        self.assertEqual(len(reduced["features"]), 2)
        self.assertTrue(all(
            feature.get("properties", {}).get("refinement", {}).get("keep", True) is not False
            for feature in reduced["features"]
        ))

    def test_drop_rejected_features_keeps_features_without_refinement(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": None},
                feature(0.2, keep=False),
            ],
        }

        reduced = drop_rejected_features(feature_collection)

        self.assertEqual(len(reduced["features"]), 1)
        self.assertEqual(reduced["features"][0].get("properties", {}), {})


if __name__ == "__main__":
    unittest.main()
