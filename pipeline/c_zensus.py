"""
Zensus 2022, 100 m grid (Destatis, open data): residents and residents under 15 for every cell in the city centre.
Children = "unter 3" + "3 bis 5" + "6 bis 14" from the infrastructural age groups (the Excel's 0–12 is not published on
the grid; under 15 is the closest). Cells with suppressed values ("–") count as 0.

  python pipeline/c_zensus.py
Output  build/cells.parquet (EPSG:25832, 100 m squares) · docs/data/cells.geojson
"""
import io, re, zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

from config import IN, BUILD, WEB, CRS, REACH

BASE = "https://www.destatis.de/static/DE/zensus/gitterdaten/"
FILES = {"pop": "Zensus2022_Bevoelkerungszahl.zip", "age": "Alter_in_infrastrukturellen_Altersgruppen.zip"}


def table(key, bbox3035):
    f = IN / FILES[key]
    if not f.exists():
        r = requests.get(BASE + FILES[key], timeout=900, headers={"User-Agent": "Mozilla/5.0 30DMC26"})
        r.raise_for_status(); f.write_bytes(r.content)
    z = zipfile.ZipFile(f)
    name = next(n for n in z.namelist() if "100m" in n.lower() and n.lower().endswith(".csv"))
    print(f"{key}: {name}", flush=True)
    x0, y0, x1, y1 = bbox3035
    parts = []
    with z.open(name) as fh:
        for ch in pd.read_csv(fh, sep=";", decimal=",", chunksize=500_000, encoding="latin-1", dtype=str):
            ch.columns = [c.strip() for c in ch.columns]
            xs, ys = pd.to_numeric(ch["x_mp_100m"]), pd.to_numeric(ch["y_mp_100m"])
            m = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
            if m.any():
                parts.append(ch[m])
    t = pd.concat(parts)
    print("  columns:", list(t.columns))
    for c in t.columns:
        if c not in ("GITTER_ID_100m", "x_mp_100m", "y_mp_100m"):
            t[c] = pd.to_numeric(t[c].str.replace("–", "").str.replace(",", ".").str.strip(), errors="coerce")
    t["x"] = pd.to_numeric(t.x_mp_100m); t["y"] = pd.to_numeric(t.y_mp_100m)
    return t


def main():
    u = gpd.read_file(BUILD / "boundary.gpkg").to_crs(CRS).union_all()
    reach = gpd.GeoSeries([u.buffer(REACH + 200)], crs=CRS)
    bbox = reach.to_crs(3035).total_bounds
    pop = table("pop", bbox)
    pcol = next(c for c in pop.columns if c.lower() in ("einwohner", "bevoelkerungszahl", "insgesamt_bevoelkerung") or "einwohner" in c.lower())
    age = table("age", bbox)
    kid_cols = [c for c in age.columns if re.search(r"unter.?3|^3.{0,8}5$|3_bis_5|6.{0,8}14|6_bis_14", c, re.I)]
    print("  child columns:", kid_cols)
    c = pop[["x", "y", pcol]].rename(columns={pcol: "pop"}).merge(age[["x", "y"] + kid_cols], on=["x", "y"], how="left")
    c["kids"] = c[kid_cols].fillna(0).sum(axis=1) if kid_cols else np.nan
    c["pop"] = c["pop"].fillna(0)
    c = c[c["pop"] > 0]
    g = gpd.GeoDataFrame(c[["pop", "kids"]], geometry=[shapely.box(x - 50, y - 50, x + 50, y + 50) for x, y in zip(c.x, c.y)], crs=3035).to_crs(CRS)
    g["inside"] = g.centroid.within(u)
    g = g[g.centroid.within(reach.iloc[0])].reset_index(drop=True)
    g["cid"] = np.arange(len(g))
    g.to_parquet(BUILD / "cells.parquet")
    ins = g[g.inside]
    print(f"cells: {len(g):,} in reach, {len(ins):,} in the centre · residents in the centre {ins['pop'].sum():,.0f} · "
          f"under 15 {ins.kids.sum():,.0f}")


if __name__ == "__main__":
    main()
