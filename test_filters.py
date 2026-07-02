from __future__ import annotations

from pathlib import Path

from annotation_refinement.config import RefinementConfig
from annotation_refinement.filters import (
    apply_confidence_filter,
    apply_bbox_size_filter,
    apply_bbox_aspect_ratio_filter,
    apply_duplicate_overlap_filter,
    apply_osm_water_filter,
    count_refinement_results,
)
from annotation_refinement.geojson_io import load_geojson, write_geojson
from annotation_refinement.raster_metadata import read_pixel_size_from_geotiff

INPUT_GEOJSON = Path("data/detections.geojson")
OUTPUT_GEOJSON = Path("data/detections_refined.geojson")
RASTER_PATH = Path("data/Egina_PN.tif")
OSM_WATER_GEOJSON = Path("data/water.geojson")


def main() -> None:
    # Eingabedateien laden
    annotations = load_geojson(INPUT_GEOJSON)

    # Pixelgröße aus GeoTIFF auslesen
    pixel_size = read_pixel_size_from_geotiff(RASTER_PATH)

    # Konfiguration mit Pixelgrößen
    config = RefinementConfig(
        pixel_size_x_m=pixel_size.x_m,
        pixel_size_y_m=pixel_size.y_m,
    )

    # Filter nacheinander anwenden (wie die Pipeline, aber manuell)
    refined = apply_confidence_filter(annotations, config)
    refined = apply_bbox_size_filter(refined, config)
    refined = apply_bbox_aspect_ratio_filter(refined, config)
    refined = apply_duplicate_overlap_filter(refined, config)
    refined = apply_osm_water_filter(refined, OSM_WATER_GEOJSON, config)

    counts = count_refinement_results(refined)
    print(f"Total: {counts['total']}, Kept: {counts['kept']}, Rejected: {counts['rejected']}")

    # Ergebnis speichern
    write_geojson(refined, OUTPUT_GEOJSON)


if __name__ == "__main__":
    main()