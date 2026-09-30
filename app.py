import os
import secrets
import math
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# SMART FARM WEATHER STATION - BACKEND
# ============================================================
# Features:
# - User authentication
# - Multi-farm support
# - One or more weather stations per farm
# - ESP32 sensor ingestion
# - Temperature, humidity, rainfall, rain detection,
#   wind speed, wind direction, optional soil moisture
# - 24-hour forecast via OpenWeather
# - Early warnings
# - Agricultural decision support
# - Historical daily summaries
# - Bilingual SW/EN API responses
# - Farm crop context
# - Safer station API-key handling
#
# Old ESP32 payloads using:
# temperature, humidity, rain, wind_speed
# remain compatible.
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder="templates", static_folder="static")

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

database_url = os.environ.get("DATABASE_URL", "").strip()

if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url.startswith("postgresql://") and "+psycopg2" not in database_url:
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(BASE_DIR, "smart_farm.db")
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_SORT_KEYS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = None

OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()

# ============================================================
# TRANSLATIONS
# ============================================================

TRANSLATIONS = {
    "sw": {
        "auth_required": "Unatakiwa kuingia kwenye mfumo.",
        "invalid_credentials": "Username/email au nenosiri si sahihi.",
        "registration_ok": "Akaunti imetengenezwa kikamilifu.",
        "username_exists": "Username tayari inatumika.",
        "email_exists": "Email tayari inatumika.",
        "invalid_registration": "Username, email na nenosiri vinahitajika.",
        "weak_password": "Nenosiri lazima liwe na angalau herufi 6.",
        "farm_required": "Jina la shamba na eneo vinahitajika.",
        "farm_not_found": "Shamba halijapatikana.",
        "station_not_found": "Kituo cha hali ya hewa hakijapatikana.",
        "invalid_sensor_key": "Sensor API key si sahihi.",
        "invalid_sensor_data": "Data ya sensor si sahihi.",
        "no_data": "Hakuna data ya sensor bado.",
        "forecast_unavailable": "Utabiri haupatikani kwa sasa.",
        "safe_weather": "Hali ya hewa inaonekana kuwa tulivu kwa sasa.",
        "heavy_rain": "Mvua kubwa inatarajiwa. Epuka shughuli zinazoweza kuathiriwa na mvua na zingatia drainage.",
        "strong_wind": "Upepo mkali unatarajiwa. Epuka kunyunyizia dawa/pembejeo wakati upepo ni mkali.",
        "high_temp": "Joto kali linatarajiwa. Linda mimea dhidi ya stress ya joto na fuatilia unyevu wa udongo.",
        "light_rain": "Mvua ndogo imeonekana/imetabiriwa. Angalia unyevu wa udongo kabla ya kumwagilia.",
        "rain_now": "Mvua inaendelea/imeonekana kwenye kituo.",
        "irrigation": "Hakuna mvua na unyevu wa hewa ni mdogo; kagua unyevu wa udongo kabla ya kuamua kumwagilia.",
        "irrigation_soil": "Unyevu wa udongo ni mdogo; zingatia umwagiliaji ikiwa hali ya mmea na ratiba ya shamba inaruhusu.",
        "wet_soil": "Unyevu wa udongo ni mkubwa; epuka kumwagilia zaidi bila sababu.",
        "fungus_risk": "Joto na unyevu vinaweza kuongeza mazingira ya magonjwa ya fangasi; kagua majani na mzunguko wa hewa.",
        "heat_dry": "Joto ni kubwa na unyevu wa hewa ni mdogo; fuatilia dalili za stress ya maji.",
        "wind_now": "Upepo ni mkubwa kwa sasa; subiri hali itulie kabla ya kunyunyizia.",
        "good_weather": "Hali ya sasa haijaonyesha hatari kubwa kulingana na vigezo vya mfumo.",
        "crop_advice": "Ushauri huu ni wa jumla; rekebisha uamuzi kulingana na aina ya zao, hatua ya ukuaji na hali halisi ya shamba.",
        "history_empty": "Hakuna historia ya kutosha.",
        "online": "ONLINE",
        "offline": "OFFLINE",
        "station_never_seen": "Kituo hakijawahi kutuma data.",
        "farm_added": "Shamba limeongezwa.",
        "farm_updated": "Taarifa za shamba zimebadilishwa.",
        "farm_deleted": "Shamba limefutwa.",
        "cannot_delete_last_farm": "Mfumo unahitaji angalau shamba moja.",
        "station_key_generated": "Station API key imetengenezwa.",
    },
    "en": {
        "auth_required": "You must be logged in.",
        "invalid_credentials": "Username/email or password is incorrect.",
        "registration_ok": "Account created successfully.",
        "username_exists": "Username is already in use.",
        "email_exists": "Email is already in use.",
        "invalid_registration": "Username, email and password are required.",
        "weak_password": "Password must contain at least 6 characters.",
        "farm_required": "Farm name and location are required.",
        "farm_not_found": "Farm was not found.",
        "station_not_found": "Weather station was not found.",
        "invalid_sensor_key": "Invalid sensor API key.",
        "invalid_sensor_data": "Invalid sensor data.",
        "no_data": "No sensor data available yet.",
        "forecast_unavailable": "Forecast is currently unavailable.",
        "safe_weather": "Current weather appears generally stable.",
        "heavy_rain": "Heavy rain is expected. Avoid rain-sensitive activities and check drainage.",
        "strong_wind": "Strong winds are expected. Avoid spraying pesticides or inputs during strong winds.",
        "high_temp": "High temperature is expected. Protect crops from heat stress and monitor soil moisture.",
        "light_rain": "Light rain has been observed/forecast. Check soil moisture before irrigating.",
        "rain_now": "Rain is currently being detected/has recently been detected.",
        "irrigation": "No rain and low air humidity; check soil moisture before deciding to irrigate.",
        "irrigation_soil": "Soil moisture is low; consider irrigation if crop condition and farm schedule allow.",
        "wet_soil": "Soil moisture is high; avoid unnecessary irrigation.",
        "fungus_risk": "Temperature and humidity may create favorable conditions for fungal disease; inspect crops and airflow.",
        "heat_dry": "Temperature is high and air humidity is low; monitor signs of water stress.",
        "wind_now": "Wind is currently strong; wait for calmer conditions before spraying.",
        "good_weather": "No major risk was detected from the current rule-based indicators.",
        "crop_advice": "This is general decision support; adjust decisions to crop type, growth stage and actual field conditions.",
        "history_empty": "Not enough historical data.",
        "online": "ONLINE",
        "offline": "OFFLINE",
        "station_never_seen": "The station has never sent data.",
        "farm_added": "Farm added.",
        "farm_updated": "Farm details updated.",
        "farm_deleted": "Farm deleted.",
        "cannot_delete_last_farm": "The system requires at least one farm.",
        "station_key_generated": "Station API key generated.",
    }
}


