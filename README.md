# Die Dachrepublik: what if Munich's roofs belonged to everyone?

**#30DayMapChallenge 2026 · Day 8 · Utopia · Munich**
Live: https://barisparlatangiller.github.io/30DMC26-D08-Utopia-Munich-Dachrepublik/

This is a 3D simulator for Munich's city centre (Stadtbezirke 1–3). Its flat roofs can be shared among seven free public uses and solar PV:

* playground
* sport and fitness
* community garden
* mini park
* open-air cinema
* social terrace
* quiet reading and rest
* solar PV

Each use goes where people within walking distance lack it, and placement stops once that need is met. Roofs nobody needs stay free.
You can change the eight shares and every assumption on the page.

The model follows the author's Excel (`data/Dachrepublik_Muenchen_8_Function_Simulator.xlsx`). The demo inputs (1,000,000 m², 100,000 residents) are replaced by measured roofs and Census residents.

## Pipeline (GitHub Actions)
| Step | Script | Data |
|---|---|---|
| Boundary, path network, existing facilities | `a_boundary_osm.py` | OpenStreetMap (ODbL), Geofabrik Oberbayern extract cut with osmium: Stadtbezirke 1–3, walkable ways, playgrounds, pitches, parks, gardens, cinemas, community centres, libraries |
| Roofs | `b_lod2.py` | Bayern LoD2 CityGML, 2 km tiles (CC BY 4.0): roof faces by slope and orientation |
| People | `c_zensus.py` | Zensus 2022, 100 m grid (Destatis): residents, children 0–15 |
| Walking distances | `d_network.py` | Distances on the path network from every cell to existing facilities and to every candidate roof (≤ 1.5 km) |
| Web layers | `e_web.py` | Buildings as vector tiles for 3D, grid cells |

## Rules
* **Flat roof faces (< 10°):** the seven public uses or PV. 75 % of the flat area counts as usable.
* **Pitched faces (10–60°) facing east, south or west:** PV only. This can be switched off on the page.
* **Number of new sites per use:** limited by the open gap (residents ÷ people per site × (1 − share already covered)) and by the use's share of the roof area.
* **Choosing roofs:** the next site goes to the roof that gives the most people new walking access within the target distance (lazy greedy). Placement stops when the gap is closed or nothing more is gained.
* **PV:** roofs are filled only until the kWh-per-resident target is met.
* **Counting:** "People gaining access" counts each resident once, however many new uses they gain.

## Limits
These are theoretical candidates, not building permits. Structure, fire safety, ownership and access are not checked. Yields and PV factors are the Excel's assumptions: GartenLeistungen 5.45 kg/m², and 0.65 × 0.2 kWp/m² × 950 kWh/kWp. OSM facilities are as mapped.

Barış Parlatangiller · built with Claude
