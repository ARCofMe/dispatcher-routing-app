# Dispatcher Routing App

Full-stack tool for dispatchers to preview, reorder, simulate, and commit daily technician routes using BlueFolder data and an optimized routing engine.

## Features
- Technician selection with daily route preview.
- Drag-and-drop stop ordering with status badges and inline edits (window/duration).
- Ad-hoc stop entry and live resimulation.
- Metrics with deltas (miles/time), ETA, origin/destination legs, and travel shown in hours/mins.
- Google Maps directions + shareable route link.
- Hide completed stops; service request context with “Open in BlueFolder”.
- Draft save/load per tech/date (local storage).
- Equipment-colored markers and compact legend.
- Default on-site duration is 60 minutes (ad-hoc and BlueFolder import).

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
VITE_GOOGLE_MAP_ID=your_map_id
VITE_BLUEFOLDER_ACCOUNT_NAME=your_subdomain
# Optional: disable frontend Directions calls to avoid Google API charges
# VITE_DISABLE_DIRECTIONS=true
```

Backend env (place in `backend/.env` or shell):
```
BLUEFOLDER_API_KEY=your_api_key
BLUEFOLDER_ACCOUNT_NAME=your_subdomain
BLUEFOLDER_API_PATH=/path/to/bluefolder-api        # optional override
ROUTING_EXTENSION_PATH=/path/to/optimized-routing-extension
DEBUG=1
# Optional: disable Google Directions on backend to avoid charges
# DISABLE_GMAPS_DIRECTIONS=true
# Optional: change default on-site minutes (fallback when BF doesn't provide)
# DEFAULT_DURATION_MINUTES=60
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

## Quick Windows install (non-technical friendly)
We ship a helper script that builds the frontend, sets up a Python virtualenv, installs backend deps, and runs everything on one port via Waitress.

1) Install Node.js LTS and Python 3.11+ (add both to PATH).
2) Fill `frontend/.env` with:
   - `VITE_GOOGLE_MAPS_API_KEY`
   - `VITE_GOOGLE_MAP_ID`
   - `VITE_BLUEFOLDER_ACCOUNT_NAME`
3) Open PowerShell and run from the repo root:
   ```powershell
   Set-Location path\to\dispatcher-routing-app
   .\scripts\windows\install_and_run.ps1 -Port 5000
   ```
   - This installs frontend deps, builds `frontend/dist`, creates `backend\.venv`, installs backend deps (including Waitress), seeds `backend\.env` from `.env.example` if missing, and starts the server.
4) Open http://localhost:5000

To stop, close the PowerShell window (Ctrl+C). Re-run the script later to restart; it reuses the existing venv/node_modules.

## Notes on Integration
- BlueFolder: `bluefolder_service.py` pulls techs/assignments via `BlueFolderIntegration`; map `_map_assignment_to_stop` to include duration/window/lat/lon when available. Status defaults to `pending`.
- Routing: `routing_service.py` geocodes, optimizes (windows + nearest-neighbor + Directions when available), anchors origin/destination, and computes metrics. Manual order still respected when provided.
- Commit endpoint is stubbed/unused in the UI; wire to BlueFolder assignment ordering if you need write-back.

## Usage
1. Start backend and frontend.
2. Select technician and date, load route.
3. Drag to reorder; edit windows/durations; add ad-hoc stops.
4. Hide completed stops; copy route link; expand stops for SR context/BlueFolder link.
5. Save/load drafts (per tech/date) if needed; commit when ready.

## Testing
- Manual: verify preview/simulate/commit endpoints, map directions, drag/drop, ad-hoc stops, status badges, and drafts in the UI.
- Automated: `cd backend && pytest` and `cd frontend && npm test -- --watch=false --reporter=dot`.
