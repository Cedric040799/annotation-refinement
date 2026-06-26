from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Point = tuple[float, float]
Ring = list[Point]
Polygon = list[Ring]


@dataclass(frozen=True)
class WaterMatch:
    polygon_index: int
    min_boundary_distance_m: float


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