def t(key, lang="sw"):
    lang = lang if lang in TRANSLATIONS else "sw"
    return TRANSLATIONS[lang].get(key, key)


def get_lang():
    lang = request.args.get("lang", "sw").lower()
    return lang if lang in ("sw", "en") else "sw"


# ============================================================
# MODELS
# ============================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="farmer", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    farms = db.relationship(
        "Farm",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Farm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(160), nullable=False)
    crop_type = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    stations = db.relationship(
        "Station",
        backref="farm",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    station_code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    api_key = db.Column(db.String(128), unique=True, nullable=False, index=True)

    farm_id = db.Column(db.Integer, db.ForeignKey("farm.id"), nullable=False)

    is_online = db.Column(db.Boolean, default=False, nullable=False)
    last_seen = db.Column(db.DateTime, nullable=True)

    logs = db.relationship(
        "WeatherLog",
        backref="station",
        lazy=True,
        cascade="all, delete-orphan"
    )


class WeatherLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    station_id = db.Column(db.Integer, db.ForeignKey("station.id"), nullable=False, index=True)

    temperature = db.Column(db.Float, nullable=True)
    humidity = db.Column(db.Float, nullable=True)

    # Existing ESP32 field retained for compatibility.
    rain = db.Column(db.Float, default=0.0)

    # New fields.
    rain_detected = db.Column(db.Boolean, default=False, nullable=False)
    wind_speed = db.Column(db.Float, default=0.0)
    wind_direction = db.Column(db.Float, nullable=True)
    soil_moisture = db.Column(db.Float, nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


# ============================================================
# DATABASE COMPATIBILITY / LIGHTWEIGHT MIGRATION
# ============================================================

def ensure_schema():
    """
    db.create_all() creates missing tables but does not add new columns
    to an existing SQLite table. This lightweight migration adds the
    new optional columns if an older database is already present.
    """
    db.create_all()

    engine = db.engine

    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.connect() as conn:
        inspector = db.inspect(engine)

        weather_columns = {
            col["name"] for col in inspector.get_columns("weather_log")
        }
        farm_columns = {
            col["name"] for col in inspector.get_columns("farm")
        }

        additions = []

        if "rain_detected" not in weather_columns:
            additions.append(
                "ALTER TABLE weather_log ADD COLUMN rain_detected BOOLEAN DEFAULT 0"
            )
        if "wind_direction" not in weather_columns:
            additions.append(
                "ALTER TABLE weather_log ADD COLUMN wind_direction FLOAT"
            )
        if "soil_moisture" not in weather_columns:
            additions.append(
                "ALTER TABLE weather_log ADD COLUMN soil_moisture FLOAT"
            )
        if "crop_type" not in farm_columns:
            additions.append(
                "ALTER TABLE farm ADD COLUMN crop_type VARCHAR(120)"
            )

        for sql in additions:
            conn.exec_driver_sql(sql)

        conn.commit()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ============================================================
# HELPERS
# ============================================================

def json_number(value, digits=1):
    if value is None:
        return None
    try:
        value = float(value)
        if not math.isfinite(value):
            return None
        return round(value, digits)
    except (TypeError, ValueError):
        return None


def parse_optional_float(value, min_value=None, max_value=None):
    if value is None or value == "":
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid numeric value")

    if not math.isfinite(number):
        raise ValueError("Invalid numeric value")

    if min_value is not None and number < min_value:
        raise ValueError("Value below allowed range")

    if max_value is not None and number > max_value:
        raise ValueError("Value above allowed range")

    return number


def iso_or_none(dt):
    return dt.isoformat() if dt else None


def format_datetime(dt, lang="sw"):
    if not dt:
        return t("station_never_seen", lang)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def farm_for_current_user(farm_id):
    try:
        farm_id = int(farm_id)
    except (TypeError, ValueError):
        return None

    return Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()


def first_station(farm):
    return Station.query.filter_by(farm_id=farm.id).order_by(Station.id.asc()).first()


def station_online(station):
    if not station or not station.last_seen:
        return False

    # Five-minute heartbeat window.
    return (datetime.utcnow() - station.last_seen) <= timedelta(minutes=5)


def latest_log(station):
    if not station:
        return None
    return (
        WeatherLog.query
        .filter_by(station_id=station.id)
        .order_by(WeatherLog.timestamp.desc())
        .first()
    )


def random_station_code():
    return "WS-" + secrets.token_hex(4).upper()


def random_api_key():
    return secrets.token_urlsafe(32)


def ensure_station_for_farm(farm):
    station = first_station(farm)
    if station:
        return station

    station = Station(
        station_code=random_station_code(),
        api_key=random_api_key(),
        farm_id=farm.id,
        is_online=False
    )
    db.session.add(station)
    db.session.commit()
    return station


def validate_station_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Payload must be JSON.")

    temperature = parse_optional_float(payload.get("temperature"), -60, 80)
    humidity = parse_optional_float(payload.get("humidity"), 0, 100)
    rain = parse_optional_float(
        payload.get("rain", payload.get("rain_amount", 0)),
        0,
        1000
    )
    wind_speed = parse_optional_float(payload.get("wind_speed"), 0, 250)
    wind_direction = parse_optional_float(
        payload.get("wind_direction"),
        0,
        360
    )
    soil_moisture = parse_optional_float(
        payload.get("soil_moisture"),
        0,
        100
    )

    rain_detected_raw = payload.get("rain_detected")

    if rain_detected_raw is None:
        rain_detected = bool(rain and rain > 0)
    elif isinstance(rain_detected_raw, bool):
        rain_detected = rain_detected_raw
    else:
        rain_detected = str(rain_detected_raw).lower() in (
            "1", "true", "yes", "rain", "mvua"
        )

    if all(v is None for v in (temperature, humidity, rain, wind_speed, wind_direction, soil_moisture)):
        raise ValueError("No valid sensor value supplied.")

    return {
        "temperature": temperature,
        "humidity": humidity,
        "rain": rain or 0.0,
        "rain_detected": rain_detected,
        "wind_speed": wind_speed or 0.0,
        "wind_direction": wind_direction,
        "soil_moisture": soil_moisture
    }


def direction_label(degrees, lang="sw"):
    if degrees is None:
        return None

    try:
        d = float(degrees) % 360
    except (TypeError, ValueError):
        return None

    labels_sw = [
        "Kaskazini", "Kaskazini-Mashariki", "Mashariki", "Kusini-Mashariki",
        "Kusini", "Kusini-Magharibi", "Magharibi", "Kaskazini-Magharibi"
    ]
    labels_en = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]

    index = int((d + 22.5) // 45) % 8
    return (labels_sw if lang == "sw" else labels_en)[index]


# ============================================================
# AGRICULTURAL DECISION ENGINE
# ============================================================

def generate_agri_advisory(farm, log, lang="sw"):
    if not log:
        return [t("no_data", lang)]

    advice = []

    temp = log.temperature
    humidity = log.humidity
    rain = log.rain or 0
    wind = log.wind_speed or 0
    soil = log.soil_moisture

    if log.rain_detected or rain > 0:
        if rain > 5:
            advice.append(t("heavy_rain", lang))
        else:
            advice.append(t("light_rain", lang))
    elif humidity is not None and humidity < 50:
        if soil is not None and soil < 35:
            advice.append(t("irrigation_soil", lang))
        else:
            advice.append(t("irrigation", lang))

    if soil is not None:
        if soil < 30:
            advice.append(t("irrigation_soil", lang))
        elif soil > 80:
            advice.append(t("wet_soil", lang))

    if (
        humidity is not None
        and temp is not None
        and humidity >= 80
        and 20 <= temp <= 32
    ):
        advice.append(t("fungus_risk", lang))

    if (
        temp is not None
        and humidity is not None
        and temp >= 32
        and humidity <= 40
    ):
        advice.append(t("heat_dry", lang))

    if wind >= 15:
        advice.append(t("wind_now", lang))

    # Crop context does not pretend to be a crop-disease expert.
    if farm.crop_type:
        advice.append(
            f"{'Zao' if lang == 'sw' else 'Crop'}: {farm.crop_type}. "
            + t("crop_advice", lang)
        )

    if not advice:
        advice.append(t("good_weather", lang))

    return advice


def generate_early_warnings(forecast, lang="sw"):
    if not forecast:
        return [t("forecast_unavailable", lang)]

    total_rain = sum((item.get("rain") or 0) for item in forecast)
    max_wind = max((item.get("wind_speed") or 0) for item in forecast)
    max_temp = max(
        (item.get("temp") for item in forecast if item.get("temp") is not None),
        default=None
    )

    warnings = []

    if total_rain >= 15:
        warnings.append(
            f"{t('heavy_rain', lang)} "
            f"{'Jumla' if lang == 'sw' else 'Total'}: {round(total_rain, 1)} mm."
        )

    if max_wind >= 20:
        warnings.append(
            f"{t('strong_wind', lang)} "
            f"{'Upepo' if lang == 'sw' else 'Wind'}: {round(max_wind, 1)} km/h."
        )

    if max_temp is not None and max_temp >= 34:
        warnings.append(
            f"{t('high_temp', lang)} "
            f"{'Joto' if lang == 'sw' else 'Temperature'}: {round(max_temp, 1)}°C."
        )

    if not warnings:
        warnings.append(t("safe_weather", lang))

    return warnings


def crop_forecast_advice(forecast, farm, lang="sw"):
    """
    Converts forecast values into simple action-oriented advice.
    This remains rule-based and deliberately avoids pretending to replace
    agronomic diagnosis.
    """
    if not forecast:
        return []

    advice = []

    rain_total = sum((x.get("rain") or 0) for x in forecast)
    max_wind = max((x.get("wind_speed") or 0) for x in forecast)
    max_temp = max(
        (x.get("temp") for x in forecast if x.get("temp") is not None),
        default=None
    )

    if rain_total >= 10:
        advice.append(
            "Tarajia mvua kabla ya kumwagilia." if lang == "sw"
            else "Consider delaying irrigation because rainfall is expected."
        )

    if max_wind >= 15:
        advice.append(
            "Panga kunyunyizia wakati upepo umetulia."
            if lang == "sw"
            else "Schedule spraying when wind conditions are calmer."
        )

    if max_temp is not None and max_temp >= 33:
        advice.append(
            "Fuatilia stress ya joto na upatikanaji wa maji."
            if lang == "sw"
            else "Monitor heat stress and water availability."
        )

    if not advice:
        advice.append(
            "Hakuna kizuizi kikubwa kilichoonekana kwenye utabiri wa saa 24."
            if lang == "sw"
            else "No major restriction was detected in the 24-hour forecast."
        )

    return advice


# ============================================================
# OPENWEATHER
# ============================================================

def fetch_weather_forecast(location_name, lang="sw"):
    if not OPENWEATHER_API_KEY:
        return None, "OPENWEATHER_API_KEY is not configured."

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "q": location_name,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "en" if lang == "en" else "en",
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return None, f"OpenWeather error: {response.status_code}"

        payload = response.json()
        entries = payload.get("list", [])[:8]

        forecast = []

        for item in entries:
            main = item.get("main", {})
            wind = item.get("wind", {})
            rain_data = item.get("rain", {})

            rain_3h = rain_data.get("3h", 0) or 0

            forecast.append({
                "time": item.get("dt_txt"),
                "temp": json_number(main.get("temp"), 1),
                "humidity": json_number(main.get("humidity"), 0),
                "desc": (
                    item.get("weather", [{}])[0].get("description")
                    or ""
                ),
                "icon": (
                    item.get("weather", [{}])[0].get("icon")
                    or "01d"
                ),
                "rain": json_number(rain_3h, 1),
                "wind_speed": json_number(
                    (wind.get("speed", 0) or 0) * 3.6, 1
                ),
                "wind_direction": json_number(wind.get("deg"), 0),
            })

        return forecast, None

    except requests.RequestException as exc:
        return None, str(exc)


# ============================================================
# ROUTES - WEB
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# ROUTES - AUTH
# ============================================================

@app.get("/api/user-status")
def user_status():
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "username": current_user.username,
            "email": current_user.email
        })

    return jsonify({"logged_in": False})


