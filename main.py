import os
import time
import io
import csv
from datetime import datetime
from typing import List
from dotenv import load_dotenv
import googlemaps
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import (Column, Float, Integer, String, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session, sessionmaker

#Configuration 
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
RADIUS_METERS = int(os.getenv("RADIUS_METERS", "50000"))  
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))   

if not API_KEY:
    raise RuntimeError("Set the GOOGLE_API_KEY environment variable first.")


# A coarse grid of 65 major US city centres (≈ all states + big metros).
# Radius = 50 km will cover the continental US with minimal overlap.
LOCATIONS: dict[str, tuple[float, float]] = {
    "Montgomery, AL": (32.3668, -86.3000),
    "Juneau, AK": (58.3019, -134.4197),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Little Rock, AR": (34.7465, -92.2896),
    "Sacramento, CA": (38.5816, -121.4944),
    "Denver, CO": (39.7392, -104.9903),
    "Hartford, CT": (41.7658, -72.6734),
    "Dover, DE": (39.1582, -75.5244),
    "Tallahassee, FL": (30.4383, -84.2807),
    "Atlanta, GA": (33.7490, -84.3880),
    "Honolulu, HI": (21.3069, -157.8583),
    "Boise, ID": (43.6150, -116.2023),
    "Springfield, IL": (39.7817, -89.6501),
    "Indianapolis, IN": (39.7684, -86.1581),
    "Des Moines, IA": (41.5868, -93.6250),
    "Topeka, KS": (39.0473, -95.6752),
    "Frankfort, KY": (38.2009, -84.8733),
    "Baton Rouge, LA": (30.4515, -91.1871),
    "Augusta, ME": (44.3106, -69.7795),
    "Annapolis, MD": (38.9784, -76.4922),
    "Boston, MA": (42.3601, -71.0589),
    "Lansing, MI": (42.7325, -84.5555),
    "St. Paul, MN": (44.9537, -93.0900),
    "Jackson, MS": (32.2988, -90.1848),
    "Jefferson City, MO": (38.5767, -92.1735),
    "Helena, MT": (46.5891, -112.0391),
    "Lincoln, NE": (40.8136, -96.7026),
    "Carson City, NV": (39.1638, -119.7674),
    "Concord, NH": (43.2081, -71.5376),
    "Trenton, NJ": (40.2171, -74.7429),
    "Santa Fe, NM": (35.6870, -105.9378),
    "Albany, NY": (42.6526, -73.7562),
    "Raleigh, NC": (35.7796, -78.6382),
    "Bismarck, ND": (46.8083, -100.7837),
    "Columbus, OH": (39.9612, -82.9988),
    "Oklahoma City, OK": (35.4676, -97.5164),
    "Salem, OR": (44.9429, -123.0351),
    "Harrisburg, PA": (40.2732, -76.8867),
    "Providence, RI": (41.8236, -71.4222),
    "Columbia, SC": (34.0007, -81.0348),
    "Pierre, SD": (44.3683, -100.3510),
    "Nashville, TN": (36.1627, -86.7816),
    "Austin, TX": (30.2672, -97.7431),
    "Salt Lake City, UT": (40.7608, -111.8910),
    "Montpelier, VT": (44.2601, -72.5754),
    "Richmond, VA": (37.5407, -77.4360),
    "Olympia, WA": (47.0379, -122.9007),
    "Charleston, WV": (38.3498, -81.6326),
    "Madison, WI": (43.0731, -89.4012),
    "Cheyenne, WY": (41.1400, -104.8202),
}



#DB setup
Base = declarative_base()
engine = create_engine("sqlite:///companies.db", echo=False, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)



class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(String, index=True, nullable=False)
    name = Column(String)
    address = Column(String)
    phone = Column(String)
    website = Column(String)
    rating = Column(Float)
    lat = Column(Float)
    lng = Column(Float)
    keyword = Column(String)  # which seed keyword matched
    fetched_at = Column(String)

    __table_args__ = (
        UniqueConstraint("place_id", name="uix_place"),
    )


Base.metadata.create_all(bind=engine)

# Google API client -----------------------------------------------------------
client = googlemaps.Client(key=API_KEY)


# FastAPI --------------------------------------------------------------------
app = FastAPI(title="US Logistics Companies Collector")


class CompanyOut(BaseModel):
    id: int
    place_id: str
    name: str | None
    address: str | None
    phone: str | None
    website: str | None
    rating: float | None
    lat: float | None
    lng: float | None
    keyword: str
    fetched_at: str

    class Config:
        from_attributes = True


# Collector logic ------------------------------------------------------------


def _collect_one_location(db: Session, keyword: str, lat: float, lng: float):
    existing = set()
    for row in db.query(Company.place_id).yield_per(500):
        existing.add(row[0])
    seen: set[str] = set()

    response = client.places_nearby(
        location=(lat, lng), radius=RADIUS_METERS, keyword=keyword
    )

    while True:
        for place in response.get("results", []):
            pid = place["place_id"]
            if pid in existing or pid in seen:
                continue  # skip duplicates fast

            # fetch details only for new pids
            details = client.place(
                place_id=pid,
                fields=[
                    "name",
                    "formatted_address",
                    "international_phone_number",
                    "website",
                    "rating",
                    "geometry",
                ],
            )
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
                fetched_at=datetime.utcnow().isoformat(timespec="seconds"),
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


def collect_companies(keyword):#iterate through all locations
    db = SessionLocal()
    try:
        for city, (lat, lng) in LOCATIONS.items():
                _collect_one_location(db, keyword, lat, lng)
    finally:
        db.close()



# API routes -----------------------------------------------------------------

@app.post("/collect", summary="Start background data‑harvest")
async def trigger_collection(bg: BackgroundTasks, keyword: str = None):
    if keyword is not None:
        bg.add_task(collect_companies,keyword)
        return {"detail": "Collection started."}
    else:
        return {"detail": "No keyword provided. Please specify a keyword."}



@app.get("/companies", response_model=List[CompanyOut])
def list_companies(size: int = 20, skip: int = 0, keyword: str | None = None):
    with SessionLocal() as db:
        query = db.query(Company)
        if keyword is not None:
            query = query.filter(Company.keyword == keyword)
        return query.offset(size*skip).limit(size).all()

@app.get("/companies.csv", summary="Get companies in CSV")
def download_companies_csv(size: int = 20, skip: int = 0, keyword: str | None = None):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    headers = [
        "id", "place_id", "name", "address", "phone", "website",
        "rating", "lat", "lng", "keyword", "fetched_at"
    ]
    writer.writerow(headers)

    with SessionLocal() as db:
        query = db.query(Company)
        if keyword:
            query = query.filter(Company.keyword == keyword)
        results = query.offset(size * skip).limit(size).all()

        for row in results:
            writer.writerow([
                row.id, row.place_id, row.name, row.address,
                row.phone, row.website, row.rating,
                row.lat, row.lng, row.keyword, row.fetched_at
            ])

    buffer.seek(0)
    headers = {"Content-Disposition": "attachment; filename=companies.csv"}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)