import unittest

from annotation_refinement import RefinementConfig, apply_bbox_size_filter


class BBoxSizeFilterTest(unittest.TestCase):

    def test_requires_pixel_size(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "score": 0.9,
                        "bounds_imcoords": "0,0,20,40",
                    },
                }
            ],
        }

        with self.assertRaises(ValueError):
            apply_bbox_size_filter(feature_collection, RefinementConfig())

    def test_marks_too_small_boxes_using_pixel_size(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "score": 0.9,
                        "bounds_imcoords": "0,0,2,2",
                    },
                }
            ],
        }

        refined = apply_bbox_size_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=0.25,
                pixel_size_y_m=0.25,
                min_bbox_side_m=1.0,
                min_bbox_area_m2=1.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertFalse(refinement["keep"])
        self.assertIn("bbox_too_small", refinement["reasons"])
        self.assertEqual(refinement["bbox_size_m"]["width"], 0.5)
        self.assertEqual(refinement["bbox_size_m"]["height"], 0.5)

    def test_marks_too_large_boxes_using_pixel_size(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "score": 0.9,
                        "bounds_imcoords": "0,0,200,200",
                    },
                }
            ],
        }

        refined = apply_bbox_size_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=0.5,
                pixel_size_y_m=0.5,
                max_bbox_side_m=30.0,
                max_bbox_area_m2=500.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertFalse(refinement["keep"])
        self.assertIn("bbox_too_large", refinement["reasons"])

    def test_keeps_vehicle_sized_boxes(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "score": 0.9,
                        "bounds_imcoords": "0,0,20,40",
                    },
                }
            ],
        }

        refined = apply_bbox_size_filter(
            feature_collection,
            RefinementConfig(
                pixel_size_x_m=0.25,
                pixel_size_y_m=0.25,
                min_bbox_side_m=1.0,
                max_bbox_side_m=30.0,
                min_bbox_area_m2=2.0,
                max_bbox_area_m2=500.0,
            ),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertTrue(refinement["keep"])
        self.assertEqual(refinement["reasons"], [])


if __name__ == "__main__":
    unittest.main()
