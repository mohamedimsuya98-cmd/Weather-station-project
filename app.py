import os
import secrets
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import africastalking

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# --- DATABASE CONFIGURATION ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///smart_farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- AFRICA'S TALKING & OPENWEATHER SETUP ---
AT_USERNAME = os.environ.get('AT_USERNAME', 'sandbox')
AT_API_KEY = os.environ.get('AT_API_KEY', '')
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')

sms = None
if AT_API_KEY:
    try:
        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        sms = africastalking.SMS
    except Exception as e:
        print(f"Africa's Talking Initialization Error: {e}")

# ==================== LANGUAGE & TRANSLATION SYSTEM ====================

TRANSLATIONS = {
    'sw': {
        'no_forecast': "ℹ️ Hakuna utabiri wa kimataifa uliopatikana kwa eneo hili.",
        'heavy_rain_warning': "🌧️ TAHADHARI YA MVUA KUBWA: Mvua ya takriban {rain}mm inatarajiwa masaa 24 yajayo. Safisha mifereji ya shamba na sitisha upuliziaji dawa.",
        'strong_wind_warning': "💨 TAHADHARI YA UPEPO MKALI: Upepo wa hadi {wind} km/h unatarajiwa. Usipulizie dawa au mbolea ya maji.",
        'high_temp_warning': "☀️ TAHADHARI YA JOTO KALI: Joto litafika {temp}°C. Hakikisha mfumo wa kumwagilia maji uko tayari kuzuia mazao kunyauka.",
        'safe_weather': "✅ Hali ya hewa inatarajiwa kuwa shwari bila hatari yoyote masaa 24 yajayo.",
        'fungus_risk': "⚠ Tishio la Ukungu/Kuvu: Unyevu mwingi unaongeza hatari ya magonjwa. Epuka kumwagilia maji juu ya majani.",
        'heat_dry_risk': "☀️ Joto Kali & Ukavu: Mazao yapo kwenye hatari ya kukauka. Hakikisha unamwagilia asubuhi au jioni mapema.",
        'irrigation_advise': "💧 Ushauri wa Maji: Hakuna mvua iliyorekodiwa na hewa ni kavu. Inashauriwa kumwagilia shamba.",
        'wind_advise': "💨 Upepo Mkali: Usipulizie dawa ya wadudu kwani itapeperushwa na upepo.",
        'rain_advise_heavy': "🌧 Mvua Kubwa Inanyesha ({rain}mm): Sitisha upuliziaji wa dawa/mbolea na hakikisha mifereji haijaziba.",
        'rain_advise_light': "🌧 Mvua Kidogo Inanyesha ({rain}mm): Usipulizie dawa ya maji kwani itaoshwa na mvua.",
        'good_weather': "✅ Hali ya Hewa: Ni nzuri kwa upuliziaji wa dawa au mbolea ya maji.",
        'no_data': "Inasubiri data kutoka sensor ya ESP32...",
        'rain_none': "Hakuna Mvua",
        'rain_light': "Mvua Kidogo",
        'rain_heavy': "Mvua Kubwa",
        'never_updated': "Hajawahi Kutuma",
        'farm_not_found': "Shamba halikupatikana"
    },
    'en': {
        'no_forecast': "ℹ️ No global forecast available for this location.",
        'heavy_rain_warning': "🌧️ HEAVY RAIN WARNING: Heavy rain of approx {rain}mm expected in next 24 hours. Clear farm drainage and pause spraying.",
        'strong_wind_warning': "💨 STRONG WIND WARNING: Winds up to {wind} km/h expected. Avoid spraying pesticides or liquid fertilizer.",
        'high_temp_warning': "☀️ EXTREME HEAT WARNING: Temperatures reaching {temp}°C. Ensure irrigation system is ready to prevent crop wilting.",
        'safe_weather': "✅ Weather is expected to be clear with no warnings for the next 24 hours.",
        'fungus_risk': "⚠ Fungal/Blight Risk: High humidity increases disease risk. Avoid overhead watering.",
        'heat_dry_risk': "☀️ Extreme Heat & Dryness: Crops are at risk of wilting. Irrigate during early morning or late evening.",
        'irrigation_advise': "💧 Irrigation Advisory: No rain recorded and air is dry. Irrigation is recommended.",
        'wind_advise': "💨 Strong Wind: Do not spray pesticides as chemicals will drift.",
        'rain_advise_heavy': "🌧 Heavy Rain Falling ({rain}mm): Stop spraying pesticides/fertilizer and ensure field drainage is clear.",
        'rain_advise_light': "🌧 Light Rain Falling ({rain}mm): Avoid liquid spraying as rain will wash it off.",
        'good_weather': "✅ Fair Weather: Good conditions for spraying pesticides or liquid fertilizer.",
        'no_data': "Waiting for data from ESP32 sensor...",
        'rain_none': "No Rain",
        'rain_light': "Light Rain",
        'rain_heavy': "Heavy Rain",
        'never_updated': "Never Received",
        'farm_not_found': "Farm not found"
    }
}

