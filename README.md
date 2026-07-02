# Annotation Refinement

Ein Python-Modul zur automatisierten Nachbearbeitung von Bounding-Box-Vorhersagen aus Object-Detection-Modellen. Die Filter markieren oder entfernen fehlerhafte Vorhersagen, bevor Daten für das nächste Training verwendet werden.

## Features

- **Confidence-Filter**: Entfernt oder markiert Bounding Boxes mit zu niedrigem Confidence-Score
- **Größen-Filter**: Filtert unrealistische Bounding-Box-Größen basierend auf Raster-Metadaten
- **Aspect-Ratio-Filter**: Markiert extrem schmale oder verzerrte Bounding Boxes
- **Duplicate-Overlap-Filter**: Entfernt redundante Erkennungen von denselben Objekten
- **OSM-Wasser-Filter**: Filtert Bounding Boxes in Wasserflächen (basierend auf OpenStreetMap-Daten)

## Installation

```bash
pip install -e .
```

oder mit `PYTHONPATH`:

```bash
PYTHONPATH=src python3 your_script.py
```

## Schnellstart

### Komplette Pipeline verwenden

```python
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
```

### Einzelne Filter verwenden

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import apply_confidence_filter, RefinementConfig
from annotation_refinement.geojson_io import load_geojson

INPUT_GEOJSON = Path("data/detections.geojson")

annotations = load_geojson(INPUT_GEOJSON)

# Nur Confidence-Filter
refined = apply_confidence_filter(annotations)

# Mit angepassten Parametern
config = RefinementConfig(min_confidence=0.5)
refined = apply_confidence_filter(annotations, config)
```

Hinweis: Wenn du einzelne Filter (insbesondere Größen- oder Aspect-Ratio-Filter) einzeln verwendest, müssen die Raster-Pixelgrößen in der `RefinementConfig` gesetzt sein — siehe Abschnitt [Raster-Metadaten (GeoTIFF)](#raster-metadaten-geotiff) weiter unten.

Jeder Filter kann einzeln auf vorher gefilterte Daten angewendet werden:

```python
from annotation_refinement import (
    apply_confidence_filter,
    apply_bbox_size_filter,
    apply_bbox_aspect_ratio_filter,
    apply_duplicate_overlap_filter,
    apply_osm_water_filter,
)

# Filter nacheinander anwenden
refined = apply_confidence_filter(annotations, config)
refined = apply_bbox_size_filter(refined, config)
refined = apply_bbox_aspect_ratio_filter(refined, config)
# ... etc.
```

## Konfiguration

Die `RefinementConfig`-Klasse stellt Standardwerte für alle Filter bereit. Sie können diese direkt überschreiben:

```python
from annotation_refinement import RefinementConfig

config = RefinementConfig(
    # Confidence-Filter
    min_confidence=0.33,
    
    # Größen-Filter (in Metern)
    min_bbox_side_m=1.0,
    max_bbox_side_m=30.0,
    min_bbox_area_m2=2.0,
    max_bbox_area_m2=500.0,
    
    # Aspect-Ratio-Filter
    max_bbox_aspect_ratio=12.0,
    
    # Duplicate-Overlap-Filter
    min_duplicate_containment=0.99,
    min_duplicate_score_delta=0.10,
    
    # OSM-Wasser-Filter
    osm_water_boundary_buffer_m=8.0,
    
    # Ausgabe
    drop_rejected=False,  # oder True, um abgelehnte Features zu entfernen
)
```

## Raster-Metadaten (GeoTIFF)

Die Größen- und Aspect-Ratio-Filter benötigen die Pixelgröße des Rasters in Metern. Diese wird automatisch aus GeoTIFF-Metadaten ausgelesen:

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import read_pixel_size_from_geotiff

RASTER_PATH = Path("data/Egina_PN.tif")

pixel_size = read_pixel_size_from_geotiff(RASTER_PATH)
print(f"Pixelgröße: {pixel_size.x_m} x {pixel_size.y_m} Meter")
```

Wenn du `refine_feature_collection()` mit `raster_path` aufrufst, werden die Metadaten automatisch gelesen und die Größenfilter in echten Metern angewendet.

