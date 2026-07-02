from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
import urllib.error
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

Point = tuple[float, float]
Ring = list[Point]
Polygon = list[Ring]


@dataclass(frozen=True)
class WaterMatch:
    polygon_index: int
    min_boundary_distance_m: float


def download_osm_water_polygons(
    output_path: str | Path,
    bbox: tuple[float, float, float, float] | None = None,
) -> Path:
    """Download OSM water polygons for a geographic bounding box as GeoJSON.

    If no bbox is provided, the function falls back to a global bounding box.
    The data is fetched from the public Overpass API and stored as a GeoJSON
    FeatureCollection so it can be consumed by the existing water filter.
    """
    output_path = Path(output_path)

    if output_path.exists():
        print(f"Using existing water polygons: {output_path}")
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if bbox is None:
        bbox = (-180.0, -90.0, 180.0, 90.0)

    min_lon, min_lat, max_lon, max_lat = _normalize_bbox(bbox)

    print(
        "Downloading OSM water polygons for bbox "
        f"[{min_lon:.5f}, {min_lat:.5f}, {max_lon:.5f}, {max_lat:.5f}]..."
    )

    query = _build_overpass_query(min_lon, min_lat, max_lon, max_lat)
    encoded_query = urllib.parse.urlencode({"data": query}).encode("utf-8")

    # Try a small set of Overpass instances with a simple retry/backoff strategy
    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://lz4.overpass.openstreetmap.fr/api/interpreter",
    ]

    payload = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                request = urllib.request.Request(
                    endpoint,
                    data=encoded_query,
                    headers={"User-Agent": "annotation-refinement/0.1"},
                )
                timeout = 120 + (attempt - 1) * 30
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = json.load(response)
                break
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network-dependent path
                print(f"Overpass request failed (attempt {attempt}) at {endpoint}: {exc}")
                # try next endpoint
                continue
        if payload is not None:
            break
        # backoff before next round of attempts
        sleep = 2 ** attempt
        time.sleep(sleep)

    if payload is None:
        raise RuntimeError("Failed to download OSM water polygons after multiple attempts")

    features = []
    for element in payload.get("elements", []):
        geometry = _overpass_element_to_geojson_geometry(element)
        if geometry is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "source": "overpass",
                    "id": element.get("id"),
                    "type": element.get("type"),
                },
            }
        )

    if not features:
        raise RuntimeError("No OSM water polygons found for the requested bounding box")

    geojson = {"type": "FeatureCollection", "features": features}
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(geojson, file)

    print(f"Water polygons saved to: {output_path}")
    return output_path


def _normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min(min_lon, max_lon), min(min_lat, max_lat), max(min_lon, max_lon), max(min_lat, max_lat))


def _build_overpass_query(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    return f"""
    [out:json][timeout:180];
    (
      way["natural"="water"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["waterway"="riverbank"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["waterway"="river"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["waterway"="canal"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["landuse"="reservoir"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["natural"="water"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["waterway"="riverbank"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """


def _overpass_element_to_geojson_geometry(element: dict[str, Any]) -> dict[str, Any] | None:
    element_type = element.get("type")
    geometry = element.get("geometry")
    if element_type == "way" and isinstance(geometry, list):
        coordinates = []
        for point in geometry:
            if not isinstance(point, dict):
                continue
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None or lon is None:
                continue
            coordinates.append([lon, lat])
        if not coordinates:
            return None
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}

    if element_type == "relation" and isinstance(geometry, list):
        polygons = []
        for part in geometry:
            if not isinstance(part, dict):
                continue
            coordinates = []
            for point in part.get("geometry", []) or []:
                if not isinstance(point, dict):
                    continue
                lat = point.get("lat")
                lon = point.get("lon")
                if lat is None or lon is None:
                    continue
                coordinates.append([lon, lat])
            if coordinates:
                if coordinates[0] != coordinates[-1]:
                    coordinates.append(coordinates[0])
                polygons.append(coordinates)
        if polygons:
            return {"type": "MultiPolygon", "coordinates": [polygons]}

    return None


FeatureCollection = dict[str, Any]


def load_water_polygons(path: str | Path) -> list[Polygon]:
    """Load Polygon and MultiPolygon geometries from a GeoJSON file."""

    with Path(path).open(encoding="utf-8") as file:
        geojson = json.load(file)

    geometries = _iter_geometries(geojson)
    polygons: list[Polygon] = []
    for geometry in geometries:
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "Polygon":
            polygon = _parse_polygon(coordinates)
            if polygon:
                polygons.append(polygon)
        elif geometry_type == "MultiPolygon":
            for raw_polygon in coordinates or []:
                polygon = _parse_polygon(raw_polygon)
                if polygon:
                    polygons.append(polygon)

    return polygons


def load_or_download_water_polygons(
    osm_water_source: str | Path | list[Polygon] | None = None,
    feature_collection: FeatureCollection | None = None,
) -> list[Polygon]:
    """Load water polygons from a GeoJSON file or download them when needed."""
    try:
        if osm_water_source is None:
            bbox = _feature_collection_bbox(feature_collection)
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "annotation_refinement_water.geojson"
                download_osm_water_polygons(temp_path, bbox=bbox)
                return load_water_polygons(temp_path)

        if isinstance(osm_water_source, (str, Path)):
            osm_water_path = Path(osm_water_source)
            if not osm_water_path.exists():
                bbox = _feature_collection_bbox(feature_collection)
                download_osm_water_polygons(osm_water_path, bbox=bbox)
            return load_water_polygons(osm_water_path)

        return osm_water_source
    except RuntimeError as exc:  # pragma: no cover - network-dependent path
        print(f"Warning: could not obtain OSM water polygons: {exc}. Continuing without OSM polygons.")
        return []


