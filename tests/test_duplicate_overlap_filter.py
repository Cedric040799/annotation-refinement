import unittest

from annotation_refinement import RefinementConfig, apply_duplicate_overlap_filter


class DuplicateOverlapFilterTest(unittest.TestCase):
    def test_marks_lower_confidence_smaller_box_mostly_inside_larger_box(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"score": 0.95, "bounds_imcoords": "0,0,100,100"},
                },
                {
                    "type": "Feature",
                    "properties": {"score": 0.80, "bounds_imcoords": "10,10,50,50"},
                },
            ],
        }

        refined = apply_duplicate_overlap_filter(
            feature_collection,
            RefinementConfig(
                min_duplicate_containment=0.9,
                min_duplicate_score_delta=0.05,
            ),
        )

        kept = refined["features"][0]["properties"].get("refinement", {}).get("keep", True)
        rejected = refined["features"][1]["properties"]["refinement"]
        self.assertTrue(kept)
        self.assertFalse(rejected["keep"])
        self.assertIn("duplicate_overlap_lower_confidence", rejected["reasons"])
        self.assertEqual(rejected["duplicate_overlap"]["matched_feature_index"], 0)
        self.assertEqual(rejected["duplicate_overlap"]["containment"], 1.0)

    def test_keeps_smaller_box_when_score_is_not_clearly_lower(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"score": 0.95, "bounds_imcoords": "0,0,100,100"},
                },
                {
                    "type": "Feature",
                    "properties": {"score": 0.93, "bounds_imcoords": "10,10,50,50"},
                },
            ],
        }

        refined = apply_duplicate_overlap_filter(
            feature_collection,
            RefinementConfig(
                min_duplicate_containment=0.9,
                min_duplicate_score_delta=0.05,
            ),
        )

        for feature in refined["features"]:
            self.assertTrue(feature["properties"].get("refinement", {}).get("keep", True))

    def test_keeps_overlap_without_high_smaller_box_containment(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"score": 0.95, "bounds_imcoords": "0,0,120,40"},
                },
                {
                    "type": "Feature",
                    "properties": {"score": 0.70, "bounds_imcoords": "80,0,140,40"},
                },
            ],
        }

        refined = apply_duplicate_overlap_filter(
            feature_collection,
            RefinementConfig(
                min_duplicate_containment=0.9,
                min_duplicate_score_delta=0.05,
            ),
        )

        for feature in refined["features"]:
            self.assertTrue(feature["properties"].get("refinement", {}).get("keep", True))

    def test_can_drop_rejected_duplicate_boxes(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"score": 0.95, "bounds_imcoords": "0,0,100,100"},
                },
                {
                    "type": "Feature",
                    "properties": {"score": 0.80, "bounds_imcoords": "10,10,50,50"},
                },
            ],
        }

        refined = apply_duplicate_overlap_filter(
            feature_collection,
            RefinementConfig(drop_rejected=True),
        )

        self.assertEqual(len(refined["features"]), 1)
        self.assertEqual(refined["features"][0]["properties"]["score"], 0.95)


if __name__ == "__main__":
    unittest.main()