Wenn du jedoch die Filter einzeln verwendest (also nicht die Pipeline), musst du die Pixelgröße selbst an die Filter-Config übergeben. Die folgenden Filter nutzen die Pixelgröße und werfen einen Fehler, falls sie nicht gesetzt ist:

- `apply_bbox_size_filter`
- `apply_bbox_aspect_ratio_filter`

Beispiel: GeoTIFF auslesen und an einzelne Filter übergeben

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import (
  read_pixel_size_from_geotiff,
  RefinementConfig,
  apply_bbox_size_filter,
)

RASTER_PATH = Path("data/Egina_PN.tif")
INPUT_GEOJSON = Path("data/detections.geojson")

# Pixelgröße aus GeoTIFF auslesen
pixel = read_pixel_size_from_geotiff(RASTER_PATH)

# Konfiguration mit expliziter Pixelgröße
config = RefinementConfig(
  pixel_size_x_m=pixel.x_m,
  pixel_size_y_m=pixel.y_m,
)

# Einzelnen Filter anwenden
from annotation_refinement.geojson_io import load_geojson
annotations = load_geojson(INPUT_GEOJSON)
refined = apply_bbox_size_filter(annotations, config)
```

Alternativ kannst du die Pixelgröße auch manuell einstellen (z. B. bei bekannten GSD-Werten), aber die zuverlässigste Methode ist das Auslesen aus dem passenden GeoTIFF mit `read_pixel_size_from_geotiff()`.

## OSM-Wasser-Filter

Der OSM-Wasser-Filter markiert Bounding Boxes, die in Wasserflächen liegen (als sicher falsche Positive).

### Automatische OSM-Polygone

Wenn du Polygone nicht selbst bereitstellst, werden sie automatisch heruntergeladen.

Wenn du `osm_water_path` angibst, muss die Datei an diesem Pfad noch nicht existieren: der Pfad wird dann als Cache verwendet. Die Polygone werden bei Bedarf heruntergeladen und im angegebenen Pfad gespeichert. Bei Netzwerkproblemen wird mehrfach versucht, die Daten von verschiedenen Overpass-Endpunkten zu laden; schlägt das wiederholt fehl, wird eine Warnung ausgegeben und die Pipeline läuft ohne OSM-Filter weiter.

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import apply_osm_water_filter

OSM_WATER_GEOJSON = Path("data/water.geojson")

# Automatische Beschaffung: Polygone basierend auf der Feature-Ausdehnung
refined = apply_osm_water_filter(annotations)

# oder mit einem Cache-Pfad (wird bei Bedarf heruntergeladen)
refined = apply_osm_water_filter(annotations, OSM_WATER_GEOJSON)
```

### Vordefinierte OSM-Polygone

Wenn du eine GeoJSON-Datei mit OSM-Wasser-Polygonen hast, kannst du diese verwenden:

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import apply_osm_water_filter

OSM_WATER_GEOJSON = Path("data/water.geojson")

refined = apply_osm_water_filter(annotations, OSM_WATER_GEOJSON)
```

Or use `download_osm_water_polygons()` zum manuellen Herunterladen:

```python
from __future__ import annotations
from pathlib import Path
from annotation_refinement import download_osm_water_polygons

OSM_WATER_GEOJSON = Path("data/water.geojson")

# Download für einen bestimmten Bereich (optional)
bbox = (10.0, 50.0, 15.0, 55.0)  # west, south, east, north
path = download_osm_water_polygons(OSM_DOWNLOAD_PATH, bbox=bbox)
```

## Ergebnis-Format

Standardmäßig werden abgelehnte Bounding Boxes **nicht gelöscht**, sondern mit Metadaten annotiert:

```json
{
  "type": "Feature",
  "geometry": {...},
  "properties": {
    "score": 0.85,
    "refinement": {
      "keep": false,
      "reasons": ["low_confidence"],
      "min_confidence": 0.33
    }
  }
}
```

Mit `drop_rejected=True` werden abgelehnte Features aus der Ausgabe entfernt.

## Beispiele

Siehe `test_filters.py` für ein Beispiel mit einzelnen Filtern und `pipeline_example.py` für ein Komplettbeispiel mit der Pipeline.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
