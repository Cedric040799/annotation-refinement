# Annotation refinement/postprocessing module

## Notizen / Text-Mindmap

```
- Architektur:
    - importierbares Modul
        - jede Stufe einzeln nutzbar
        - von außen kommen geoTifs und geo JSONs mit metadaten.
        - intern sollten die Daten als gerenderts Arrays bzw. Pixel-Koordinaten behandelt werden.  
    - evtl. logging
    - 

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
        -oder unnatürliche Seitenverhältnisse.
        --> wenn nicht einheitlich: räumliche Auflösung der Bilder einbeziehen
        - Plan ist im Bereich GSD 5cm bis 4m zu arbeiten.

    - Aspekt Ratio der Bounding Box:
        --> filtern von extrem schmalen Boxen

    - Überlappende Bounding Boxes:
        --> filtern, wenn eine kleinere Box (nahezu) vollständig in einer größeren Box liegt + kleiner Confidence-Score
        - Vorsicht bei dichten Szenen. Gerade Parkplätze.
        - Behalte verschiedene Auflösungen im Kopf. Fixe Werte können dramatisch daniben liegen, wenn sich GSD ändert.
        --> für performance: vermeiden, alle gegen alle zu vergleichen
        - zB nearest neighbeours
    
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
```
