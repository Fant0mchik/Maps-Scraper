import os
import time
import csv
import sys
import uuid
import subprocess
import argparse
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
import googlemaps
from sqlalchemy import (Column, Float, Integer, String, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from threading import Lock
from io import StringIO
import threading
import traceback

# Configuration
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
RADIUS_METERS = int(os.getenv("RADIUS_METERS", "50000"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))

if not API_KEY:
    raise RuntimeError("Set the GOOGLE_API_KEY environment variable first.")

# Locations with coordinates
LOCATIONS: dict[str,list[tuple[str,float,float]]] = {
    "AL": [("Birmingham", 33.543682, -86.779633)],
    "AK": [("Anchorage", 61.217381, -149.863129)],
    "AZ": [("Phoenix", 33.4484, -112.0740)],
    "AR": [("Little Rock", 34.7465, -92.2896)],
    "CA": [("Los Angeles", 34.0522, -118.2437)],
    "CO": [("Denver", 39.7392, -104.9903)],
    "CT": [("Bridgeport", 41.1782, -73.1952)],
    "DE": [("Wilmington", 39.7391, -75.5398)],
    "FL": [
        ("Jacksonville", 30.3322, -81.6557),
        ("Tampa", 27.964157, -82.452606),
        ("Miami", 25.775163, -80.208615),
        ("Orlando", 28.538336, -81.379222),
    ],
    "GA": [("Atlanta", 33.7490, -84.3880)],
    "HI": [("Honolulu", 21.3069, -157.8583)],
    "ID": [("Boise", 43.6150, -116.2023)],
    "IL": [
        ("Chicago", 41.8781, -87.6298),
        ("Springfield", 39.7817, -89.6501),  
    ],
    "IN": [("Indianapolis", 39.7684, -86.1581)],
    "IA": [("Des Moines", 41.5868, -93.6250)],
    "KS": [("Wichita", 37.6872, -97.3301)],
    "KY": [("Louisville", 38.2527, -85.7585)],
    "LA": [("New Orleans", 29.9511, -90.0715)],
    "ME": [("Portland", 43.6591, -70.2568)],
    "MD": [("Baltimore", 39.2904, -76.6122)],
    "MA": [("Boston", 42.3601, -71.0589)],
    "MI": [
        ("Detroit", 42.3314, -83.0458),
        ("Cleveland", 41.505493, -81.681290),  
    ],
    "MN": [("Minneapolis", 44.9778, -93.2650)],
    "MS": [("Jackson", 32.2988, -90.1848)],
    "MO": [
        ("Kansas City", 39.0997, -94.5786),
        ("St. Louis", 38.627003, -90.199402),
    ],
    "MT": [("Billings", 45.7833, -108.5007)],
    "NE": [("Omaha", 41.2565, -95.9345)],
    "NV": [("Las Vegas", 36.1699, -115.1398)],
    "NH": [("Manchester", 42.9956, -71.4548)],
    "NJ": [("Newark", 40.7357, -74.1724)],
    "NM": [("Albuquerque", 35.0844, -106.6504)],
    "NY": [
        ("New York City", 40.7128, -74.0060),
        ("Buffalo", 42.8864, -78.8784),
        ("Rochester", 43.1566, -77.6088),
    ],
    "NC": [("Charlotte", 35.2271, -80.8431)],
    "ND": [("Fargo", 46.8772, -96.7898)],
    "OH": [
        ("Columbus", 39.9612, -82.9988),
        ("Cleveland", 41.505493, -81.681290),
        ("Cincinnati", 39.1031, -84.5120),
    ],
    "OK": [("Oklahoma City", 35.4676, -97.5164)],
    "OR": [("Portland", 45.5122, -122.6587)],
    "PA": [
        ("Philadelphia", 39.9526, -75.1652),
        ("Pittsburgh", 40.440624, -79.995888),
    ],
    "RI": [("Providence", 41.8236, -71.4222)],
    "SC": [("Columbia", 34.0007, -81.0348)],
    "SD": [("Sioux Falls", 43.5446, -96.7311)],
    "TN": [("Memphis", 35.1495, -90.0490), ("Nashville", 36.1627, -86.7816)],
    "TX": [
        ("Houston", 29.7604, -95.3698),
        ("San Antonio", 29.4241, -98.4936),
        ("Dallas", 32.7767, -96.7970),
        ("Fort Worth", 32.7555, -97.3308),
        ("Austin", 30.2672, -97.7431),
    ],
    "UT": [("Salt Lake City", 40.7608, -111.8910)],
    "VT": [("Burlington", 44.4759, -73.2121)],
    "VA": [
        ("Virginia Beach", 36.8529, -75.9780),
        ("Washington, D.C.", 38.8950, -77.0364),
    ],
    "WA": [("Seattle", 47.6062, -122.3321)],
    "WV": [("Charleston", 38.3498, -81.6326)],
    "WI": [("Milwaukee", 43.0389, -87.9065)],
    "WY": [("Cheyenne", 41.1400, -104.8202)],
}

# DB setup
Base = declarative_base()
engine = create_engine("sqlite:///companies.db", echo=False, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    place_id = Column(String, unique=True, index=True)
    name = Column(String)
    address = Column(String)
    phone = Column(String)
    website = Column(String)
    rating = Column(Float)
    lat = Column(Float)
    lng = Column(Float)
    keyword = Column(String)
    fetched_at = Column(String)
    state = Column(String)
    __table_args__ = (UniqueConstraint("place_id", name="uix_place"),)

Base.metadata.create_all(bind=engine)

# Google API client
client = googlemaps.Client(key=API_KEY)

# Collector
def _collect_one_location(db: Session, keyword: str, lat: float, lng: float, state: Optional[str]=None):
    existing = {row[0] for row in db.query(Company.place_id).yield_per(500)}
    seen: set[str] = set()
    response = client.places_nearby(location=(lat, lng), radius=RADIUS_METERS, keyword=keyword)
    while True:
        for place in response.get("results", []):
            pid = place["place_id"]
            if pid in existing or pid in seen:
                continue
            details = client.place(place_id=pid, fields=[
                "name", "formatted_address", "international_phone_number",
                "website", "rating", "geometry",
            ])
            res = details["result"]
            company = Company(
                place_id=pid,
                name=res.get("name"),
                address=res.get("formatted_address"),
                phone=res.get("international_phone_number"),
                website=res.get("website"),
                rating=res.get("rating"),
                lat=res.get("geometry", {}).get("location", {}).get("lat"),
                lng=res.get("geometry", {}).get("location", {}).get("lng"),
                keyword=keyword,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                state=state,
            )
            db.add(company)
            seen.add(pid)
            try:
                db.commit()
            except Exception:
                db.rollback()
        token = response.get("next_page_token")
        if not token:
            break
        time.sleep(REQUEST_DELAY)
        response = client.places_nearby(page_token=token)

def collect_companies(keyword: str, states: Optional[str]=None, task_id: Optional[str]=None):
    db = SessionLocal()
    try:
        if states is None:
            locations = LOCATIONS.items()
        else:
            coords = LOCATIONS.get(states)
            if not coords:
                log_status(task_id, f"State '{states}' not found in LOCATIONS or has no cities.")
                return
            locations = [(states, coords)]
        for state, coords in locations:
            for city, lat, lng in coords:
                log_status(task_id, f"Collecting for {city}, {state}") 
                _collect_one_location(db, keyword, lat, lng, state)
    finally:
        db.close()

# CLI and background spawn
collector_tasks: dict[str, "CollectorTask"] = {}
collector_tasks_lock = Lock()

class CollectorTask:
    def __init__(self, keyword: str, states: Optional[str]=None):
        self.id = str(uuid.uuid4())
        self.keyword = keyword
        self.states = states
        self.status = "in progress"

    def run(self):
        """
        Runs the collection task.
        """
        start_time = time.time()
        try:
            collect_companies(self.keyword, self.states)
            self.status = "done"
        except Exception as e:
            self.status = f"failed: {str(e)}" 
            return
        self.elapsed = time.time() - start_time

def export_companies_to_csv(filename: str, size: int=1000, skip: int=0, keyword: Optional[str]=None, state: Optional[str]=None):
    with SessionLocal() as db:
        query = db.query(Company)
        if keyword:
            query = query.filter(Company.keyword == keyword)
        if state:
            query = query.filter(Company.state == state)
        companies = query.offset(size * skip).limit(size).all()
        with open(filename, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "place_id", "name", "address", "phone",
                "website", "rating", "lat", "lng",
                "keyword", "fetched_at", "state"
            ])
            for c in companies:
                row = [
                    c.id, c.place_id, c.name, c.address,
                    c.phone, c.website, c.rating,
                    c.lat, c.lng, c.keyword,
                    c.fetched_at, c.state
                ]

                row = ["NULL" if v is None else v for v in row]
                writer.writerow(row)

def log_status(task_id: str, message: str):
    log_file = f"{task_id}.log"
    #print(message, flush=True)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(message + "\n")

def run_collector_in_thread(keyword: str, state: Optional[str]=None):
    task = CollectorTask(keyword, state)
    print(f"Collection started in background thread. Task ID: {task.id}")
    print(f"Logs: {task.id}.log")
    log_status(task.id, f"Task {task.id} started at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    def target():
        start_time = time.time()
        try:
            log_status(task.id, f"Collecting for keyword='{task.keyword}' state='{task.states}'")
            collect_companies(task.keyword, task.states, task.id)
            task.status = "done"
        except Exception as e:
            tb = traceback.format_exc()
            log_status(task.id, f"FAILED: {str(e)}\n{tb}")
            task.status = f"failed: {str(e)}"
        finally:
            elapsed = time.time() - start_time
            log_status(task.id, f"Task {task.id} finished with status: {task.status} in {elapsed:.2f} seconds")
    thread = threading.Thread(target=target)
    thread.start()
    thread.join()  
    return task.id

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Google Maps Collector CLI")
    subparsers = parser.add_subparsers(dest="command")

    # collect: spawn background thread
    collect_parser = subparsers.add_parser("collect", help="Start collection in background")
    collect_parser.add_argument("keyword", type=str)
    collect_parser.add_argument("--state", type=str, default=None)

    # list and export remain synchronous for simplicity
    list_parser = subparsers.add_parser("list", help="List companies")
    list_parser.add_argument("--size", type=int, default=20)
    list_parser.add_argument("--skip", type=int, default=0)
    list_parser.add_argument("--keyword", type=str, default=None)
    list_parser.add_argument("--state", type=str, default=None)

    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument("--filename", type=str, default="companies.csv")
    export_parser.add_argument("--size", type=int, default=1000)
    export_parser.add_argument("--skip", type=int, default=0)
    export_parser.add_argument("--keyword", type=str, default=None)
    export_parser.add_argument("--state", type=str, default=None)

    args = parser.parse_args()

    if args.command == "collect":
        task_id = run_collector_in_thread(args.keyword, args.state)
    elif args.command == "list":
        with SessionLocal() as db:
            query = db.query(Company)
            if args.keyword:
                query = query.filter(Company.keyword == args.keyword)
            if args.state:
                query = query.filter(Company.state == args.state)
            companies = query.offset(args.size * args.skip).limit(args.size).all()
            for c in companies:
                print(f"{c.id}: {c.name} ({c.address}) [{c.state}]")

    elif args.command == "export":
        export_companies_to_csv(
            filename=args.filename,
            size=args.size,
            skip=args.skip,
            keyword=args.keyword,
            state=args.state
        )
        print(f"CSV saved to {args.filename}")

    else:
        parser.print_help()
