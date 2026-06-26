from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FeatureCollection = dict[str, Any]


def load_geojson(path: str | Path) -> FeatureCollection:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def write_geojson(feature_collection: FeatureCollection, path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(feature_collection, file, ensure_ascii=False, indent=2)
        file.write("\n")