@app.post("/api/register")
def register():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or not email or not password:
        return jsonify({
            "status": "error",
            "message": t("invalid_registration", lang)
        }), 400

    if len(password) < 6:
        return jsonify({
            "status": "error",
            "message": t("weak_password", lang)
        }), 400

    if User.query.filter_by(username=username).first():
        return jsonify({
            "status": "error",
            "message": t("username_exists", lang)
        }), 409

    if User.query.filter_by(email=email).first():
        return jsonify({
            "status": "error",
            "message": t("email_exists", lang)
        }), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.flush()

    # Every new account starts with one farm so the dashboard is immediately usable.
    farm = Farm(
        name="Shamba Langu",
        location="Tanzania",
        crop_type="",
        user_id=user.id
    )
    db.session.add(farm)
    db.session.flush()

    station = Station(
        station_code=random_station_code(),
        api_key=random_api_key(),
        farm_id=farm.id
    )
    db.session.add(station)

    db.session.commit()

    login_user(user)

    return jsonify({
        "status": "success",
        "message": t("registration_ok", lang)
    }), 201


@app.post("/api/login")
def login():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    identity = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    user = (
        User.query.filter(
            (User.username == identity) |
            (User.email == identity.lower())
        ).first()
    )

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({
            "status": "error",
            "message": t("invalid_credentials", lang)
        }), 401

    login_user(user)

    return jsonify({
        "status": "success",
        "username": user.username
    })


