"""
Web layers: every building part of the centre as vector tiles (3D extrusion, coloured live by the simulator through
feature-state on "bid"), and the 100 m cells for the need / result maps.

  python pipeline/e_web.py
Output  docs/data/buildings.pmtiles (layer "b": bid, h, c = candidate index or -1, p = pitched PV-facing m²)
        docs/data/cells.geojson (i = cell index used by sim.json) · stats in docs/data/stats.json
"""
import json, subprocess, tempfile, time
from pathlib import Path

import geopandas as gpd
import numpy as np

from config import BUILD, WEB, PARAMS, FUNCTIONS

b = gpd.read_parquet(BUILD / "buildings.parquet")
sim = json.loads((WEB / "sim.json").read_text())
cidx = {bid: i for i, bid in enumerate(sim["roofs"]["bid"])}
b["c"] = b.bid.map(cidx).fillna(-1).astype(int)
b4 = b.to_crs(4326)
with tempfile.TemporaryDirectory() as td:
    seq = Path(td) / "b.geojsonl"
    with open(seq, "w") as f:
        for r in b4.itertuples():
            p = {"bid": int(r.bid), "h": round(float(r.h), 1), "c": int(r.c), "p": int(round(r.pvp_m2)), "fl": int(round(r.flat_m2))}
            f.write(json.dumps({"type": "Feature", "properties": p, "geometry": r.geometry.__geo_interface__}, separators=(",", ":")) + "\n")
    subprocess.run(["tippecanoe", "-o", str(WEB / "buildings.pmtiles"), "--force", "-l", "b", "-Z", "12", "-z", "16",
                    "--no-feature-limit", "--no-tile-size-limit", "--no-tiny-polygon-reduction", "--simplification=2",
                    "-q", str(seq)], check=True)

cells = gpd.read_parquet(BUILD / "cells.parquet")
cells = cells[cells.inside].reset_index(drop=True)
cells["i"] = np.arange(len(cells))
cells[["i", "pop", "kids", "geometry"]].to_crs(4326).to_file(WEB / "cells.geojson", driver="GeoJSON")

st = {"build": int(time.time()), "totals": sim["totals"],
      "sources": {"lod2": "Bayerische Vermessungsverwaltung, 3D-Gebäudemodelle LoD2, CC BY 4.0",
                  "zensus": "Statistisches Bundesamt (Destatis), Zensus 2022, 100 m grid",
                  "osm": "OpenStreetMap contributors, ODbL"}}
(WEB / "stats.json").write_text(json.dumps(st, indent=1))
print(json.dumps(st, indent=1))
