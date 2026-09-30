import os
import secrets
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import africastalking

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart_farm_secret_key_2026_x89z')

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
USERNAME = os.environ.get('AT_USERNAME', 'sandbox')
API_KEY = os.environ.get('AT_API_KEY', 'your_africastalking_api_key')
africastalking.initialize(USERNAME, API_KEY)
sms = africastalking.SMS

OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '2ad63a80db9d993fc4d960e0d7992651')

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='farmer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Subscriber(db.Model):
    __tablename__ = 'subscribers'
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farms.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ==================== FORECAST & EARLY WARNING LOGIC ====================

def fetch_weather_forecast(location_name):
    if not location_name:
        return None
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={location_name}&appid={OPENWEATHER_API_KEY}&units=metric&lang=sw"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            forecast_list = []
            for item in data.get('list', [])[:8]: # Masaa 24 yajayo (3x8)
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

def generate_early_warnings(forecast_list):
    warnings = []
    if not forecast_list:
        return ["ℹ️ Hakuna utabiri wa kimataifa uliopatikana kwa eneo hili."]

    total_rain = sum([f['rain'] for f in forecast_list])
    max_wind = max([f['wind'] for f in forecast_list])
    max_temp = max([f['temp'] for f in forecast_list])

    if total_rain >= 15.0:
        warnings.append(f"🌧️ TAHADHARI YA MVUA KUBWA: Mvua ya takriban {round(total_rain, 1)}mm inatarajiwa masaa 24 yajayo. Safisha mifereji ya shamba na sitisha upuliziaji dawa.")
    
    if max_wind >= 20.0:
        warnings.append(f"💨 TAHADHARI YA UPEPO MKALI: Upepo wa hadi {max_wind} km/h unatarajiwa. Usipulizie dawa au mbolea ya maji.")

    if max_temp >= 34.0:
        warnings.append(f"☀️ TAHADHARI YA JOTO KALI: Joto litafika {max_temp}°C. Hakikisha mfumo wa kumwagilia maji uko tayari kuzuia mazao kunyauka.")

    if not warnings:
        warnings.append("✅ Hali ya hewa inatarajiwa kuwa shwari bila hatari yoyote masaa 24 yajayo.")

    return warnings

def generate_agri_advisory(temp, hum, rain, wind):
    advisories = []
    if hum >= 80 and 20 <= temp <= 32:
        advisories.append("⚠ Tishio la Ukungu/Kuvu: Unyevu mwingi unaongeza hatari ya magonjwa. Epuka kumwagilia maji juu ya majani.")
    if temp >= 32 and hum <= 40:
        advisories.append("☀️ Joto Kali & Ukavu: Mazao yapo kwenye hatari ya kukauka. Hakikisha unamwagilia asubuhi au jioni mapema.")
    elif rain == 0 and hum < 50:
        advisories.append("💧 Ushauri wa Maji: Hakuna mvua iliyorekodiwa na hewa ni kavu. Inashauriwa kumwagilia shamba.")
    if wind >= 15:
        advisories.append("💨 Upepo Mkali: Usipulizie dawa ya wadudu kwani itapeperushwa na upepo.")
    elif rain > 5:
        advisories.append("🌧 Mvua Inanyesha: Usipulizie dawa kwani itaoshwa na mvua.")
    else:
        advisories.append("✅ Hali ya Hewa: Ni nzuri kwa upuliziaji wa dawa au mbolea ya maji.")
    return advisories