def _feature_collection_bbox(feature_collection: FeatureCollection | None) -> tuple[float, float, float, float] | None:
    if not feature_collection or feature_collection.get("type") != "FeatureCollection":
        return None

    min_lon = math.inf
    min_lat = math.inf
    max_lon = -math.inf
    max_lat = -math.inf

    for feature in feature_collection.get("features", []):
        geometry = feature.get("geometry")
        if geometry is None:
            continue
        min_lon, min_lat, max_lon, max_lat = _expand_bbox_from_geometry(
            geometry, min_lon, min_lat, max_lon, max_lat
        )

    if min_lon == math.inf:
        return None

    return min_lon, min_lat, max_lon, max_lat


def _expand_bbox_from_geometry(
    geometry: dict[str, Any],
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[float, float, float, float]:
    geometry_type = geometry.get("type")
    if geometry_type == "GeometryCollection":
        for sub_geometry in geometry.get("geometries", []):
            min_lon, min_lat, max_lon, max_lat = _expand_bbox_from_geometry(
                sub_geometry, min_lon, min_lat, max_lon, max_lat
            )
        return min_lon, min_lat, max_lon, max_lat

    coordinates = geometry.get("coordinates")
    if coordinates is None:
        return min_lon, min_lat, max_lon, max_lat

    return _expand_bbox_from_coordinates(coordinates, min_lon, min_lat, max_lon, max_lat)


def _expand_bbox_from_coordinates(
    coordinates: Any,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> tuple[float, float, float, float]:
    if not coordinates:
        return min_lon, min_lat, max_lon, max_lat

    if isinstance(coordinates[0], (int, float)):
        lon = float(coordinates[0])
        lat = float(coordinates[1])
        return (
            min(min_lon, lon),
            min(min_lat, lat),
            max(max_lon, lon),
            max(max_lat, lat),
        )

    for coordinate in coordinates:
        min_lon, min_lat, max_lon, max_lat = _expand_bbox_from_coordinates(
            coordinate, min_lon, min_lat, max_lon, max_lat
        )

    return min_lon, min_lat, max_lon, max_lat


def match_points_in_water(
    points: list[Point],
    water_polygons: list[Polygon],
    boundary_buffer_m: float,
) -> WaterMatch | None:
    """Return a match when all points are safely inside the same water polygon."""

    for polygon_index, polygon in enumerate(water_polygons):
        if not all(_point_in_polygon(point, polygon) for point in points):
            continue

        min_distance = min(
            _distance_to_polygon_boundary_m(point, polygon)
            for point in points
        )
        if min_distance >= boundary_buffer_m:
            return WaterMatch(
                polygon_index=polygon_index,
                min_boundary_distance_m=min_distance,
            )

    return None


def _iter_geometries(geojson: dict[str, Any]) -> list[dict[str, Any]]:
    geojson_type = geojson.get("type")
    if geojson_type == "FeatureCollection":
        return [
            feature.get("geometry", {})
            for feature in geojson.get("features", [])
            if feature.get("geometry")
        ]
    if geojson_type == "Feature":
        geometry = geojson.get("geometry")
        return [geometry] if geometry else []
    if geojson_type in {"Polygon", "MultiPolygon"}:
        return [geojson]
    return []


def _parse_polygon(coordinates: Any) -> Polygon | None:
    if not coordinates:
        return None

    rings: Polygon = []
    for raw_ring in coordinates:
        ring = [(float(x), float(y)) for x, y, *_ in raw_ring]
        if len(ring) >= 4:
            rings.append(ring)

    return rings or None


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    exterior = polygon[0]
    holes = polygon[1:]
    if not _point_in_ring(point, exterior):
        return False
    return not any(_point_in_ring(point, hole) for hole in holes)


def _point_in_ring(point: Point, ring: Ring) -> bool:
    x, y = point
    inside = False
    previous_x, previous_y = ring[-1]

    for current_x, current_y in ring:
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            intersection_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y

    return inside


def _distance_to_polygon_boundary_m(point: Point, polygon: Polygon) -> float:
    return min(
        _distance_to_ring_m(point, ring)
        for ring in polygon
    )


def _distance_to_ring_m(point: Point, ring: Ring) -> float:
    return min(
        _distance_to_segment_m(point, start, end)
        for start, end in zip(ring, ring[1:] + ring[:1])
    )


def _distance_to_segment_m(point: Point, start: Point, end: Point) -> float:
    point_xy = _project_relative_m(point, point)
    start_xy = _project_relative_m(start, point)
    end_xy = _project_relative_m(end, point)

    px, py = point_xy
    sx, sy = start_xy
    ex, ey = end_xy
    dx = ex - sx
    dy = ey - sy
    segment_length_sq = dx * dx + dy * dy

    if segment_length_sq == 0:
        return math.hypot(px - sx, py - sy)

    t = ((px - sx) * dx + (py - sy) * dy) / segment_length_sq
    t = max(0.0, min(1.0, t))
    closest_x = sx + t * dx
    closest_y = sy + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _project_relative_m(point: Point, origin: Point) -> tuple[float, float]:
    lon, lat = point
    origin_lon, origin_lat = origin
    mean_lat_rad = math.radians((lat + origin_lat) / 2)
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = 111_320.0 * math.cos(mean_lat_rad)
    return (
        (lon - origin_lon) * meters_per_degree_lon,
        (lat - origin_lat) * meters_per_degree_lat,
    )
