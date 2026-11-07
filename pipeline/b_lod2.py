"""
Bayern LoD2 (CityGML, 2 km tiles, CC BY 4.0) → every building part in the city centre with its roof faces sorted into
  flat_m2   roof faces with slope < 10° (planar area) → candidates for the 7 public uses (or PV)
  pvp_m2    pitched faces 10–60° facing east, south or west (true area) → PV
Tiles: https://download1.bayernwolke.de/a/lod2/citygml/{E}_{N}.gml (E, N = lower-left corner in km, EPSG:25832)

  python pipeline/b_lod2.py
Output  build/buildings.parquet
"""
import math, time

import geopandas as gpd
import numpy as np
import requests
import shapely

from config import IN, BUILD, CRS, FLAT_MAX_SLOPE, PV_SLOPE, PV_AZIMUTH
from lod2lib import parse

URL = "https://download{k}.bayernwolke.de/a/lod2/citygml/{e}_{n}.gml"


def tiles(bounds):
    x0, y0, x1, y1 = bounds
    for e in range(int(x0 // 2000) * 2, int(x1 // 2000) * 2 + 1, 2):
        for n in range(int(y0 // 2000) * 2, int(y1 // 2000) * 2 + 1, 2):
            yield e, n


def fetch(e, n):
    f = IN / "lod2" / f"{e}_{n}.gml"
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists() and f.stat().st_size > 1000:
        return f
    for k in (1, 2, 1, 2):
        try:
            r = requests.get(URL.format(k=k, e=e, n=n), timeout=600)
            if r.status_code == 200 and len(r.content) > 1000:
                f.write_bytes(r.content); return f
            print(f"  {e}_{n}: HTTP {r.status_code}")
        except Exception as ex:                                            # noqa: BLE001
            print(f"  {e}_{n}: {ex}")
        time.sleep(5)
    return None


def main():
    b = gpd.read_file(BUILD / "boundary.gpkg").to_crs(CRS)
    u = b.union_all()
    rows, roofs = [], []
    for e, n in tiles(u.bounds):
        if not shapely.box(e * 1000, n * 1000, e * 1000 + 2000, n * 1000 + 2000).intersects(u):
            continue
        f = fetch(e, n)
        if f is None:
            raise SystemExit(f"tile {e}_{n} missing")
        with open(f, "rb") as s:
            r, rf = parse(s, f.stem)
        rows += r; roofs += rf
        print(f"  {f.name}: {len(r):,} parts, {len(rf):,} roof faces ({f.stat().st_size / 1e6:.0f} MB)", flush=True)
    g = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS)
    g = g[g.geometry.notna() & ~g.geometry.is_empty & (g.area > 2)]
    g = g[g.representative_point().within(u)].copy()
    rf = gpd.GeoDataFrame(roofs, geometry="geometry", crs=CRS)
    rf = rf[rf.uid.isin(g.uid)].copy()
    # slope and the direction the face looks to (downhill), 0° = north, clockwise
    grad = np.hypot(rf.a, rf.b)
    rf["slope"] = np.degrees(np.arctan(grad))
    rf["aspect"] = (np.degrees(np.arctan2(-rf.a, -rf.b)) + 360) % 360
    rf["area2d"] = rf.area
    rf["area3d"] = rf.area2d / np.cos(np.radians(rf.slope.clip(upper=80)))
    flat = rf.slope < FLAT_MAX_SLOPE
    pvp = (rf.slope >= PV_SLOPE[0]) & (rf.slope <= PV_SLOPE[1]) & (rf.aspect >= PV_AZIMUTH[0]) & (rf.aspect <= PV_AZIMUTH[1])
    agg = rf.assign(flat=np.where(flat, rf.area2d, 0), pvp=np.where(pvp, rf.area3d, 0)).groupby("uid")[["flat", "pvp", "area3d"]].sum()
    g = g.join(agg, on="uid").fillna({"flat": 0, "pvp": 0, "area3d": 0})
    g = g.rename(columns={"flat": "flat_m2", "pvp": "pvp_m2", "area3d": "roof_m2"})
    g["h"] = g.h.fillna((g.ztop - g.z0).clip(lower=3)).fillna(10).clip(2, 120)
    g = g.reset_index(drop=True); g["bid"] = np.arange(len(g))
    g.to_parquet(BUILD / "buildings.parquet")
    print(f"building parts in the centre: {len(g):,} · roof {g.roof_m2.sum() / 1e6:.2f} km² · flat {g.flat_m2.sum() / 1e6:.2f} km² · "
          f"pitched PV-facing {g.pvp_m2.sum() / 1e6:.2f} km²")
    print(g.fn.value_counts().head(10))


if __name__ == "__main__":
    main()
