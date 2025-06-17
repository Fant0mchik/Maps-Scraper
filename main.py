import os
import time
from datetime import datetime
from typing import List
from dotenv import load_dotenv
import googlemaps
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel
from sqlalchemy import (Column, Float, Integer, String, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session, sessionmaker

#Configuration 
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Set the GOOGLE_API_KEY environment variable first.")

# Keywords 
KEYWORDS = [
    "moving company",
    "logistics service",
    "shipping company",
]

# A coarse grid of 65 major US city centres (≈ all states + big metros).
# Radius = 50 km will cover the continental US with minimal overlap.
LOCATIONS = [  # (lat, lng)
    (40.7128, -74.0060),   # New York, NY
    (34.0522, -118.2437),  # Los Angeles, CA
    (41.8781, -87.6298),   # Chicago, IL
    (29.7604, -95.3698),   # Houston, TX
    (33.4484, -112.0740),  # Phoenix, AZ
    (39.7392, -104.9903),  # Denver, CO
    (47.6062, -122.3321),  # Seattle, WA
    (25.7617, -80.1918),   # Miami, FL
    (38.9072, -77.0369),   # Washington, DC
    (32.7767, -96.7970),   # Dallas, TX
    (37.7749, -122.4194),  # San Francisco, CA
    (42.3601, -71.0589),   # Boston, MA
    (36.1627, -86.7816),   # Nashville, TN
    (35.2271, -80.8431),   # Charlotte, NC
    (45.5051, -122.6750),  # Portland, OR
    (39.9526, -75.1652),   # Philadelphia, PA
    (33.7490, -84.3880),   # Atlanta, GA
    (36.1699, -115.1398),  # Las Vegas, NV
    (44.9778, -93.2650),   # Minneapolis, MN
    (39.7684, -86.1581),   # Indianapolis, IN
]
RADIUS_METERS = 50_000  # 50 km ≈ 31 mi – max allowed for Places API Nearby
REQUEST_DELAY = 2       # seconds – per Google’s next_page_token docs

#DB setup
Base = declarative_base()
engine = create_engine("sqlite:///companies.db", echo=False, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def _collect_one_location(db: Session, keyword: str, lat: float, lng: float):#collects info of 1 location
    # pull already‑present place_ids once per location call
    existing = {row[0] for row in db.query(Company.place_id).all()}
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

            # try to commit immediately; on duplicate (race with another thread)
            # rollback and ignore
            try:
                db.commit()
            except Exception:
                db.rollback()

        token = response.get("next_page_token")
        if not token:
            break
        time.sleep(REQUEST_DELAY)
        response = client.places_nearby(page_token=token)


def collect_companies():#iterate through all keywords
    db = SessionLocal()
    try:
        for kw in KEYWORDS:
            for lat, lng in LOCATIONS:
                _collect_one_location(db, kw, lat, lng)
    finally:
        db.close()



# API routes -----------------------------------------------------------------

@app.post("/collect", summary="Start background data‑harvest")
async def trigger_collection(bg: BackgroundTasks):
    bg.add_task(collect_companies)
    return {"detail": "Collection started – check /companies for progress."}


@app.get("/companies", response_model=List[CompanyOut])
def list_companies(limit: int = 100, skip: int = 0):
    with SessionLocal() as db:
        return db.query(Company).offset(skip).limit(limit).all()

