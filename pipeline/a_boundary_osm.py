"""
1) City-centre boundary: Munich Stadtbezirke 1–3 (OpenStreetMap admin_level 9).
2) OpenStreetMap inside the boundary + 1.6 km: walkable ways (for network distances) and existing facilities per function.

  python pipeline/a_boundary_osm.py
Output  build/boundary.gpkg · build/walk.parquet · build/facilities.parquet · docs/data/boundary.geojson
"""
import json, time

import geopandas as gpd
import pandas as pd
import requests
import shapely
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import polygonize, unary_union

from config import IN, BUILD, WEB, CRS, DISTRICTS, FUNCTIONS, REACH

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def overpass(q):
    """Overpass with retries; answers are cached in input/osm/ (kept between runs by the Actions cache)"""
    import hashlib
    cf = IN / "osm" / (hashlib.sha1(q.encode()).hexdigest()[:16] + ".json")
    if cf.exists():
        return json.loads(cf.read_text())
    cf.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(9):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": q}, timeout=360, headers={"User-Agent": "30DMC26-Dachrepublik/1.0"})
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                cf.write_text(r.text); return r.json()
            last = f"{url} → HTTP {r.status_code}"
        except Exception as e:                                             # noqa: BLE001
            last = f"{url} → {e}"
        print("overpass retry:", last, flush=True); time.sleep(15)
    raise SystemExit(f"Overpass failed: {last}")


def boundary():
    names = "|".join(DISTRICTS)
    q = f'[out:json][timeout:180];area["name"="München"]["admin_level"="6"]->.m;' \
        f'rel(area.m)["boundary"="administrative"]["admin_level"="9"]["name"~"^({names})$"];out geom;'
    d = overpass(q)
    polys, names_found = [], []
    for el in d["elements"]:
        lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in el.get("members", [])
                 if m.get("role") == "outer" and m.get("geometry")]
        ps = list(polygonize(unary_union(lines)))
        if ps:
            polys.append(unary_union(ps)); names_found.append(el["tags"].get("name"))
    print("districts:", names_found)
    if len(polys) != len(DISTRICTS):
        raise SystemExit(f"expected {len(DISTRICTS)} districts, got {names_found}")
    g = gpd.GeoDataFrame({"name": names_found}, geometry=polys, crs=4326).to_crs(CRS)
    g["geometry"] = g.buffer(0)
    return g


def main():
    b = boundary()
    b.to_file(BUILD / "boundary.gpkg", driver="GPKG")
    u = b.union_all()
    print(f"area {u.area / 1e6:.2f} km²")
    gpd.GeoDataFrame(geometry=[u], crs=CRS).to_crs(4326).to_file(WEB / "boundary.geojson", driver="GeoJSON")
    b.to_crs(4326).to_file(WEB / "districts.geojson", driver="GeoJSON")

    w, s, e, n = gpd.GeoSeries([u.buffer(REACH + 100)], crs=CRS).to_crs(4326).total_bounds
    bb = f"{s},{w},{n},{e}"
    # walkable network
    q = f'[out:json][timeout:300];way["highway"]["highway"!~"^(motorway|motorway_link|trunk|trunk_link|construction|proposed|raceway|bus_guideway)$"]' \
        f'["foot"!~"^(no|private)$"]["access"!~"^(no|private)$"]({bb});out geom;'
    d = overpass(q)
    ways = [{"id": el["id"], "hw": el["tags"].get("highway"), "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]])}
            for el in d["elements"] if el.get("geometry") and len(el["geometry"]) > 1]
    gw = gpd.GeoDataFrame(ways, crs=4326).to_crs(CRS)
    gw.to_parquet(BUILD / "walk.parquet")
    print(f"walk ways: {len(gw):,}, {gw.length.sum() / 1000:.0f} km")
    # existing facilities, one point per feature (polygon → representative point)
    rows = []
    for f in FUNCTIONS:
        if not f["osm"]:
            continue
        q = "[out:json][timeout:300];(" + "".join(f"{s_}({bb});" for s_ in f["osm"]) + ");out geom;"
        d = overpass(q)
        for el in d["elements"]:
            if el["type"] == "node":
                g = Point(el["lon"], el["lat"])
            elif el.get("geometry"):
                pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
                g = Polygon(pts).representative_point() if len(pts) >= 4 and pts[0] == pts[-1] else LineString(pts).interpolate(0.5, normalized=True)
            elif el.get("members"):
                pts = [(p["lon"], p["lat"]) for m in el["members"] for p in m.get("geometry", [])]
                if not pts:
                    continue
                g = shapely.MultiPoint(pts).centroid
            else:
                continue
            rows.append({"fn": f["id"], "osm": f'{el["type"]}/{el["id"]}', "name": el.get("tags", {}).get("name"), "geometry": g})
        print(f"  {f['id']}: {sum(r['fn'] == f['id'] for r in rows)} existing", flush=True)
        time.sleep(3)
    fac = gpd.GeoDataFrame(rows, crs=4326).to_crs(CRS)
    fac.to_parquet(BUILD / "facilities.parquet")
    fac.to_crs(4326).to_file(WEB / "facilities.geojson", driver="GeoJSON")


if __name__ == "__main__":
    main()
