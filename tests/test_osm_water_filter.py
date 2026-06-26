import unittest

from annotation_refinement import RefinementConfig, apply_osm_water_filter


WATER_POLYGONS = [
    [
        [
        (0.0, 0.0),
        (0.02, 0.0),
        (0.02, 0.02),
        (0.0, 0.02),
            (0.0, 0.0),
        ]
    ]
]


def feature(bounds):
    min_lon, min_lat, max_lon, max_lat = bounds
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [min_lon, max_lat],
                    [max_lon, max_lat],
                    [max_lon, min_lat],
                    [min_lon, min_lat],
                    [min_lon, max_lat],
                ]
            ],
        },
        "properties": {"score": 0.9},
    }


class OSMWaterFilterTest(unittest.TestCase):
    def test_marks_box_safely_inside_water(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature((0.009, 0.009, 0.011, 0.011))],
        }

        refined = apply_osm_water_filter(
            feature_collection,
            WATER_POLYGONS,
            RefinementConfig(osm_water_boundary_buffer_m=20.0),
        )

        refinement = refined["features"][0]["properties"]["refinement"]
        self.assertFalse(refinement["keep"])
        self.assertIn("osm_water_forbidden_area", refinement["reasons"])
        self.assertGreater(refinement["osm_water"]["min_boundary_distance_m"], 20.0)

    def test_keeps_box_near_water_boundary(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature((0.0001, 0.009, 0.001, 0.011))],
        }

        refined = apply_osm_water_filter(
            feature_collection,
            WATER_POLYGONS,
            RefinementConfig(osm_water_boundary_buffer_m=20.0),
        )

        self.assertTrue(
            refined["features"][0]["properties"].get("refinement", {}).get("keep", True)
        )

    def test_keeps_box_outside_water(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [feature((0.03, 0.03, 0.031, 0.031))],
        }

        refined = apply_osm_water_filter(
            feature_collection,
            WATER_POLYGONS,
            RefinementConfig(osm_water_boundary_buffer_m=0.0),
        )

        self.assertTrue(
            refined["features"][0]["properties"].get("refinement", {}).get("keep", True)
        )

    def test_can_drop_rejected_water_boxes(self):
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                feature((0.009, 0.009, 0.011, 0.011)),
                feature((0.03, 0.03, 0.031, 0.031)),
            ],
        }

        refined = apply_osm_water_filter(
            feature_collection,
            WATER_POLYGONS,
            RefinementConfig(osm_water_boundary_buffer_m=20.0, drop_rejected=True),
        )

        self.assertEqual(len(refined["features"]), 1)


if __name__ == "__main__":
    unittest.main()
