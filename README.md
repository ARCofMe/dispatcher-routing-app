# Dispatcher Routing App

Full-stack tool for dispatchers to preview, reorder, simulate, and commit daily technician routes using BlueFolder data and an optimized routing engine.

## Features
- Technician selection with daily route preview.
- Drag-and-drop stop ordering with status badges and inline edits (window/duration).
- Ad-hoc stop entry and live resimulation.
- Metrics with deltas (miles/time), ETA, and origin/destination legs.
- Google Maps directions + shareable route link.
- Hide completed stops; service request context with “Open in BlueFolder”.
- Draft save/load per tech/date (local storage).

## Project Structure
- `backend/` – Flask API, BlueFolder/routing integration stubs.
  - `services/bluefolder_service.py` – uses local BlueFolder SDK; set env for paths/keys.
  - `services/routing_service.py` – uses local optimized-routing-extension; geocodes and computes metrics.
- `frontend/` – Vite + React UI (Route planner, Map, Metrics, Stop list).

## Requirements
- Python 3.11+ (backend)
- Node 18+ (frontend)
- Local installs of:
  - https://github.com/ARCofMe/bluefolder-api
  - https://github.com/ARCofMe/optimized-routing-extension
  (use editable installs; override paths via env if needed)

## Environment
Copy `frontend/.env.example` to `frontend/.env` and fill:
```
VITE_GOOGLE_MAPS_API_KEY=your_key
VITE_BLUEFOLDER_ACCOUNT_NAME=your_subdomain
```

Backend env (place in `backend/.env` or shell):
```
BLUEFOLDER_API_KEY=your_api_key
BLUEFOLDER_ACCOUNT_NAME=your_subdomain
BLUEFOLDER_API_PATH=/path/to/bluefolder-api        # optional override
ROUTING_EXTENSION_PATH=/path/to/optimized-routing-extension
DEBUG=1
```

## Setup
Backend:
```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e path/to/bluefolder-api  # or git+https://github.com/ARCofMe/bluefolder-api.git
pip install -e path/to/optimized-routing-extension  # or git+https://github.com/ARCofMe/optimized-routing-extension.git
python app.py
```

Frontend:
```
cd frontend
npm install
npm run dev
```

## Notes on Integration
- BlueFolder: `bluefolder_service.py` pulls techs/assignments via `BlueFolderIntegration`; map `_map_assignment_to_stop` to include duration/window/lat/lon when available. Status defaults to `pending`.
- Routing: `routing_service.py` currently uses Haversine + geopy for metrics and honors manual order; plug in optimized-routing-extension for true optimization (replace `_optimize_order` and metrics as needed).
- Commit endpoint is stubbed; wire to BlueFolder assignment ordering when available.

## Usage
1. Start backend and frontend.
2. Select technician and date, load route.
3. Drag to reorder; edit windows/durations; add ad-hoc stops.
4. Hide completed stops; copy route link; expand stops for SR context/BlueFolder link.
5. Save/load drafts (per tech/date) if needed; commit when ready.

## Testing
- Manual: verify preview/simulate/commit endpoints, map directions, drag/drop, ad-hoc stops, status badges, and drafts in the UI.
- Automated tests not included; add as needed.
