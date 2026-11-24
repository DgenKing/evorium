City pipeline contracts (schema version 1). Coordinates in intermediate GeoJSON and
city.json are local metres: x is easting minus origin easting; z is northing minus
origin northing; y is height above local terrain. Client arrays use [x,y,z].

layers/*.geojson: FeatureCollection with stable OSM-derived feature ids and geometry
in local metric coordinates. Properties include osm_id, osm_type, and source.

buildings.json: {schema_version, snapshot, buildings:[{id, geometry, height_m,
height_source, levels, type, roof, properties}]}. Polygon coordinates are [x,z].

props.json: {schema_version, props:[{id,type,position:[x,y,z],yaw,source}]}; deterministic
procedural props use the configured seed combined with stable feature id.

navmesh.json: {schema_version, vertices:[[x,y,z]], polygons:[[vertex_index,...]],
portals:[{a,b,from,to,cost}]}; only walkable public surfaces are included.

city.json: {schema_version, snapshot, origin_epsg, origin, attribution, buildings,
roads, props, navmesh, shuttle_street}. The manifest embeds the navmesh; rendered and
collision meshes are city.glb and city-collision.glb under the selected quality tier.
Geometry payloads are static and independent of runtime NPC/simulation data. IDs and
output ordering are stable.
