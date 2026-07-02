from __future__ import annotations
from pathlib import Path
from annotation_refinement import refine_feature_collection
from annotation_refinement.geojson_io import load_geojson, write_geojson

INPUT_GEOJSON = Path("data/detections.geojson")
OUTPUT_GEOJSON = Path("data/detections_refined.geojson")
RASTER_PATH = Path("data/Egina_PN.tif")
OSM_WATER_GEOJSON = Path("data/water.geojson")

# Eingabedateien laden
annotations = load_geojson(INPUT_GEOJSON)

# Pipeline ausführen (liest automatisch Raster-Metadaten und lädt OSM-Polygone)
refined = refine_feature_collection(
    annotations,
    raster_path=RASTER_PATH,
    osm_water_path=OSM_WATER_GEOJSON,  # optional, wird bei Bedarf heruntergeladen
)

# Ergebnis speichern
write_geojson(refined, OUTPUT_GEOJSON)