# AquaSense — Smart Water Consumption Analysis & Leakage Prediction

A complete local web application based on the supplied academic project presentation. It analyses historical water readings, visualises consumption patterns, flags possible leakage anomalies and estimates the next seven days of demand.

> **Dataset note:** The application starts with a reproducible synthetic dataset (60 days, hourly readings across four zones) because no real dataset was supplied. It includes planted night-flow/leak events for demonstration. Charts and model outputs are generated from the data stored in the database. Synthetic results are for academic demonstration and are not proof of a real-world leak or a validated utility forecast.

## Technology
- Frontend: HTML5, CSS3, JavaScript, Chart.js
- Backend: Python 3, Flask
- Database: SQLite with Flask-SQLAlchemy
- Data analysis: Pandas, NumPy
- Anomaly detection: Scikit-learn Isolation Forest, IQR and Z-score, plus a minimum-night-flow rule
- Demand forecast: Scikit-learn Random Forest regression using lag features
- Authentication: Flask-Login and Werkzeug password hashing

## Features
1. Registration, login, logout and protected application pages.
2. Overview dashboard with KPIs, daily trend, hourly usage, latest open alerts and seven-day forecast.
3. Zone filter for the dashboard and readings list.
4. Water readings table, manual reading creation, editing and deletion.
5. CSV import with required-column validation, numeric validation, duplicate removal and invalid-row skipping.
6. CSV export of readings.
7. Leakage/anomaly alert log with open/resolved status and resolve action.
8. JSON endpoints: `/api/summary` and `/api/forecast`.
9. Responsive layout for desktop and mobile.

## Folder structure
```text
smart-water-analysis/
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── models.py
│   ├── routes.py
│   ├── services.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── readings.html
│   │   ├── alerts.html
│   │   └── upload.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── instance/                 # SQLite database created on first run
├── config.py
├── run.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
└── README.md
```

## Run on Windows (recommended)

1. Install **Python 3.14 (64-bit)** and make sure the Python Launcher (`py`) is installed.
2. Extract this ZIP. In VS Code, open the `smart-water-analysis` folder.
3. Double-click `setup_and_run.bat`. It creates a virtual environment, installs the compatible packages, and starts the website. The setup disables SQLAlchemy's optional C extensions because some Windows Application Control policies block those compiled files.
4. Open **http://127.0.0.1:5000** in your browser.
5. Choose **Create an account**, register with your own name/email and a password of at least 8 characters, then sign in. There are no hard-coded default credentials.

Keep the command window open while using the website. Press **Ctrl+C** in that window to stop it. The first launch needs an internet connection to install Python packages.

### Manual Windows setup (optional)

Open PowerShell in this folder and run these commands one at a time:

```powershell
py -3.14 -m venv .venv
$env:DISABLE_SQLALCHEMY_CEXT="1"
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install --only-binary=:all: --no-binary=SQLAlchemy -r requirements.txt
.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000.

### macOS / Linux

Use Python 3.14, create a virtual environment, and install the packages from `requirements.txt`. On these systems, set `DISABLE_SQLALCHEMY_CEXT=1` before installing SQLAlchemy from source if the same compiled-extension issue occurs.

## Database
- SQLite database is created automatically at `instance/smart_water.db` on first startup.
- Tables: `user`, `reading`, and `alert`.
- Synthetic sample readings and initial anomaly alerts are seeded only when the readings table is empty.
- To reset all local data, stop the server and delete `instance/smart_water.db`; restart the app to recreate the database and sample data.
- Passwords are stored as Werkzeug password hashes, not plain text.

## CSV import format
CSV must contain these exact column names:

```csv
timestamp,zone,meter_id,consumption_l,flow_rate
2026-10-01 08:00:00,North Zone,MTR-01,42.5,0.71
2026-10-01 09:00:00,North Zone,MTR-01,36.2,0.60
```

Optional `consumer_type` is supported. Timestamps should be parseable by Pandas. Negative consumption/flow values are discarded. Duplicate `(timestamp, zone, meter_id)` rows are removed.

## API endpoints (login required)
- `GET /api/summary?zone=All%20zones` — KPI summary JSON.
- `GET /api/forecast?zone=All%20zones` — next seven daily demand estimates.

## Testing
A lightweight Flask integration test is included as `test_app.py`. Run:

```bash
pip install -r requirements-dev.txt
pytest -q
```

The app uses Chart.js from jsDelivr and Google Fonts for the dashboard presentation; those visual assets need an internet connection. Core Flask pages, authentication, database and data processing run locally.

## Academic explanation / viva points
- **Data collection:** synthetic smart-meter records represent timestamps, zone, meter ID, litres consumed and flow rate.
- **Preprocessing:** timestamps and numeric fields are parsed; invalid rows, negative values and duplicate meter/time/zone entries are removed on CSV import.
- **Pattern analysis:** the dashboard aggregates readings by day, hour and weekday to reveal peaks and usage variation.
- **Leakage analysis:** IQR and Z-score identify statistical outliers; Isolation Forest detects multivariable anomalies; 2–4 AM high flow is an additional minimum-night-flow signal.
- **Forecasting:** a Random Forest model learns from previous daily totals (lag-1, lag-2, lag-7 and weekday index) and recursively estimates seven future days.
- **Limitations:** synthetic data is not a substitute for field measurements. A flagged reading is only a possible anomaly. Forecast accuracy should be evaluated on a chronological held-out real dataset using MAE/RMSE/MAPE before operational use.

## Security / deployment note
This is a college demonstration application intended for local use. Before public deployment, set a strong random `SECRET_KEY`, use HTTPS, add CSRF protection and rate limiting, configure a production WSGI server, and review data-access permissions.
