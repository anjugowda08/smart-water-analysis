from datetime import datetime, timedelta
import csv, io
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
from app import db
from app.models import Reading, Alert
from app.services import (ZONES, readings_frame, dashboard_stats, forecast_daily,
                          run_leak_detection, import_csv)

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    return redirect(url_for("auth.login"))

@main_bp.route("/dashboard")
@login_required
def dashboard():
    zone = request.args.get("zone", "All zones")
    if zone not in ["All zones"] + ZONES:
        zone = "All zones"
    stats = dashboard_stats(zone)
    frame = readings_frame(zone=zone)
    daily = []
    hourly = []
    weekday = []
    if not frame.empty:
        d = frame.set_index("timestamp").resample("D").consumption_l.sum().tail(14)
        daily = [{"label": x.strftime("%d %b"), "value": round(float(y), 1)} for x, y in d.items()]
        h = frame.assign(hour=frame.timestamp.dt.hour).groupby("hour").consumption_l.mean()
        hourly = [{"label": f"{int(x):02d}:00", "value": round(float(y), 1)} for x, y in h.items()]
        w = frame.assign(day=frame.timestamp.dt.day_name()).groupby("day").consumption_l.mean()
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = [{"label": x, "value": round(float(w[x]), 1)} for x in order if x in w]
    recent_alerts = Alert.query.filter_by(status="Open")
    if zone != "All zones":
        recent_alerts = recent_alerts.filter_by(zone=zone)
    recent_alerts = recent_alerts.order_by(Alert.timestamp.desc()).limit(5).all()
    return render_template("dashboard.html", stats=stats, zones=ZONES, selected_zone=zone,
                           daily=daily, hourly=hourly, weekday=weekday, alerts=recent_alerts,
                           forecasts=forecast_daily(7, zone))

@main_bp.route("/readings")
@login_required
def readings():
    zone = request.args.get("zone", "All zones")
    q = Reading.query
    if zone != "All zones" and zone in ZONES:
        q = q.filter_by(zone=zone)
    records = q.order_by(Reading.timestamp.desc()).limit(500).all()
    return render_template("readings.html", readings=records, zones=ZONES, selected_zone=zone)

@main_bp.route("/readings/add", methods=["POST"])
@login_required
def add_reading():
    try:
        timestamp = datetime.fromisoformat(request.form["timestamp"])
        zone = request.form["zone"]
        consumption = float(request.form["consumption_l"])
        flow = float(request.form["flow_rate"])
        meter = request.form["meter_id"].strip()
        if zone not in ZONES or not meter or consumption < 0 or flow < 0:
            raise ValueError("Enter a valid zone, meter ID and non-negative readings.")
        item = Reading(timestamp=timestamp, zone=zone, meter_id=meter, consumption_l=consumption,
                       flow_rate=flow, consumer_type=request.form.get("consumer_type", "Household"))
        db.session.add(item); db.session.commit()
        run_leak_detection(save_alerts=True)
        flash("Water reading added successfully.", "success")
    except (ValueError, KeyError):
        db.session.rollback(); flash("Please enter valid reading details. Consumption and flow must be non-negative.", "danger")
    return redirect(url_for("main.readings"))

@main_bp.route("/readings/<int:reading_id>/edit", methods=["GET", "POST"])
@login_required
def edit_reading(reading_id):
    item = db.session.get(Reading, reading_id)
    if not item:
        flash("Reading not found.", "danger")
        return redirect(url_for("main.readings"))
    if request.method == "POST":
        try:
            timestamp = datetime.fromisoformat(request.form["timestamp"])
            zone = request.form["zone"]
            consumption = float(request.form["consumption_l"])
            flow = float(request.form["flow_rate"])
            meter = request.form["meter_id"].strip()
            if zone not in ZONES or not meter or consumption < 0 or flow < 0:
                raise ValueError
            item.timestamp = timestamp
            item.zone = zone
            item.meter_id = meter
            item.consumption_l = consumption
            item.flow_rate = flow
            item.consumer_type = request.form.get("consumer_type", "Household")
            Alert.query.filter_by(reading_id=item.id).delete()
            db.session.commit()
            run_leak_detection(save_alerts=True)
            flash("Reading updated successfully.", "success")
            return redirect(url_for("main.readings"))
        except (ValueError, KeyError):
            db.session.rollback()
            flash("Please enter valid reading details.", "danger")
    return render_template("edit_reading.html", reading=item, zones=ZONES)

@main_bp.route("/readings/<int:reading_id>/delete", methods=["POST"])
@login_required
def delete_reading(reading_id):
    item = db.session.get(Reading, reading_id)
    if item:
        Alert.query.filter_by(reading_id=item.id).delete()
        db.session.delete(item); db.session.commit()
        flash("Reading deleted.", "success")
    else:
        flash("Reading not found.", "danger")
    return redirect(url_for("main.readings"))

@main_bp.route("/alerts")
@login_required
def alerts():
    items = Alert.query.order_by(Alert.timestamp.desc()).limit(300).all()
    return render_template("alerts.html", alerts=items)

@main_bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@login_required
def resolve_alert(alert_id):
    alert = db.session.get(Alert, alert_id)
    if alert:
        alert.status = "Resolved"; db.session.commit()
        flash("Alert marked as resolved.", "success")
    else:
        flash("Alert not found.", "danger")
    return redirect(url_for("main.alerts"))

@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please select a CSV file.", "danger")
        else:
            try:
                count = import_csv(file)
                flash(f"Imported {count} valid readings and refreshed leakage alerts.", "success")
                return redirect(url_for("main.readings"))
            except Exception as exc:
                db.session.rollback(); flash(str(exc), "danger")
    return render_template("upload.html")

@main_bp.route("/export.csv")
@login_required
def export_csv():
    zone = request.args.get("zone", "All zones")
    q = Reading.query
    if zone != "All zones":
        q = q.filter_by(zone=zone)
    records = q.order_by(Reading.timestamp.asc()).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["timestamp", "zone", "meter_id", "consumption_l", "flow_rate"])
    for r in records:
        writer.writerow([r.timestamp.isoformat(sep=" "), r.zone, r.meter_id, r.consumption_l, r.flow_rate])
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=water_readings.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

@main_bp.route("/api/summary")
@login_required
def api_summary():
    zone = request.args.get("zone", "All zones")
    return jsonify(dashboard_stats(zone))

@main_bp.route("/api/forecast")
@login_required
def api_forecast():
    return jsonify(forecast_daily(7, request.args.get("zone", "All zones")))