@app.post("/api/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"status": "success"})


# ============================================================
# ROUTES - FARMS
# ============================================================

@app.get("/api/farms")
@login_required
def get_farms():
    farms = (
        Farm.query
        .filter_by(user_id=current_user.id)
        .order_by(Farm.created_at.asc())
        .all()
    )

    return jsonify({
        "status": "success",
        "farms": [
            {
                "id": farm.id,
                "name": farm.name,
                "location": farm.location,
                "crop_type": farm.crop_type or "",
                "created_at": iso_or_none(farm.created_at)
            }
            for farm in farms
        ]
    })


@app.post("/api/farms/add")
@login_required
def add_farm():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    location = str(data.get("location", "")).strip()
    crop_type = str(data.get("crop_type", "")).strip()

    if not name or not location:
        return jsonify({
            "status": "error",
            "message": t("farm_required", lang)
        }), 400

    farm = Farm(
        name=name,
        location=location,
        crop_type=crop_type,
        user_id=current_user.id
    )
    db.session.add(farm)
    db.session.flush()

    station = Station(
        station_code=random_station_code(),
        api_key=random_api_key(),
        farm_id=farm.id
    )
    db.session.add(station)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": t("farm_added", lang),
        "farm_id": farm.id,
        "station_code": station.station_code
    }), 201


