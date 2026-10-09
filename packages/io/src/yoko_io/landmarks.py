"""Read a landmarks sidecar file (YAML)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from yoko_engine.landmarks import Landmarks


def read_landmarks(source: str | Path) -> Landmarks:
    """Read `<name>.landmarks.yaml`. `source` is a path, or YAML text if it contains a newline."""
    text = source if isinstance(source, str) and "\n" in source else Path(source).read_text()
    data: object = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("a landmarks file must be a mapping with 'version' and 'landmarks'")
    mapping = cast(dict[object, object], data)
    return Landmarks.from_mapping({str(k): v for k, v in mapping.items()})
