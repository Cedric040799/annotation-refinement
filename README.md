# Annotation refinement/postprocessing module

Ziel ist es, vorhergesagte Bounding Boxes aus einem Object-Detection-Modell zu prüfen, zu markieren und später gezielt zu filtern, bevor sie als neue Trainingsdaten genutzt werden.

## Projektstruktur

```text
annotation_refinement/
├── README.md
├── pyproject.toml
├── src/
│   └── annotation_refinement/
│       ├── __init__.py
│       ├── config.py
│       ├── filters.py
│       ├── geojson_io.py
│       └── pipeline.py
└── tests/
    └── test_confidence_filter.py
```

Die wichtigsten Dateien:

- `src/annotation_refinement/config.py`: zentrale Defaultwerte für Filter.
- `src/annotation_refinement/filters.py`: einzelne Filterfunktionen.
- `src/annotation_refinement/geojson_io.py`: GeoJSON-Dateien lesen und schreiben.
- `src/annotation_refinement/pipeline.py`: Einstiegspunkt, der aktuell alle vorhandenen Filter nacheinander ausführt.
- `tests/`: kleine Unit-Tests für das aktuelle Verhalten.

## Funktionsweise

Die Pipeline arbeitet aktuell auf GeoJSON-`FeatureCollection`s. Erwartet wird ein GeoJSON mit Features, deren Confidence-Score in `feature["properties"]["score"]` steht.

Wichtig: Schlechte Bounding Boxes werden standardmäßig nicht direkt gelöscht. Stattdessen bekommen sie unter `properties.refinement` eine Bewertung:

```json
{
  "refinement": {
    "keep": false,
    "reasons": ["low_confidence"],
    "min_confidence": 0.33
  }
}
```

Dadurch bleiben die ursprünglichen Vorhersagen nachvollziehbar. Später können weitere Filter, Scores oder manuelle Review-Schritte darauf aufbauen.

Die bisher implementierten Filter sind:

- Confidence-Filter: markiert Features mit fehlendem Score oder einem Score unterhalb von `min_confidence`.
- Größenfilter: markiert Bounding Boxes, deren reale Seitenlängen oder Fläche nicht zu Straßenfahrzeugen passen.
- Aspect-Ratio-Filter: markiert extrem schmale Bounding Boxes.
- Duplicate-Overlap-Filter: markiert kleinere, niedriger bewertete Boxen, die fast vollständig in größeren Boxen liegen.

Mit `drop_rejected=True` können abgelehnte Features stattdessen direkt aus der Ausgabe entfernt werden.

## Verwendung

Direkt aus dem Repository kann das Modul mit gesetztem `PYTHONPATH` genutzt werden:

```bash
PYTHONPATH=src python3 -c "from annotation_refinement import RefinementConfig; print(RefinementConfig())"
```

Ein einfaches Beispiel für eine GeoJSON-Datei:

```python
from annotation_refinement import RefinementConfig, refine_feature_collection
from annotation_refinement.geojson_io import load_geojson, write_geojson

annotations = load_geojson("data/detections.geojson")

refined = refine_feature_collection(
    annotations,
    RefinementConfig(
        min_confidence=0.33,
        drop_rejected=False,
    ),
)

write_geojson(refined, "data/detections_refined.geojson")
```

Wenn wirklich nur akzeptierte Features in der Ausgabe landen sollen:

```python
refined = refine_feature_collection(
    annotations,
    RefinementConfig(
        min_confidence=0.33,
        drop_rejected=True,
    ),
)
```


### Duplicate-Overlap-Filter

Der Duplicate-Overlap-Filter sucht Fälle, in denen eine kleinere Bounding Box zu einem sehr großen Anteil in einer größeren Bounding Box liegt. Markiert wird die kleinere Box nur, wenn ihr Confidence-Score mindestens `min_duplicate_score_delta` niedriger ist als der Score der größeren Box.