@app.post("/api/farms/edit")
@login_required
def edit_farm():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    farm = farm_for_current_user(data.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    name = str(data.get("name", "")).strip()
    location = str(data.get("location", "")).strip()
    crop_type = str(data.get("crop_type", "")).strip()

    if not name or not location:
        return jsonify({
            "status": "error",
            "message": t("farm_required", lang)
        }), 400

    farm.name = name
    farm.location = location
    farm.crop_type = crop_type

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": t("farm_updated", lang)
    })


@app.post("/api/farms/delete")
@login_required
def delete_farm():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    farm = farm_for_current_user(data.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    count = Farm.query.filter_by(user_id=current_user.id).count()

    if count <= 1:
        return jsonify({
            "status": "error",
            "message": t("cannot_delete_last_farm", lang)
        }), 400

    db.session.delete(farm)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": t("farm_deleted", lang)
    })


# ============================================================
# ROUTES - STATION / SENSOR
# ============================================================

@app.get("/api/station")
@login_required
def station_info():
    lang = get_lang()
    farm = farm_for_current_user(request.args.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    station = ensure_station_for_farm(farm)

    return jsonify({
        "status": "success",
        "station": {
            "id": station.id,
            "station_code": station.station_code,
            "api_key": station.api_key,
            "is_online": station_online(station),
            "last_seen": format_datetime(station.last_seen, lang)
        }
    })


@app.post("/api/station/regenerate-key")
@login_required
def regenerate_station_key():
    lang = get_lang()
    data = request.get_json(silent=True) or {}

    farm = farm_for_current_user(data.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    station = ensure_station_for_farm(farm)
    station.api_key = random_api_key()
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": t("station_key_generated", lang),
        "api_key": station.api_key,
        "station_code": station.station_code
    })


