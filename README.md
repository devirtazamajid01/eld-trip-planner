# ELD Trip Planner

Full-stack application that generates FMCSA-compliant Hours of Service (HOS) trip plans with interactive route maps and daily ELD log sheets.

## Features

- **Trip Planning**: Enter current location, pickup, drop-off, and cycle hours used
- **HOS-Compliant Scheduling**: Automatically schedules breaks, rest periods, and fuel stops per 49 CFR Part 395
- **Interactive Map**: Route visualization with color-coded stop markers using Leaflet + OpenStreetMap
- **Daily ELD Log Sheets**: Canvas-drawn log sheets replicating the official FMCSA paper form

## HOS Rules Implemented

| Rule | Limit |
|------|-------|
| Driving limit per shift | 11 hours |
| On-duty window | 14 hours |
| Mandatory break | 30 min after 8 hours driving |
| Cycle limit | 70 hours / 8 days |
| Off-duty between shifts | 10 consecutive hours |
| Cycle restart | 34 hours off-duty |
| Fuel stops | Every 1,000 miles |
| Pickup / drop-off | 1 hour each (on-duty not driving) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5, Django REST Framework, Python 3.12 |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4 |
| Map | Leaflet.js + React-Leaflet + OpenStreetMap |
| Routing | OpenRouteService API |
| Geocoding | Nominatim (OpenStreetMap) |
| Log Sheets | HTML5 Canvas |
| CI | GitHub Actions (ruff, ESLint, TypeScript, build) |

## Project Structure

```
├── backend/
│   ├── config/              # Django settings, URLs, WSGI
│   ├── trips/
│   │   ├── hos_engine.py    # HOS scheduling engine (core logic)
│   │   ├── route_service.py # OpenRouteService API wrapper
│   │   ├── views.py         # REST API endpoint
│   │   └── serializers.py   # Request validation
│   ├── pyproject.toml       # Ruff linter/formatter config
│   ├── requirements.txt
│   └── Procfile             # Gunicorn for production
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── TripForm.tsx
│   │   │   ├── LocationInput.tsx
│   │   │   ├── RouteMap.tsx
│   │   │   ├── DailyLogSheet.tsx
│   │   │   ├── StopsList.tsx
│   │   │   └── TripSummary.tsx
│   │   ├── hooks/           # Custom React hooks
│   │   ├── types/           # TypeScript interfaces
│   │   └── utils/           # Canvas drawing, stop config
│   ├── eslint.config.js
│   └── .prettierrc
└── .github/workflows/ci.yml # CI pipeline
```

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- OpenRouteService API key (free at https://openrouteservice.org/dev/#/signup)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ORS_API_KEY
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local if backend URL differs
npm run dev
```

Open http://localhost:5173 in your browser.

## Linting & Formatting

### Backend

```bash
cd backend
pip install ruff
ruff check .          # Lint
ruff format .         # Format
```

### Frontend

```bash
cd frontend
npx eslint src/       # Lint
npx prettier --write src/  # Format
npx tsc --noEmit      # Type check
```

## CI

GitHub Actions runs on every push/PR to `main`:

- **Backend**: `ruff check`, `ruff format --check`, Django import verification
- **Frontend**: TypeScript type check, ESLint, production build

## Deployment

- **Backend**: Deploy to Render using the included `render.yaml`
- **Frontend**: Deploy to Vercel — it auto-detects Vite projects

Set these environment variables:

| Variable | Where | Value |
|----------|-------|-------|
| `ORS_API_KEY` | Backend | Your OpenRouteService key |
| `CORS_ALLOWED_ORIGINS` | Backend | Your Vercel frontend URL |
| `ALLOWED_HOSTS` | Backend | Your Render domain |
| `VITE_API_URL` | Frontend | Your Render backend URL |
