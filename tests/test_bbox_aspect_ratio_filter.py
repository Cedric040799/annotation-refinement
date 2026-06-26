import unittest

from annotation_refinement import RefinementConfig, apply_bbox_aspect_ratio_filter


class BBoxAspectRatioFilterTest(unittest.TestCase):
    def test_requires_pixel_size(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"bounds_imcoords": "0,0,20,40"},
                }
            ],
        }

        with self.assertRaises(ValueError):
            apply_bbox_aspect_ratio_filter(feature_collection, RefinementConfig())

    def test_marks_extreme_aspect_ratio(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"bounds_imcoords": "0,0,130,10"},
                }
            ],
        }

        refined = apply_bbox_aspect_ratio_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=1.0,
                pixel_size_y_m=1.0,
                max_bbox_aspect_ratio=12.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertFalse(refinement["keep"])
        self.assertIn("bbox_aspect_ratio_too_extreme", refinement["reasons"])
        self.assertEqual(refinement["bbox_aspect_ratio"], 13.0)

    def test_keeps_ratio_at_threshold(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"bounds_imcoords": "0,0,120,10"},
                }
            ],
        }

        refined = apply_bbox_aspect_ratio_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=1.0,
                pixel_size_y_m=1.0,
                max_bbox_aspect_ratio=12.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertTrue(refinement["keep"])
        self.assertEqual(refinement["reasons"], [])
        self.assertEqual(refinement["bbox_aspect_ratio"], 12.0)

    def test_uses_meter_dimensions_not_pixel_dimensions(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"bounds_imcoords": "0,0,120,10"},
                }
            ],
        }

        refined = apply_bbox_aspect_ratio_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=0.5,
                pixel_size_y_m=1.0,
                max_bbox_aspect_ratio=12.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertTrue(refinement["keep"])
        self.assertEqual(refinement["bbox_aspect_ratio"], 6.0)


if __name__ == "__main__":
    unittest.main()