@app.post("/update")
def update_sensor_data():
    """
    ESP32 endpoint.

    Required header:
        X-API-Key: station_api_key

    Compatible JSON examples:

    {
      "temperature": 28.5,
      "humidity": 72,
      "rain": 2.4,
      "wind_speed": 8.5,
      "wind_direction": 90,
      "soil_moisture": 44,
      "rain_detected": true
    }

    Old payloads without the new fields still work.
    """
    payload = request.get_json(silent=True) or {}

    api_key = (
        request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
        or payload.get("api_key")
    )

    if not api_key:
        return jsonify({
            "status": "error",
            "message": "Missing X-API-Key"
        }), 401

    station = Station.query.filter_by(api_key=str(api_key).strip()).first()

    if not station:
        return jsonify({
            "status": "error",
            "message": "Invalid API key"
        }), 401

    try:
        sensor_data = validate_station_payload(payload)
    except ValueError as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 400

    log = WeatherLog(
        station_id=station.id,
        temperature=sensor_data["temperature"],
        humidity=sensor_data["humidity"],
        rain=sensor_data["rain"],
        rain_detected=sensor_data["rain_detected"],
        wind_speed=sensor_data["wind_speed"],
        wind_direction=sensor_data["wind_direction"],
        soil_moisture=sensor_data["soil_moisture"],
        timestamp=datetime.utcnow()
    )

    station.is_online = True
    station.last_seen = datetime.utcnow()

    db.session.add(log)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Sensor data received.",
        "timestamp": log.timestamp.isoformat()
    })


# ============================================================
# ROUTES - DASHBOARD DATA
# ============================================================

