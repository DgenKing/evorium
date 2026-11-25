"""Account-scoped 3D checkpoints. The scene checks physical clearance on restore."""
import json
from functools import lru_cache
from math import pi, remainder
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from evorium import accounts
from evorium.db import connect

MapName = Literal['city', 'kit']
Coordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]


@lru_cache(maxsize=1)
def city_bounds():
    path = Path(__file__).with_name('static') / 'world3d/data/city.json'
    return json.loads(path.read_text())['bounds']


class Position(BaseModel):
    model_config = ConfigDict(extra='forbid')

    map: MapName
    x: Coordinate
    y: Coordinate
    z: Coordinate
    yaw: Coordinate

    @model_validator(mode='after')
    def inside_map(self):
        bounds = city_bounds() if self.map == 'city' else {'min': [-12, -9.6], 'max': [11, 5.5]}
        west, north = bounds['min']
        east, south = bounds['max']
        if not (west <= self.x <= east and north <= self.z <= south and -12 <= self.y <= 3):
            raise ValueError('Position is outside the playable map')
        self.yaw = remainder(self.yaw, 2 * pi)
        return self


def load(map_name, db_path):
    with connect(db_path) as c:
        row = c.execute(
            'SELECT map, x, y, z, yaw FROM player_positions WHERE account=? AND map=?',
            (accounts.current.get(), map_name),
        ).fetchone()
    try:
        return Position.model_validate(dict(row)) if row else None
    except ValidationError:
        return None


def save(position, db_path):
    with connect(db_path) as c:
        c.execute(
            """INSERT INTO player_positions (account, map, x, y, z, yaw)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (account, map) DO UPDATE
               SET x=excluded.x, y=excluded.y, z=excluded.z, yaw=excluded.yaw""",
            (accounts.current.get(), position.map, position.x, position.y, position.z, position.yaw),
        )
