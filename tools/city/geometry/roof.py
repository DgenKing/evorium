"""Emit eaves, gables and slate from the mapped building footprint."""
import math

from .mesh import triangulate_simple_ring


def pitched_roof(mesh, ring, base, eaves, rise, wall):
    from shapely.geometry import LineString, Polygon
    from shapely.ops import split, triangulate

    polygon = Polygon(ring)
    rectangle = list(polygon.minimum_rotated_rectangle.exterior.coords)
    a,b = max(zip(rectangle, rectangle[1:]), key=lambda pair: math.dist(*pair))
    length = math.dist(a,b)
    ux, uz = (b[0]-a[0])/length, (b[1]-a[1])/length
    offset = lambda p: -uz*p[0]+ux*p[1]
    low, high = min(map(offset,ring)),max(map(offset,ring))
    mid = (low+high)/2
    cx, cz = -uz*mid, ux*mid
    ridge = LineString([(cx-1000*ux,cz-1000*uz),(cx+1000*ux,cz+1000*uz)])
    def top(p):
        return base+eaves+rise*max(0,1-abs(offset(p)-mid)/max(.01,(high-low)/2))
    for side in split(polygon,ridge).geoms:
        for triangle in triangulate(side):
            if not side.covers(triangle):
                continue
            points = list(triangle.exterior.coords)[:3]
            mesh.triangle(*[(p[0],top(p),p[1]) for p in reversed(points)],"roof")
        points = list(side.exterior.coords)
        for a,b in zip(points,points[1:]):
            if abs(offset(a)-mid) < .001 and abs(offset(b)-mid) < .001:
                continue
            if max(top(a),top(b)) > base+eaves+.005:
                mesh.quad((a[0],base+eaves,a[1]),(b[0],base+eaves,b[1]),
                          (b[0],top(b),b[1]),(a[0],top(a),a[1]),wall)


def flat_roof(mesh, ring, y, material="roof"):
    for a,b,c in triangulate_simple_ring(ring):
        mesh.triangle(*[(ring[i][0],y,ring[i][1]) for i in (a,c,b)],material)