@app.get("/api/get-data")
@login_required
def get_data():
    lang = get_lang()

    farm = farm_for_current_user(request.args.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    station = ensure_station_for_farm(farm)
    log = latest_log(station)

    if not log:
        return jsonify({
            "status": "success",
            "has_data": False,
            "farm": {
                "id": farm.id,
                "name": farm.name,
                "location": farm.location,
                "crop_type": farm.crop_type or ""
            },
            "station": {
                "station_code": station.station_code,
                "is_online": False,
                "last_seen": format_datetime(None, lang)
            },
            "message": t("no_data", lang),
            "advisories": [t("no_data", lang)]
        })

    online = station_online(station)

    return jsonify({
        "status": "success",
        "has_data": True,
        "farm": {
            "id": farm.id,
            "name": farm.name,
            "location": farm.location,
            "crop_type": farm.crop_type or ""
        },
        "station": {
            "station_code": station.station_code,
            "is_online": online,
            "last_seen": format_datetime(station.last_seen, lang)
        },
        "temperature": json_number(log.temperature, 1),
        "humidity": json_number(log.humidity, 0),
        "rain": json_number(log.rain, 1),
        "rain_detected": bool(log.rain_detected),
        "wind_speed": json_number(log.wind_speed, 1),
        "wind_direction": json_number(log.wind_direction, 0),
        "wind_direction_label": direction_label(log.wind_direction, lang),
        "soil_moisture": json_number(log.soil_moisture, 0),
        "last_updated": format_datetime(log.timestamp, lang),
        "advisories": generate_agri_advisory(farm, log, lang)
    })


# ============================================================
# ROUTES - FORECAST
# ============================================================

@app.get("/api/forecast")
@login_required
def forecast():
    lang = get_lang()

    farm = farm_for_current_user(request.args.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    forecast_data, error = fetch_weather_forecast(farm.location, lang)

    if forecast_data is None:
        return jsonify({
            "status": "error",
            "message": t("forecast_unavailable", lang),
            "detail": error
        }), 503

    return jsonify({
        "status": "success",
        "location": farm.location,
        "forecast": forecast_data,
        "early_warnings": generate_early_warnings(forecast_data, lang),
        "farming_actions": crop_forecast_advice(forecast_data, farm, lang)
    })


# ============================================================
# ROUTES - HISTORY
# ============================================================

@app.get("/api/history")
@login_required
def history():
    lang = get_lang()

    farm = farm_for_current_user(request.args.get("farm_id"))

    if not farm:
        return jsonify({
            "status": "error",
            "message": t("farm_not_found", lang)
        }), 404

    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        days = 7

    days = max(1, min(days, 90))

    station = first_station(farm)

    if not station:
        return jsonify({
            "status": "success",
            "days": [],
            "message": t("history_empty", lang)
        })

    since = datetime.utcnow() - timedelta(days=days)

    logs = (
        WeatherLog.query
        .filter(
            WeatherLog.station_id == station.id,
            WeatherLog.timestamp >= since
        )
        .order_by(WeatherLog.timestamp.asc())
        .all()
    )

    if not logs:
        return jsonify({
            "status": "success",
            "days": [],
            "message": t("history_empty", lang)
        })

    grouped = {}

    for log in logs:
        day = log.timestamp.strftime("%Y-%m-%d")
        grouped.setdefault(day, []).append(log)

    rows = []

    for day, items in grouped.items():
        temps = [x.temperature for x in items if x.temperature is not None]
        hums = [x.humidity for x in items if x.humidity is not None]
        rains = [x.rain or 0 for x in items]
        winds = [x.wind_speed or 0 for x in items]
        soils = [x.soil_moisture for x in items if x.soil_moisture is not None]

        rows.append({
            "date": day,
            "temperature_avg": json_number(
                sum(temps) / len(temps) if temps else None, 1
            ),
            "temperature_max": json_number(max(temps) if temps else None, 1),
            "temperature_min": json_number(min(temps) if temps else None, 1),
            "humidity_avg": json_number(
                sum(hums) / len(hums) if hums else None, 0
            ),
            "rain_total": json_number(sum(rains), 1),
            "wind_max": json_number(max(winds) if winds else None, 1),
            "soil_moisture_avg": json_number(
                sum(soils) / len(soils) if soils else None, 0
            ),
            "samples": len(items)
        })

    return jsonify({
        "status": "success",
        "days": rows
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Smart Farm Weather Station",
        "time": datetime.utcnow().isoformat()
    })


# ============================================================
# STARTUP
# ============================================================

with app.app_context():
    ensure_schema()


if __name__ == "__main__":
    # For production deployment, use a production WSGI server and
    # set DEBUG=false. Debug is intentionally disabled by default.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug
    )
