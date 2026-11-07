"""
Walking distances on the OpenStreetMap path network (not straight lines):
  base   for every 100 m cell in the centre and each function: distance to the nearest existing facility
  pairs  for every candidate roof and every cell within 1,500 m: the walking distance between them
The simulator in the browser uses these to place roofs and to count, without double counting, who gains access.

  python pipeline/d_network.py
Output  docs/data/sim.json · docs/data/pairs.bin (uint16 roof, uint16 cell, uint8 distance/10 m, sorted by roof)
"""
import json, time

import geopandas as gpd
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from config import BUILD, WEB, CRS, FUNCTIONS, PARAMS, REACH, FLAT_MAX_SLOPE, PV_SLOPE, PV_AZIMUTH

MIN_FLAT = min(f["min_m2"] for f in FUNCTIONS)          # smallest roof any function can use (net m²)


def graph(ways):
    xy = []
    for g in ways.geometry:
        c = np.asarray(g.coords)[:, :2]
        xy.append(c)
    allp = np.round(np.vstack(xy), 1)
    uniq, inv = np.unique(allp, axis=0, return_inverse=True)
    inv = inv.ravel()
    a, b, w = [], [], []
    k = 0
    for c in xy:
        idx = inv[k:k + len(c)]; k += len(c)
        d = np.hypot(*np.diff(c, axis=0).T)
        a.append(idx[:-1]); b.append(idx[1:]); w.append(d)
    a, b, w = np.concatenate(a), np.concatenate(b), np.concatenate(w)
    keep = a != b
    n = len(uniq)
    G = coo_matrix((np.r_[w[keep], w[keep]], (np.r_[a[keep], b[keep]], np.r_[b[keep], a[keep]])), shape=(n, n)).tocsr()
    return G, uniq


def main():
    t0 = time.time()
    ways = gpd.read_parquet(BUILD / "walk.parquet").to_crs(CRS)
    G, nodes = graph(ways)
    tree = cKDTree(nodes)
    print(f"network: {len(nodes):,} nodes, {G.nnz // 2:,} edges", flush=True)

    cells = gpd.read_parquet(BUILD / "cells.parquet")
    cells = cells[cells.inside].reset_index(drop=True)
    cxy = np.c_[cells.centroid.x, cells.centroid.y]
    cd, cn = tree.query(cxy)

    # baseline: walking distance from each cell to the nearest existing facility of each function
    fac = gpd.read_parquet(BUILD / "facilities.parquet")
    base = {}
    for f in FUNCTIONS:
        if f["id"] == "pv":
            continue
        ff = fac[fac.fn == f["id"]]
        if not len(ff):
            base[f["id"]] = np.full(len(cells), 255, dtype=int); continue
        fd, fnode = tree.query(np.c_[ff.geometry.x, ff.geometry.y])
        ok = fd < 150
        dist = dijkstra(G, directed=False, indices=np.unique(fnode[ok]), limit=2550, min_only=True)
        d = dist[cn] + cd
        base[f["id"]] = np.where(np.isfinite(d), np.clip(np.round(d / 10), 0, 254), 255).astype(int)
        print(f"  baseline {f['id']}: {len(ff)} facilities, cells within target {np.mean(base[f['id']] * 10 <= f['target']):.0%}", flush=True)

    # candidate roofs: flat roof area (net) big enough for the smallest function
    b = gpd.read_parquet(BUILD / "buildings.parquet")
    b["net"] = b.flat_m2 * PARAMS["usable_net"]
    cand = b[b.net >= MIN_FLAT].reset_index(drop=True)
    pxy = np.c_[cand.representative_point().x, cand.representative_point().y]
    pd_, pn = tree.query(pxy)
    print(f"candidate roofs: {len(cand):,} (net flat ≥ {MIN_FLAT} m²) of {len(b):,} building parts", flush=True)

    # cell → all candidates within REACH, in chunks of sources
    node2cand = {}
    for i, n in enumerate(pn):
        node2cand.setdefault(int(n), []).append(i)
    cand_nodes = np.array(sorted(node2cand))
    R, C, D = [], [], []
    uniq_cn, inv_cn = np.unique(cn, return_inverse=True)
    for s in range(0, len(uniq_cn), 200):
        src = uniq_cn[s:s + 200]
        dist = dijkstra(G, directed=False, indices=src, limit=REACH)
        sub = dist[:, cand_nodes]
        for row, node in enumerate(src):
            hit = np.isfinite(sub[row])
            if not hit.any():
                continue
            for ci in np.where(inv_cn == s + row)[0]:
                for nd, dd in zip(cand_nodes[hit], sub[row][hit]):
                    for k in node2cand[int(nd)]:
                        tot = dd + cd[ci] + pd_[k]
                        if tot <= REACH:
                            R.append(k); C.append(ci); D.append(int(round(tot / 10)))
        print(f"  sources {min(s + 200, len(uniq_cn))}/{len(uniq_cn)} · pairs {len(R):,}", flush=True)
    R, C, D = np.array(R, dtype=np.uint16), np.array(C, dtype=np.uint16), np.array(D, dtype=np.uint8)
    o = np.lexsort((C, R))
    buf = np.empty(len(R) * 5, dtype=np.uint8)
    rec = np.zeros(len(R), dtype=[("r", "<u2"), ("c", "<u2"), ("d", "u1")])
    rec["r"], rec["c"], rec["d"] = R[o], C[o], D[o]
    (WEB / "pairs.bin").write_bytes(rec.tobytes())
    start = np.searchsorted(rec["r"], np.arange(len(cand) + 1)).tolist()

    all_pv = float((b.pvp_m2).sum())
    sim = {
        "functions": [{k: v for k, v in f.items() if k != "osm"} for f in FUNCTIONS],
        "params": PARAMS, "flat_max_slope": FLAT_MAX_SLOPE, "pv_slope": PV_SLOPE, "pv_azimuth": PV_AZIMUTH,
        "cells": {"pop": cells["pop"].round().astype(int).tolist(), "kids": cells.kids.fillna(0).round().astype(int).tolist(),
                  "base": {k: v.tolist() for k, v in base.items()},
                  "x": np.round(cells.centroid.to_crs(4326).x, 5).tolist(), "y": np.round(cells.centroid.to_crs(4326).y, 5).tolist()},
        "roofs": {"bid": cand.bid.astype(int).tolist(), "net": cand.net.round().astype(int).tolist(),
                  "pvp": cand.pvp_m2.round().astype(int).tolist(), "start": start},
        "totals": {"parts": int(len(b)), "roof_m2": round(float(b.roof_m2.sum())), "flat_m2": round(float(b.flat_m2.sum())),
                   "net_flat_candidates_m2": round(float(cand.net.sum())), "candidates": int(len(cand)),
                   "pitched_pv_m2": round(all_pv), "residents": int(cells["pop"].sum()), "kids": int(cells.kids.fillna(0).sum()),
                   "cells": int(len(cells)), "pairs": int(len(rec))},
    }
    (WEB / "sim.json").write_text(json.dumps(sim, separators=(",", ":")))
    print(json.dumps(sim["totals"], indent=1), f"\n{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
