import unittest

from annotation_refinement import RefinementConfig, apply_confidence_filter


class ConfidenceFilterTest(unittest.TestCase):
    def test_marks_low_confidence_without_dropping_by_default(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"score": 0.9}},
                {"type": "Feature", "properties": {"score": 0.1}},
            ],
        }

        refined = apply_confidence_filter(
            feature_collection,
            RefinementConfig(min_confidence=0.25),
        )

        self.assertEqual(len(refined["features"]), 2)
        self.assertTrue(refined["features"][0]["properties"]["refinement"]["keep"])
        self.assertFalse(refined["features"][1]["properties"]["refinement"]["keep"])
        self.assertEqual(
            refined["features"][1]["properties"]["refinement"]["reasons"],
            ["low_confidence"],
        )

    def test_can_drop_rejected_features(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"score": 0.9}},
                {"type": "Feature", "properties": {"score": 0.1}},
            ],
        }

        refined = apply_confidence_filter(
            feature_collection,
            RefinementConfig(min_confidence=0.25, drop_rejected=True),
        )

        self.assertEqual(len(refined["features"]), 1)
        self.assertEqual(refined["features"][0]["properties"]["score"], 0.9)


if __name__ == "__main__":
    unittest.main()
