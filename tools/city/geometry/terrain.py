"""Sample the 1 m DTM in local city coordinates, pinned to the kit street level."""
import math


class Terrain:
    def __init__(self, path, origin, anchor):
        import rasterio

        self.origin = origin
        with rasterio.open(path) as ds:
            if ds.crs.to_epsg() != 27700:
                raise ValueError("City DTM must use the British National Grid")
            self.data = ds.read(1, masked=True)
            self.transform = ~ds.transform
        self.zero = self._absolute(*anchor)
        if self.zero is None:
            raise ValueError("City DTM has no sample at the Shuttle Street anchor")
        self.anchor = tuple(anchor)

    def _absolute(self, x, z):
        col, row = self.transform * (x + self.origin[0], z + self.origin[1])
        col, row = col - .5, row - .5
        c, r = math.floor(col), math.floor(row)
        if r < 0 or c < 0 or r+1 >= self.data.shape[0] or c+1 >= self.data.shape[1]:
            return None
        samples = self.data[r:r+2, c:c+2]
        if samples.mask.any():
            return None
        u, v = col-c, row-r
        return float((1-v)*((1-u)*samples[0,0]+u*samples[0,1]) +
                     v*((1-u)*samples[1,0]+u*samples[1,1]))

    def __call__(self, x, z):
        level = self._absolute(x,z)
        if level is None:
            return 0.0
        # Match the existing flat kit block, then blend into surveyed ground.
        distance = math.dist((x,z), self.anchor)
        blend = max(0.0,min(1.0,(distance-20)/24))
        return round((level-self.zero)*blend, 3)


def terrain_for(config, root, fixture=False):
    path = root / config.get("inputs", {}).get("lidar_dtm", "tools/city/raw/lidar_dtm.tif")
    if not fixture and path.is_file():
        return Terrain(path, config["area"]["origin"], config.get("shuttle_street",{}).get("position",[0,0]))
    return None
