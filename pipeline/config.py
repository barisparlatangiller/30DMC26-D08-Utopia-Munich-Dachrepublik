"""Shared settings for Die Dachrepublik (Day 8). Defaults follow the user's Excel (data/Dachrepublik_…xlsx)."""
from pathlib import Path

IN, BUILD, WEB = Path("input"), Path("build"), Path("docs/data")
for p in (IN, BUILD, WEB):
    p.mkdir(parents=True, exist_ok=True)

# Munich city centre = Stadtbezirke 1–3
DISTRICTS = ["Altstadt-Lehel", "Ludwigsvorstadt-Isarvorstadt", "Maxvorstadt"]
CRS = 25832
REACH = 1500            # longest walking distance any function needs (open-air cinema max, m)

FLAT_MAX_SLOPE = 10     # degrees: flat roof faces → the 7 public uses (and PV if chosen)
PV_SLOPE = (10, 60)     # pitched faces usable for PV
PV_AZIMUTH = (90, 270)  # east … south … west (0 = north)

# The 8 functions. share = Excel default %, min_m2 = minimum area per facility, target/max walking distance (m),
# per = people one facility should serve, have = share of need already met (Excel "Mevcut karşılama"), osm = what counts as
# an existing facility (baseline, from OpenStreetMap)
FUNCTIONS = [
    {"id": "play",   "name": "Children's playground",      "share": 15, "min_m2": 350, "target": 300, "max": 700,  "per": 250,  "have": 45, "group": "kids",
     "osm": ['nwr["leisure"="playground"]']},
    {"id": "sport",  "name": "Sport & fitness",            "share": 12, "min_m2": 400, "target": 500, "max": 1000, "per": 1500, "have": 40, "group": "all",
     "osm": ['nwr["leisure"="pitch"]', 'nwr["leisure"="fitness_station"]', 'nwr["leisure"="sports_centre"]["access"!="private"]']},
    {"id": "garden", "name": "Free community garden",      "share": 20, "min_m2": 500, "target": 300, "max": 800,  "per": 1000, "have": 10, "group": "all",
     "osm": ['nwr["landuse"="allotments"]', 'nwr["leisure"="garden"]["garden:type"="community"]', 'nwr["garden:type"="community"]']},
    {"id": "park",   "name": "Mini park / green terrace",  "share": 15, "min_m2": 500, "target": 300, "max": 700,  "per": 1200, "have": 35, "group": "all",
     "osm": ['nwr["leisure"="park"]']},
    {"id": "cinema", "name": "Open-air cinema",            "share": 7,  "min_m2": 350, "target": 800, "max": 1500, "per": 5000, "have": 20, "group": "all",
     "osm": ['nwr["amenity"="cinema"]']},
    {"id": "social", "name": "Social meeting terrace",     "share": 10, "min_m2": 250, "target": 300, "max": 700,  "per": 1000, "have": 30, "group": "all",
     "osm": ['nwr["amenity"="community_centre"]', 'nwr["amenity"="social_centre"]']},
    {"id": "quiet",  "name": "Quiet reading & rest",       "share": 8,  "min_m2": 150, "target": 300, "max": 700,  "per": 1000, "have": 25, "group": "all",
     "osm": ['nwr["amenity"="library"]']},
    {"id": "pv",     "name": "Solar PV",                   "share": 13, "min_m2": 100, "target": 0,   "max": 0,    "per": 0,    "have": 0,  "group": None,
     "osm": []},
]

PARAMS = {  # Excel 02_SENARYO / 03_STANDARTLAR
    "usable_net": 0.75,          # net usable share of a flat roof (parapets, plant, access)
    "veg_need_kg": 168,          # vegetables & fruit, kg per person per year
    "grow_share": 0.55,          # share of a garden roof actually planted
    "yield_kg_m2": 5.45,         # kg per m² planted per season (GartenLeistungen)
    "pv_fill": 0.65,             # panel cover of a PV roof
    "kwp_m2": 0.2,               # kWp per m² of panel
    "kwh_kwp": 950,              # kWh per kWp per year (Fraunhofer ISE order of magnitude)
    "pv_target_kwh": 500,        # PV contribution target, kWh per resident per year
}
