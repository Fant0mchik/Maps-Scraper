Python 3.12.1

This project is async webserver on FastAPI, which parses companies from Google Maps and saves data to SQLite db.
API needed: Places API

To launch:
-install requirements
-add "GOOGLE_API_KEY" in .end and paste your api key 
-launch ASGI server ( /Maps-Scraper uvicorn main:app --reload )