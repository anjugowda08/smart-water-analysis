from datetime import datetime, timedelta
import io
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from app import db
from app.models import Reading, Alert

ZONES = ["North Zone", "South Zone", "East Zone", "West Zone"]


def seed_if_empty():
    if Reading.query.first():
        return
    rng = np.random.default_rng(42)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    rows = []
    # 60 days of hourly zone readings; regular morning/evening peaks and a few planted leak events.
    for day in range(60):
        for hour in range(24):
            stamp = now - timedelta(days=59-day, hours=23-hour)
            for zi, zone in enumerate(ZONES):
                morning = 34 if 6 <= hour <= 9 else 0
                evening = 29 if 17 <= hour <= 20 else 0
                base = 13 + morning + evening + (5 if stamp.weekday() >= 5 else 0)
                seasonal = 1 + 0.12 * np.sin(day / 12)
                value = max(2, (base + zi * 2) * seasonal + rng.normal(0, 4))
                leak = (day in (18, 19, 42, 43) and hour in range(1, 5) and zi in (0, 2))
                if leak:
                    value += float(rng.uniform(65, 100))
                flow = value / 60 * float(rng.uniform(0.85, 1.15))
                rows.append(Reading(timestamp=stamp, zone=zone, meter_id=f"MTR-{zi+1:02d}",
                                    consumer_type="Household" if zi % 2 == 0 else "Residential Block",
                                    consumption_l=round(float(value), 2), flow_rate=round(float(flow), 3),
                                    is_synthetic_leak=leak))
    db.session.bulk_save_objects(rows)
    db.session.commit()
    run_leak_detection(save_alerts=True)


def readings_frame(zone=None, start=None, end=None):
    q = Reading.query
    if zone and zone != "All zones":
        q = q.filter_by(zone=zone)
    if start:
        q = q.filter(Reading.timestamp >= datetime.fromisoformat(start))
    if end:
        q = q.filter(Reading.timestamp < datetime.fromisoformat(end) + timedelta(days=1))
    records = q.order_by(Reading.timestamp.asc()).all()
    if not records:
        return pd.DataFrame(columns=["timestamp", "zone", "consumption_l", "flow_rate"])
    return pd.DataFrame([{"timestamp": r.timestamp, "zone": r.zone, "consumption_l": r.consumption_l,
                          "flow_rate": r.flow_rate, "reading_id": r.id, "is_synthetic_leak": r.is_synthetic_leak}
                         for r in records])


def run_leak_detection(save_alerts=False):
    frame = readings_frame()
    if frame.empty:
        return []
    flagged = set()
    for zone, group in frame.groupby("zone"):
        vals = group["consumption_l"]
        q1, q3 = vals.quantile(.25), vals.quantile(.75)
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr
        std = vals.std() or 1
        zscore = (vals - vals.mean()) / std
        # Isolation Forest is applied per zone; night-flow rule is an additional transparent signal.
        model = IsolationForest(contamination=0.025, random_state=42)
        iso = model.fit_predict(group[["consumption_l", "flow_rate"]])
        hours = group["timestamp"].dt.hour
        night = (hours >= 2) & (hours <= 4) & (group["consumption_l"] > vals.quantile(.80))
        mask = (vals > upper) | (zscore > 2.5) | (iso == -1) | night
        flagged.update(group.loc[mask, "reading_id"].astype(int).tolist())
    if save_alerts:
        existing = {a.reading_id for a in Alert.query.all() if a.reading_id}
        by_id = {int(r.reading_id): r for r in frame.itertuples()}
        for rid in flagged - existing:
            r = by_id.get(rid)
            if r:
                severity = "High" if r.consumption_l > 90 else "Medium"
                db.session.add(Alert(reading_id=rid, timestamp=r.timestamp, zone=r.zone, severity=severity,
                                    message=f"Unusual water flow detected: {r.consumption_l:.1f} L recorded. Inspect meter and nearby pipes."))
        db.session.commit()
    return sorted(flagged)


def forecast_daily(days=7, zone="All zones"):
    frame = readings_frame(zone=zone)
    if frame.empty:
        return []
    daily = frame.set_index("timestamp").resample("D")["consumption_l"].sum().dropna()
    if len(daily) < 8:
        return []
    data = pd.DataFrame({"y": daily.values})
    data["lag1"] = data.y.shift(1)
    data["lag2"] = data.y.shift(2)
    data["lag7"] = data.y.shift(7)
    data["day"] = np.arange(len(data)) % 7
    train = data.dropna()
    if len(train) < 5:
        return []
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(train[["lag1", "lag2", "lag7", "day"]], train.y)
    history = list(daily.values)
    out = []
    last_date = daily.index[-1]
    for i in range(1, days + 1):
        features = [[history[-1], history[-2], history[-7] if len(history) >= 7 else history[-1], (len(history)) % 7]]
        pred = max(0, float(model.predict(features)[0]))
        history.append(pred)
        out.append({"date": (last_date + timedelta(days=i)).strftime("%Y-%m-%d"), "value": round(pred, 1)})
    return out


def dashboard_stats(zone="All zones"):
    frame = readings_frame(zone=zone)
    if frame.empty:
        return {"total": 0, "average": 0, "readings": 0, "alerts": 0, "zones": 0}
    alerts = Alert.query.filter_by(status="Open")
    if zone != "All zones":
        alerts = alerts.filter_by(zone=zone)
    return {"total": round(float(frame.consumption_l.sum()), 1),
            "average": round(float(frame.groupby(frame.timestamp.dt.date).consumption_l.sum().mean()), 1),
            "readings": len(frame), "alerts": alerts.count(), "zones": frame.zone.nunique()}


def import_csv(file_storage):
    raw = pd.read_csv(file_storage)
    required = {"timestamp", "zone", "meter_id", "consumption_l", "flow_rate"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError("CSV must contain columns: timestamp, zone, meter_id, consumption_l, flow_rate. Missing: " + ", ".join(sorted(missing)))
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    raw["consumption_l"] = pd.to_numeric(raw["consumption_l"], errors="coerce")
    raw["flow_rate"] = pd.to_numeric(raw["flow_rate"], errors="coerce")
    raw = raw.dropna(subset=["timestamp", "zone", "meter_id", "consumption_l", "flow_rate"])
    raw = raw[(raw.consumption_l >= 0) & (raw.flow_rate >= 0)].drop_duplicates(subset=["timestamp", "zone", "meter_id"])
    if raw.empty:
        raise ValueError("No valid rows found in the uploaded CSV.")
    for r in raw.itertuples():
        db.session.add(Reading(timestamp=r.timestamp.to_pydatetime(), zone=str(r.zone)[:60], meter_id=str(r.meter_id)[:60],
                               consumer_type=str(getattr(r, "consumer_type", "Household"))[:40],
                               consumption_l=float(r.consumption_l), flow_rate=float(r.flow_rate)))
    db.session.commit()
    run_leak_detection(save_alerts=True)
    return len(raw)
