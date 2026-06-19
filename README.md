# Annotation refinement/postprocessing module

## Notizen / Text-Mindmap

```
- Architektur:
    - importierbares Modul
    - jede Stufe einzeln nutzbar
    - evtl. logging

- Input: geojson mit Bounding Boxes, confidence etc. + tif Bild

- schlechte bounding boxes nicht direkt rausschmeißen, sondern erst mal nur bewerten/sortieren
    --> damit lässt sich später ein Bildausschnitt bewerten und ggf. entfernen

- Filter-Ansätze:

    - Confidence-Score:
        --> Schwellenwert nicht klar ersichtlich, also wirklich nur sehr unsichere Vorhersagen entfernen
        --> in Kombination mit anderen Filtern verwenden

    - Größe der Bounding Box:
        --> filtern von extrem kleinen oder extrem großen Boxen
        --> wenn nicht einheitlich: räumliche Auflösung der Bilder einbeziehen

    - Aspekt Ratio der Bounding Box:
        --> filtern von extrem schmalen Boxen

    - Überlappende Bounding Boxes:
        --> filtern, wenn eine kleinere Box (nahezu) vollständig in einer größeren Box liegt + kleiner Confidence-Score
        --> für performance: vermeiden, alle gegen alle zu vergleichen
    
    - OpenStreetMap-Daten:
        --> CRS konsistent halten
        --> filtern von Boxen, die in Gebieten liegen, in denen die Fahrzeuge nicht sein sollten (z.B. Autos auf Wasserflächen)
            --> zuordnung über Mittelpunkt der Bounding Box oder über Schwellenwert der Überlappung mit OSM-Polygonen


- Man könnte auch Scoring statt Hard Filtering nutzen:
    --> Also sowas wie:

        final_score =
            confidence
            * size_factor
            * overlap_penalty
            * osm_penalty
            ... (weitere Faktoren)
```