# ==================== ROUTING ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not username or not email or not password:
        return jsonify({'status': 'error', 'message': 'Jaza taarifa zote'}), 400

    if User.query.filter(User.username.ilike(username)).first():
        return jsonify({'status': 'error', 'message': 'Username tayari ipo'}), 400

    if User.query.filter(User.email.ilike(email)).first():
        return jsonify({'status': 'error', 'message': 'Email tayari ipo'}), 400

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    default_farm = Farm(name="Shamba la Kwanza", location="Tanga", user_id=new_user.id)
    db.session.add(default_farm)
    db.session.commit()

    default_station = Station(
        station_code=f"STATION_{default_farm.id:03d}",
        api_key=secrets.token_hex(16),
        farm_id=default_farm.id
    )
    db.session.add(default_station)
    db.session.commit()

    login_user(new_user)
    return jsonify({'status': 'success', 'message': 'Usajili umefanikiwa!'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    login_input = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    user = User.query.filter((User.username.ilike(login_input)) | (User.email.ilike(login_input))).first()
    if user and user.check_password(password):
        login_user(user)
        return jsonify({'status': 'success', 'message': 'Umeingia kikamilifu'})

    return jsonify({'status': 'error', 'message': 'Taarifa si sahihi'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'status': 'success', 'message': 'Umetoka'})

@app.route('/api/user-status', methods=['GET'])
def user_status():
    if current_user.is_authenticated:
        return jsonify({'logged_in': True, 'username': current_user.username, 'email': current_user.email})
    return jsonify({'logged_in': False})

@app.route('/api/farms', methods=['GET'])
@login_required
def get_farms():
    farms = Farm.query.filter_by(user_id=current_user.id).all()
    result = []
    for f in farms:
        st = Station.query.filter_by(farm_id=f.id).first()
        result.append({'id': f.id, 'name': f.name, 'location': f.location or 'Tanga', 'api_key': st.api_key if st else ''})
    return jsonify({'status': 'success', 'farms': result})

@app.route('/api/farms/add', methods=['POST'])
@login_required
def add_farm():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    location = (data.get('location') or 'Tanga').strip()

    if not name:
        return jsonify({'status': 'error', 'message': 'Ingiza jina la shamba'}), 400

    new_farm = Farm(name=name, location=location, user_id=current_user.id)
    db.session.add(new_farm)
    db.session.commit()

    new_station = Station(station_code=f"STATION_{new_farm.id:03d}", api_key=secrets.token_hex(16), farm_id=new_farm.id)
    db.session.add(new_station)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Shamba limeongezwa'})

@app.route('/api/get-data', methods=['GET'])
@login_required
def get_data():
    farm_id = request.args.get('farm_id', type=int)
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Shamba halikupatikana'}), 404

    station = Station.query.filter_by(farm_id=farm.id).first()
    if not station:
        return jsonify({'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0, 'wind_speed': 0, 'is_online': False, 'advisories': []})

    latest_log = WeatherLog.query.filter_by(station_id=station.id).order_by(WeatherLog.timestamp.desc()).first()
    is_online = station.last_seen and (datetime.utcnow() - station.last_seen) < timedelta(minutes=5)

    if not latest_log:
        return jsonify({
            'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0, 'wind_speed': 0,
            'is_online': is_online, 'last_updated': 'Hajawahi Kutuma', 'api_key': station.api_key,
            'advisories': ["Inasubiri data kutoka sensor ya ESP32..."]
        })

    advisories = generate_agri_advisory(latest_log.temperature, latest_log.humidity, latest_log.rain, latest_log.wind_speed)

    return jsonify({
        'status': 'success',
        'temperature': round(latest_log.temperature, 1),
        'humidity': round(latest_log.humidity, 1),
        'rain': round(latest_log.rain, 1),
        'wind_speed': round(latest_log.wind_speed, 1),
        'is_online': is_online,
        'last_updated': latest_log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'api_key': station.api_key,
        'advisories': advisories
    })

# --- FORECAST & EARLY WARNINGS ENDPOINT ---
@app.route('/api/forecast', methods=['GET'])
@login_required
def get_forecast():
    farm_id = request.args.get('farm_id', type=int)
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Shamba halikupatikana'}), 404

    forecast_data = fetch_weather_forecast(farm.location or "Tanga")
    early_warnings = generate_early_warnings(forecast_data)

    return jsonify({
        'status': 'success',
        'location': farm.location or 'Tanga',
        'early_warnings': early_warnings,
        'forecast': forecast_data or []
    })

@app.route('/update', methods=['POST'])
def update_weather():
    data = request.get_json() or {}
    api_key = data.get('api_key')

    station = Station.query.filter_by(api_key=api_key).first()
    if not station:
        return jsonify({'status': 'error', 'message': 'API Key si sahihi'}), 401

    temp = data.get('temperature')
    hum = data.get('humidity')
    rain = data.get('rain', 0.0)
    wind = data.get('wind_speed', 0.0)

    if temp is None or hum is None:
        return jsonify({'status': 'error', 'message': 'Data hazijakamilika'}), 400

    log = WeatherLog(station_id=station.id, temperature=temp, humidity=hum, rain=rain, wind_speed=wind)
    station.is_online = True
    station.last_seen = datetime.utcnow()

    db.session.add(log)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Data imepokewa'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
