"""
Fetches Austin's road network from OpenStreetMap using osmnx,
converts it to a GeoDataFrame with real LineString geometry,
and inserts each segment into the road_segments table.

Usage:
    python etl/seed_road_segments.py
    python etl/seed_road_segments.py --force   # re-seed even if rows exist
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import osmnx as ox
import geopandas as gpd
from dotenv import load_dotenv
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
from sqlalchemy.orm import Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from backend.app.database import SessionLocal, init_postgis
from backend.app.geo_models import RoadSegment


# ── Austin metro bounding box ──────────────────────────────────────────────────
# osmnx 2.x bbox order: (left, bottom, right, top) = (west, south, east, north)
AUSTIN_BBOX = (-98.22, 30.00, -97.46, 30.62)

# Road types relevant for traffic analysis — excludes footpaths, cycleways, etc.
HIGHWAY_FILTER = (
    '["highway"~"motorway|motorway_link|trunk|trunk_link'
    '|primary|primary_link|secondary|secondary_link|tertiary"]'
)

# Map known monitored corridor names → patterns that appear in OSM road names.
# Used to populate the corridor_name FK so geo queries can link back to traffic data.
CORRIDOR_PATTERNS: dict[str, list[str]] = {
    "I-35_Downtown":             ["interstate 35", "i-35", "i 35"],
    "Mopac_Expressway_Downtown": ["mopac", "loop 1"],
    "US-183_North":              ["183", "ed bluestein", "research boulevard"],
    "Loop-360_West":             ["capital of texas", "loop 360"],
    "Congress_Ave_Downtown":     ["congress avenue", "congress ave"],
}


# ── OSM fetch ──────────────────────────────────────────────────────────────────

def fetch_road_network() -> gpd.GeoDataFrame:
    """
    Download the Austin road network from OpenStreetMap and return
    the edges as a GeoDataFrame.  Each row is one road segment with
    a LineString geometry already in EPSG:4326 (SRID 4326).
    """
    print("  Querying OpenStreetMap via Overpass API...")
    G = ox.graph_from_bbox(
        AUSTIN_BBOX,
        network_type="drive",
        custom_filter=HIGHWAY_FILTER,
        retain_all=False,
    )

    # graph_to_gdfs returns (nodes_gdf, edges_gdf) when both=True
    _, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)

    print(f"  {len(edges):,} road segments returned")
    return edges


# ── field parsers ──────────────────────────────────────────────────────────────

def _scalar(value) -> str | None:
    """OSM fields can be a string or list — always return a single string."""
    if value is None:
        return None
    return value[0] if isinstance(value, list) else str(value)


def parse_name(value) -> str | None:
    return _scalar(value)


def parse_highway(value) -> str | None:
    return _scalar(value)


def parse_speed_mph(value) -> int | None:
    """
    Convert OSM maxspeed to integer mph.
    Handles: "35 mph", "35", "56 km/h", lists, None.
    """
    raw = _scalar(value)
    if raw is None:
        return None

    match = re.search(r"(\d+)", raw)
    if not match:
        return None

    speed = int(match.group(1))
    if "km" in raw.lower():
        speed = round(speed * 0.621371)
    return speed


def to_linestring_wkt(geom) -> str | None:
    """
    Convert Shapely geometry to a PostGIS WKT string with SRID prefix.
    Handles MultiLineString by merging or taking the longest sub-line.
    """
    if geom is None:
        return None
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        geom = merged if isinstance(merged, LineString) else max(geom.geoms, key=lambda g: g.length)
    if not isinstance(geom, LineString):
        return None
    return f"SRID=4326;{geom.wkt}"


def corridor_for(name: str | None) -> str | None:
    """Return the matching corridor_name if this road name matches a monitored corridor."""
    if not name:
        return None
    name_lower = name.lower()
    for corridor, patterns in CORRIDOR_PATTERNS.items():
        if any(p in name_lower for p in patterns):
            return corridor
    return None


# ── database insert ────────────────────────────────────────────────────────────

def load_into_db(edges: gpd.GeoDataFrame, force: bool = False) -> int:
    """
    Iterate over each road segment in the GeoDataFrame and insert a row
    into road_segments with name, speed_limit_mph, and geometry.

    Returns the number of rows inserted.
    """
    db: Session = SessionLocal()
    try:
        existing = db.query(RoadSegment).count()
        if existing > 0 and not force:
            print(f"  road_segments already has {existing:,} rows — skipping.")
            print("  Pass --force to re-seed.")
            return 0

        if existing > 0 and force:
            print(f"  --force: deleting {existing:,} existing rows...")
            db.query(RoadSegment).delete()
            db.commit()

        inserted = 0
        skipped = 0

        for (_, _, _), row in edges.iterrows():
            wkt = to_linestring_wkt(row.get("geometry"))
            if wkt is None:
                skipped += 1
                continue

            osmid = row.get("osmid")
            if isinstance(osmid, list):
                osmid = osmid[0]

            name = parse_name(row.get("name"))

            segment = RoadSegment(
                osm_id=int(osmid) if osmid is not None else None,
                name=name,
                highway_type=parse_highway(row.get("highway")),
                speed_limit_mph=parse_speed_mph(row.get("maxspeed")),
                corridor_name=corridor_for(name),
                length_m=float(row["length"]) if row.get("length") is not None else None,
                geometry=wkt,
            )
            db.add(segment)
            inserted += 1

            # Commit every 500 rows to avoid a huge single transaction
            if inserted % 500 == 0:
                db.commit()
                print(f"  {inserted:,} rows inserted...")

        db.commit()

        if skipped:
            print(f"  {skipped} segments skipped (no valid geometry)")

        return inserted

    finally:
        db.close()


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    force = "--force" in sys.argv

    print("Road segment seeder — Austin metro\n")
    print(f"  Bounding box : west={AUSTIN_BBOX[0]}, south={AUSTIN_BBOX[1]}, "
          f"east={AUSTIN_BBOX[2]}, north={AUSTIN_BBOX[3]}")
    print(f"  Highway types: motorway, trunk, primary, secondary, tertiary\n")

    init_postgis()

    print("[1/2] Fetching road network from OpenStreetMap...")
    edges = fetch_road_network()

    print("\n[2/2] Inserting into road_segments...")
    n = load_into_db(edges, force=force)

    if n:
        print(f"\nDone. {n:,} road segments inserted into road_segments.")
    else:
        print("\nFinished.")


if __name__ == "__main__":
    main()
