Python version used in project: Python 3.12.1

This project is async webserver on FastAPI, which parses companies from Google Maps and saves data to SQLite db.
API needed: Places API

WARNING!
Script adds items to database only with unique place_id, which means data will not be updated by newer POST request and can only be updated by erasing db data.

Commands:
- Install requirements:
  - pip install -r requirements.txt
  - Other option:
    - pip install fastapi uvicorn sqlalchemy
- Lauch server:
  - uvicorn main:app --reload
 
Examples of curl requests:
- GET /companies?size=20&skip=0&keyword=ups
- GET /companies.csv?size=20&skip=0&keyword=ups
- POST /collect?keyword=apple