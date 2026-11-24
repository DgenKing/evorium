import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools" / "city"))

from geometry.mesh import Mesh
from facades.generate import add_facades


def shop():
    return {"id": "way/42", "type": "shop", "height_m": 6.4, "levels": 2,
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 6], [0, 6], [0, 0]]]},
            "properties": {"shop": "yes"}}


def road_east():
    return [{"geometry": {"type": "LineString", "coordinates": [[12, -4], [12, 12]]}}]


def test_shop_door_faces_nearest_source_road_and_is_deterministic():
    one, two = Mesh(), Mesh()
    result = add_facades(one, shop(), roads=road_east())
    again = add_facades(two, shop(), roads=road_east())
    assert result["door_edge"] == 1
    assert result == again
    assert one.positions == two.positions
    assert result["windows"] > 0
    assert one.groups["shopfront"]


def test_shop_without_nearby_road_gets_no_door():
    mesh = Mesh()
    result = add_facades(mesh, shop(), roads=[{"geometry": {"type": "LineString", "coordinates": [[100, 100], [120, 100]]}}])
    assert result["door_edge"] is None


def test_masonry_types_get_sills_lintels_parapet_and_seeded_chimney():
    building = shop() | {"type": "terrace", "properties": {}, "id": "way/43"}
    first, second = Mesh(), Mesh()
    result = add_facades(first, building)
    add_facades(second, building)
    assert result["details"] > result["windows"]
    assert first.positions == second.positions
    assert first.groups["facade_detail"]


def test_non_shop_never_gets_a_shop_door():
    building = shop() | {"type": "other", "properties": {}}
    mesh = Mesh()
    result = add_facades(mesh, building, roads=road_east())
    assert result["door_edge"] is None
    assert "shopfront" not in mesh.groups