Das soll doppelte Vorhersagen für dasselbe Objekt entfernen, ohne normale Überlappungen in dichten Szenen zu stark zu bestrafen. Für Performance werden die Boxen in ein Pixel-Grid einsortiert, sodass nur räumlich nahe Boxen miteinander verglichen werden.

```bash
PYTHONPATH=src python3 scripts/evaluate_duplicate_overlap_thresholds.py data/detections.geojson \
  --configs 0.90,0.05 0.95,0.05 0.95,0.10 0.98,0.05
```

Die Werte bedeuten `min_containment,min_score_delta`. Beispiel: `0.95,0.10` markiert eine kleinere Box nur dann, wenn mindestens 95% ihrer Fläche in der größeren Box liegen und ihr Score mindestens 0.10 niedriger ist.

## Tests

Die Tests laufen mit:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```



## Notizen / Text-Mindmap

```
- Architektur:
    - importierbares Modul
        - jede Stufe einzeln nutzbar
        - von außen kommen geoTifs und geo JSONs mit metadaten.
        - intern sollten die Daten als gerenderts Arrays bzw. Pixel-Koordinaten behandelt werden.  
    - evtl. logging
    - die defaultwerte für die Filter sollten in einer config Datei liegen

- Input: geojson mit Bounding Boxes, confidence etc. + tif Bild
    - @Ced falls benötigt kann ich den Export der tifs und jsons ziemlich beliebig anpassen.
    - siehe: https://github.com/OHB-DS/THEIA_Vehicle_Detection/blob/main/src/infer.py

- schlechte bounding boxes nicht direkt rausschmeißen, sondern erst mal nur bewerten/sortieren
    --> damit lässt sich später ein Bildausschnitt bewerten und ggf. entfernen

- Filter-Ansätze:

    - Confidence-Score:
        --> Schwellenwert nicht klar ersichtlich, also wirklich nur sehr unsichere Vorhersagen entfernen
        --> in Kombination mit anderen Filtern verwenden

    - Größe der Bounding Box:
        --> filtern von extrem kleinen oder extrem großen Boxen
        --> wenn nicht einheitlich: räumliche Auflösung der Bilder einbeziehen
        - Plan ist im Bereich GSD 5cm bis 4m zu arbeiten.

    - Aspekt Ratio der Bounding Box:
        --> filtern von extrem schmalen Boxen

    - Überlappende Bounding Boxes:
        --> filtern, wenn eine kleinere Box (nahezu) vollständig in einer größeren Box liegt + kleiner Confidence-Score
        - Vorsicht bei dichten Szenen. Gerade Parkplätze.
        - Behalte verschiedene Auflösungen im Kopf. Fixe Werte können dramatisch daneben liegen, wenn sich GSD ändert.
        --> für performance: vermeiden, alle gegen alle zu vergleichen
        - zB nearest neighbors
    
    - OpenStreetMap-Daten:
        --> CRS konsistent halten
        --> filtern von Boxen, die in Gebieten liegen, in denen die Fahrzeuge nicht sein sollten (z.B. Autos auf Wasserflächen)
            --> zuordnung über Mittelpunkt der Bounding Box oder über Schwellenwert der Überlappung mit OSM-Polygonen
            - OSM ist eine top Quelle. Man könnte zB auch Straßen und Parkplätze (+ margin) wohlwollender bewerten.
            - Vorsicht bei der Präzision. Selbst bei guten EO Daten ist die Registrierung oft mehrere Meter daneben!


- Man könnte auch Scoring statt Hard Filtering nutzen:
    --> Also sowas wie:

        final_score =
            confidence
            * size_factor
            * overlap_penalty
            * osm_penalty
            ... (weitere Faktoren)
    --> das kann man aber auch erst mal aufschieben, wenn hard filtering gut funktioniert
        --> erstmal hard filtering implementieren, dann ggf. scoring einbauen
```