def t(key, lang='sw', **kwargs):
    """Helper function to retrieve translated text."""
    language = lang if lang in TRANSLATIONS else 'sw'
    text = TRANSLATIONS[language].get(key, TRANSLATIONS['sw'].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='farmer')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    farms = db.relationship('Farm', backref='owner', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Farm(db.Model):
    __tablename__ = 'farms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    stations = db.relationship('Station', backref='farm', lazy=True, cascade="all, delete-orphan")
    subscribers = db.relationship('Subscriber', backref='farm', lazy=True, cascade="all, delete-orphan")


class Station(db.Model):
    __tablename__ = 'stations'
    id = db.Column(db.Integer, primary_key=True)
    station_code = db.Column(db.String(50), unique=True, nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, nullable=True)

    logs = db.relationship('WeatherLog', backref='station', lazy=True, cascade="all, delete-orphan")


class WeatherLog(db.Model):
    __tablename__ = 'weather_logs'
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    rain = db.Column(db.Float, default=0.0)
    wind_speed = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Subscriber(db.Model):
    __tablename__ = 'subscribers'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# ==================== FORECAST & EARLY WARNING LOGIC ====================

def fetch_weather_forecast(location_name, lang='sw'):
    if not location_name or not OPENWEATHER_API_KEY:
        return None
    try:
        api_lang = 'sw' if lang == 'sw' else 'en'
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={location_name}&appid={OPENWEATHER_API_KEY}&units=metric&lang={api_lang}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            forecast_list = []
            for item in data.get('list', [])[:8]: # Next 24 hours
                forecast_list.append({
                    'time': item.get('dt_txt'),
                    'temp': round(item['main']['temp'], 1),
                    'humidity': item['main']['humidity'],
                    'desc': item['weather'][0]['description'].capitalize(),
                    'icon': item['weather'][0]['icon'],
                    'rain': item.get('rain', {}).get('3h', 0.0),
                    'wind': round(item['wind']['speed'] * 3.6, 1) # m/s to km/h
                })
            return forecast_list
    except Exception as e:
        print(f"Forecast Error: {e}")
    return None

def generate_early_warnings(forecast_list, lang='sw'):
    warnings = []
    if not forecast_list:
        return [t('no_forecast', lang)]

    total_rain = sum([f['rain'] for f in forecast_list])
    max_wind = max([f['wind'] for f in forecast_list])
    max_temp = max([f['temp'] for f in forecast_list])

    if total_rain >= 15.0:
        warnings.append(t('heavy_rain_warning', lang, rain=round(total_rain, 1)))
    
    if max_wind >= 20.0:
        warnings.append(t('strong_wind_warning', lang, wind=max_wind))

    if max_temp >= 34.0:
        warnings.append(t('high_temp_warning', lang, temp=max_temp))

    if not warnings:
        warnings.append(t('safe_weather', lang))

    return warnings

def generate_agri_advisory(temp, hum, rain, wind, lang='sw'):
    advisories = []
    
    # Check Rain Sensor reading
    if rain > 5.0:
        advisories.append(t('rain_advise_heavy', lang, rain=round(rain, 1)))
    elif rain > 0.0:
        advisories.append(t('rain_advise_light', lang, rain=round(rain, 1)))
    elif rain == 0.0 and hum < 50:
        advisories.append(t('irrigation_advise', lang))

    # Check humidity & temperature risks
    if hum >= 80 and 20 <= temp <= 32:
        advisories.append(t('fungus_risk', lang))
    if temp >= 32 and hum <= 40:
        advisories.append(t('heat_dry_risk', lang))

    # Check wind speed
    if wind >= 15:
        advisories.append(t('wind_advise', lang))

    if not advisories:
        advisories.append(t('good_weather', lang))

    return advisories

# ==================== ROUTING ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get-data', methods=['GET'])
@login_required
def get_data():
    farm_id = request.args.get('farm_id', type=int)
    lang = request.args.get('lang', 'sw')  # 'sw' or 'en'
    
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': t('farm_not_found', lang)}), 404

    station = Station.query.filter_by(farm_id=farm.id).first()
    if not station:
        return jsonify({
            'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0,
            'rain_status': t('rain_none', lang), 'wind_speed': 0, 'is_online': False, 'advisories': []
        })

    latest_log = WeatherLog.query.filter_by(station_id=station.id).order_by(WeatherLog.timestamp.desc()).first()
    now_utc = datetime.now(timezone.utc)
    
    is_online = False
    if station.last_seen:
        last_seen_aware = station.last_seen if station.last_seen.tzinfo else station.last_seen.replace(tzinfo=timezone.utc)
        is_online = (now_utc - last_seen_aware) < timedelta(minutes=5)

    if not latest_log:
        return jsonify({
            'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0,
            'rain_status': t('rain_none', lang), 'wind_speed': 0,
            'is_online': is_online, 'last_updated': t('never_updated', lang), 'api_key': station.api_key,
            'advisories': [t('no_data', lang)]
        })

    # Rain sensor classification
    if latest_log.rain > 5.0:
        rain_status = t('rain_heavy', lang)
    elif latest_log.rain > 0.0:
        rain_status = t('rain_light', lang)
    else:
        rain_status = t('rain_none', lang)

    advisories = generate_agri_advisory(latest_log.temperature, latest_log.humidity, latest_log.rain, latest_log.wind_speed, lang=lang)

    return jsonify({
        'status': 'success',
        'temperature': round(latest_log.temperature, 1),
        'humidity': round(latest_log.humidity, 1),
        'rain': round(latest_log.rain, 1),
        'rain_status': rain_status,
        'wind_speed': round(latest_log.wind_speed, 1),
        'is_online': is_online,
        'last_updated': latest_log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'api_key': station.api_key,
        'advisories': advisories
    })

@app.route('/api/forecast', methods=['GET'])
@login_required
def get_forecast():
    farm_id = request.args.get('farm_id', type=int)
    lang = request.args.get('lang', 'sw')  # 'sw' or 'en'
    
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': t('farm_not_found', lang)}), 404

    forecast_data = fetch_weather_forecast(farm.location or "Tanga", lang=lang)
    early_warnings = generate_early_warnings(forecast_data, lang=lang)

    return jsonify({
        'status': 'success',
        'location': farm.location or 'Tanga',
        'early_warnings': early_warnings,
        'forecast': forecast_data or []
    })

@app.route('/update', methods=['POST'])
def update_weather():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({'status': 'error', 'message': 'API Key is required'}), 400

    station = Station.query.filter_by(api_key=api_key).first()
    if not station:
        return jsonify({'status': 'error', 'message': 'Invalid API Key'}), 401

    try:
        temp = float(data.get('temperature'))
        hum = float(data.get('humidity'))
        rain = float(data.get('rain', 0.0)) # Receives rain sensor data
        wind = float(data.get('wind_speed', 0.0))
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid sensor data format'}), 400

    log = WeatherLog(station_id=station.id, temperature=temp, humidity=hum, rain=rain, wind_speed=wind)
    station.is_online = True
    station.last_seen = datetime.now(timezone.utc)

    db.session.add(log)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Data received successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
