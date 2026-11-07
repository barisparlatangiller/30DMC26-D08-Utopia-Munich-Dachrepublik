"""
1) City-centre boundary: Munich Stadtbezirke 1–3 (OpenStreetMap admin_level 9).
2) OpenStreetMap inside the boundary + 1.6 km: walkable ways (for network distances) and existing facilities per function.

Source: Geofabrik extract of Oberbayern (OpenStreetMap, ODbL), cut and filtered with osmium. (Overpass was too slow and
unreliable for the path network of a whole city centre.)

  python pipeline/a_boundary_osm.py
Output  build/boundary.gpkg · build/walk.parquet · build/facilities.parquet · docs/data/boundary.geojson
"""
import json, subprocess

import geopandas as gpd
import requests
from shapely.geometry import shape

from config import IN, BUILD, WEB, CRS, DISTRICTS, REACH

PBF_URL = "https://download.geofabrik.de/europe/germany/bayern/oberbayern-latest.osm.pbf"
MUC_BBOX = (11.36, 48.06, 11.72, 48.25)           # Munich, generous
NO_WALK = {"motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed", "raceway", "bus_guideway", "abandoned", "platform"}


def sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def features(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    pbf = IN / "oberbayern.osm.pbf"
    if not pbf.exists():
        with requests.get(PBF_URL, stream=True, timeout=900) as r:
            r.raise_for_status()
            with open(pbf, "wb") as f:
                for ch in r.iter_content(1 << 22):
                    f.write(ch)
    print(f"Geofabrik Oberbayern: {pbf.stat().st_size / 1e6:.0f} MB", flush=True)
    muc = BUILD / "muc.osm.pbf"
    sh("osmium", "extract", "-b", ",".join(map(str, MUC_BBOX)), "-s", "smart", "--overwrite", "-o", muc, pbf)

    # ---- boundary: the three Stadtbezirke
    sh("osmium", "tags-filter", "--overwrite", "-o", BUILD / "adm.osm.pbf", muc, "r/boundary=administrative")
    sh("osmium", "export", "--overwrite", "-f", "geojsonseq", "-o", BUILD / "adm.geojsonseq", BUILD / "adm.osm.pbf", "--geometry-types=polygon")
    adm = [f for f in features(BUILD / "adm.geojsonseq")
           if f["properties"].get("admin_level") == "9" and f["properties"].get("name") in DISTRICTS]
    names = [f["properties"]["name"] for f in adm]
    print("districts:", names)
    if sorted(set(names)) != sorted(DISTRICTS):
        raise SystemExit(f"expected {DISTRICTS}, got {names}")
    b = gpd.GeoDataFrame({"name": names}, geometry=[shape(f["geometry"]) for f in adm], crs=4326).to_crs(CRS)
    b = b.dissolve("name").reset_index()
    b["geometry"] = b.buffer(0)
    b.to_file(BUILD / "boundary.gpkg", driver="GPKG")
    u = b.union_all()
    print(f"area {u.area / 1e6:.2f} km²")
    gpd.GeoDataFrame(geometry=[u], crs=CRS).to_crs(4326).to_file(WEB / "boundary.geojson", driver="GeoJSON")
    b.to_crs(4326).to_file(WEB / "districts.geojson", driver="GeoJSON")

    # ---- cut to the centre + reach
    w, s, e, n = gpd.GeoSeries([u.buffer(REACH + 100)], crs=CRS).to_crs(4326).total_bounds
    cen = BUILD / "centre.osm.pbf"
    sh("osmium", "extract", "-b", f"{w},{s},{e},{n}", "-s", "smart", "--overwrite", "-o", cen, muc)

    # ---- walkable ways
    sh("osmium", "tags-filter", "--overwrite", "-o", BUILD / "hw.osm.pbf", cen, "w/highway")
    sh("osmium", "export", "--overwrite", "-f", "geojsonseq", "-o", BUILD / "hw.geojsonseq", BUILD / "hw.osm.pbf", "--geometry-types=linestring")
    ways = []
    for f in features(BUILD / "hw.geojsonseq"):
        p = f["properties"]
        if p.get("highway") in NO_WALK or p.get("foot") in ("no", "private"):
            continue
        if p.get("access") in ("no", "private") and p.get("foot") not in ("yes", "designated", "permissive"):
            continue
        ways.append({"hw": p.get("highway"), "geometry": shape(f["geometry"])})
    gw = gpd.GeoDataFrame(ways, crs=4326).to_crs(CRS)
    gw.to_parquet(BUILD / "walk.parquet")
    print(f"walk ways: {len(gw):,}, {gw.length.sum() / 1000:.0f} km")

    # ---- existing facilities, one point per feature
    sh("osmium", "tags-filter", "--overwrite", "-o", BUILD / "fac.osm.pbf", cen,
       "nwr/leisure=playground,pitch,fitness_station,sports_centre,park,garden", "nwr/landuse=allotments",
       "nwr/amenity=cinema,community_centre,social_centre,library", "nwr/garden:type=community")
    sh("osmium", "export", "--overwrite", "-f", "geojsonseq", "-o", BUILD / "fac.geojsonseq", BUILD / "fac.osm.pbf")
    rows = []
    for f in features(BUILD / "fac.geojsonseq"):
        p = f["properties"]; g = shape(f["geometry"])
        pt = g if g.geom_type == "Point" else g.representative_point() if g.geom_type in ("Polygon", "MultiPolygon") else g.interpolate(0.5, normalized=True)
        le, am, lu, gt = p.get("leisure"), p.get("amenity"), p.get("landuse"), p.get("garden:type")
        fn = ("play" if le == "playground" else
              "sport" if le in ("pitch", "fitness_station") or (le == "sports_centre" and p.get("access") != "private") else
              "garden" if lu == "allotments" or gt == "community" else
              "park" if le == "park" else
              "cinema" if am == "cinema" else
              "social" if am in ("community_centre", "social_centre") else
              "quiet" if am == "library" else None)
        if fn:
            rows.append({"fn": fn, "name": p.get("name"), "geometry": pt})
    fac = gpd.GeoDataFrame(rows, crs=4326).to_crs(CRS)
    fac.to_parquet(BUILD / "facilities.parquet")
    fac.to_crs(4326).to_file(WEB / "facilities.geojson", driver="GeoJSON")
    print(fac.fn.value_counts().to_dict())


if __name__ == "__main__":
    main()
