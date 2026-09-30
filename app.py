import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import africastalking

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart_farm_secret_key_2026_x89z')

# --- DATABASE CONFIGURATION (PostgreSQL / SQLite) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///smart_farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- AFRICA'S TALKING SETUP ---
USERNAME = os.environ.get('AT_USERNAME', 'sandbox')
API_KEY = os.environ.get('AT_API_KEY', 'your_africastalking_api_key')
africastalking.initialize(USERNAME, API_KEY)
sms = africastalking.SMS

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

# --- AUTO-CREATE DATABASE TABLES ---
with app.app_context():
    db.create_all()

# ==================== AGRI-ADVISORY LOGIC ====================

def generate_agri_advisory(temp, hum, rain, wind):
    advisories = []

    # 1. Tishio la Ukungu / Kuvu
    if hum >= 80 and 20 <= temp <= 32:
        advisories.append("⚠ Tishio la Ukungu/Kuvu: Unyevu mwingi unaongeza hatari ya magonjwa ya majani. Epuka kumwagilia maji juu ya majani.")

    # 2. Joto Kali na Uwagiliaji
    if temp >= 32 and hum <= 40:
        advisories.append("☀️ Joto Kali & Ukavu: Mazao yapo kwenye hatari ya kukauka. Hakikisha unamwagilia asubuhi au jioni mapema.")
    elif rain == 0 and hum < 50:
        advisories.append("💧 Ushauri wa Maji: Hakuna mvua iliyorekodiwa na hewa ni kavu. Inashauriwa kumwagilia shamba.")

    # 3. Ushauri wa Kupuliza Dawa / Mbolea
    if wind >= 15:
        advisories.append("💨 Upepo Mkali: Usipulizie dawa ya wadudu au mbolea kwa sasa kwani itapeperushwa na upepo.")
    elif rain > 5:
        advisories.append("🌧️ Mvua Inanyesha: Usipulizie dawa kwani itaoshwa na mvua na kupotea.")
    else:
        advisories.append("✅ Hali ya Hewa: Ni nzuri kwa upuliziaji wa dawa au mbolea ya maji kama inahitajika.")

    # 4. Mvua Kubwa
    if rain >= 20:
        advisories.append("🌊 Mvua Kubwa: Hakikisha mifereji ya kutoa maji shambani ni wazi ili kuzuia maji kutuama kwenye mizizi.")

    if not advisories:
        advisories.append("🌱 Hali ya hewa ipo katika kiwango salama kwa ukuaji wa mazao.")

    return advisories

# ==================== ROUTING ZA MFUMO ====================

@app.route('/')
def index():
    return render_template('index.html')

# --- AUTHENTICATION ENDPOINTS ---

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'status': 'error', 'message': 'Jaza taarifa zote zinazotakiwa'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'error', 'message': 'Jina hili la mtumiaji tayari linatumika'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'status': 'error', 'message': 'Barua pepe hii tayari imesajiliwa'}), 400

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    # Tengeneza Shamba la Kwanza la Mfano
    default_farm = Farm(name="Shamba la Kwanza", location="Kuu", user_id=new_user.id)
    db.session.add(default_farm)
    db.session.commit()

    # Tengeneza Kituo cha Sensor cha Mfano kwa ajili ya ESP32
    default_station = Station(
        station_code=f"STATION_{default_farm.id:03d}",
        api_key=secrets.token_hex(16),
        farm_id=default_farm.id
    )
    db.session.add(default_station)
    db.session.commit()

    login_user(new_user)
    return jsonify({
        'status': 'success',
        'message': 'Usajili umefanikiwa!',
        'user': {'username': new_user.username, 'email': new_user.email}
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'status': 'success',
            'message': 'Umeingia kikamilifu',
            'user': {'username': user.username, 'email': user.email}
        })

    return jsonify({'status': 'error', 'message': 'Jina la mtumiaji au nenosiri si sahihi'}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'status': 'success', 'message': 'Umetoka kwenye mfumo'})

@app.route('/api/user-status', methods=['GET'])
def user_status():
    if current_user.is_authenticated:
        return jsonify({
            'logged_in': True,
            'username': current_user.username,
            'email': current_user.email
        })
    return jsonify({'logged_in': False})

# --- FARM MANAGEMENT ENDPOINTS ---

@app.route('/api/farms', methods=['GET'])
@login_required
def get_farms():
    farms = Farm.query.filter_by(user_id=current_user.id).all()
    result = []
    for f in farms:
        st = Station.query.filter_by(farm_id=f.id).first()
        result.append({
            'id': f.id,
            'name': f.name,
            'location': f.location or 'Haina Eneo',
            'api_key': st.api_key if st else ''
        })
    return jsonify({'status': 'success', 'farms': result})

@app.route('/api/farms/add', methods=['POST'])
@login_required
def add_farm():
    data = request.get_json() or {}
    name = data.get('name')
    location = data.get('location', '')

    if not name:
        return jsonify({'status': 'error', 'message': 'Tafadhali ingiza jina la shamba'}), 400

    new_farm = Farm(name=name, location=location, user_id=current_user.id)
    db.session.add(new_farm)
    db.session.commit()

    new_station = Station(
        station_code=f"STATION_{new_farm.id:03d}",
        api_key=secrets.token_hex(16),
        farm_id=new_farm.id
    )
    db.session.add(new_station)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': 'Shamba limeongezwa kikamilifu!',
        'farm': {'id': new_farm.id, 'name': new_farm.name, 'location': new_farm.location, 'api_key': new_station.api_key}
    })

# --- WEATHER DATA ENDPOINTS ---

@app.route('/api/get-data', methods=['GET'])
@login_required
def get_data():
    farm_id = request.args.get('farm_id', type=int)
    if not farm_id:
        first_farm = Farm.query.filter_by(user_id=current_user.id).first()
        if not first_farm:
            return jsonify({'status': 'error', 'message': 'Hakuna shamba lililopatikana'}), 404
        farm_id = first_farm.id

    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Ruhusa imekataliwa'}), 403

    station = Station.query.filter_by(farm_id=farm.id).first()
    if not station:
        return jsonify({
            'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0, 'wind_speed': 0,
            'is_online': False, 'last_updated': 'Hakuna Kituo', 'api_key': '',
            'advisories': ["Akaunti haina kituo cha sensor."]
        })

    latest_log = WeatherLog.query.filter_by(station_id=station.id).order_by(WeatherLog.timestamp.desc()).first()

    is_online = False
    if station.last_seen and (datetime.utcnow() - station.last_seen) < timedelta(minutes=5):
        is_online = True

    if not latest_log:
        return jsonify({
            'status': 'success', 'temperature': 0, 'humidity': 0, 'rain': 0, 'wind_speed': 0,
            'is_online': is_online, 'last_updated': 'Hajawahi Kutuma', 'api_key': station.api_key,
            'advisories': ["Inasubiri data kutoka kwenye sensor ya ESP32..."]
        })

    # Kutoa ushauri kulingana na vipimo vya hivi karibuni
    advisories = generate_agri_advisory(
        latest_log.temperature,
        latest_log.humidity,
        latest_log.rain,
        latest_log.wind_speed
    )

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

@app.route('/api/get-logs', methods=['GET'])
@login_required
def get_logs():
    farm_id = request.args.get('farm_id', type=int)
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Shamba halikupatikana'}), 404

    station = Station.query.filter_by(farm_id=farm.id).first()
    if not station:
        return jsonify({'status': 'success', 'logs': []})

    logs = WeatherLog.query.filter_by(station_id=station.id).order_by(WeatherLog.timestamp.desc()).limit(50).all()
    logs_data = [{
        'id': l.id,
        'temperature': l.temperature,
        'humidity': l.humidity,
        'rain': l.rain,
        'wind_speed': l.wind_speed,
        'timestamp': l.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for l in logs]

    return jsonify({'status': 'success', 'logs': logs_data})

@app.route('/api/get-stats', methods=['GET'])
@login_required
def get_stats():
    farm_id = request.args.get('farm_id', type=int)
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Shamba halikupatikana'}), 404

    station = Station.query.filter_by(farm_id=farm.id).first()
    if not station:
        return jsonify({'status': 'success', 'stats': {}})

    logs = WeatherLog.query.filter_by(station_id=station.id).all()
    if not logs:
        return jsonify({'status': 'success', 'stats': {'avg_temp': 0, 'max_temp': 0, 'min_temp': 0, 'avg_hum': 0}})

    temps = [l.temperature for l in logs]
    hums = [l.humidity for l in logs]

    return jsonify({
        'status': 'success',
        'stats': {
            'avg_temp': round(sum(temps) / len(temps), 1),
            'max_temp': max(temps),
            'min_temp': min(temps),
            'avg_hum': round(sum(hums) / len(hums), 1)
        }
    })

# --- ESP32 HARDWARE UPDATE ENDPOINT ---

@app.route('/update', methods=['POST'])
def update_weather():
    data = request.get_json() or {}
    api_key = data.get('api_key')

    station = Station.query.filter_by(api_key=api_key).first()
    if not station:
        return jsonify({'status': 'error', 'message': 'API Key ya Sensor si sahihi'}), 401

    temp = data.get('temperature')
    hum = data.get('humidity')
    rain = data.get('rain', 0.0)
    wind = data.get('wind_speed', 0.0)

    if temp is None or hum is None:
        return jsonify({'status': 'error', 'message': 'Data haijakamilika'}), 400

    log = WeatherLog(station_id=station.id, temperature=temp, humidity=hum, rain=rain, wind_speed=wind)
    station.is_online = True
    station.last_seen = datetime.utcnow()

    db.session.add(log)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Data imepokewa kikamilifu'})

# --- SMS & SUBSCRIBERS MANAGEMENT ---

@app.route('/api/subscribers', methods=['GET', 'POST'])
@login_required
def manage_subscribers():
    farm_id = request.args.get('farm_id', type=int) or (request.json and request.json.get('farm_id'))
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'status': 'error', 'message': 'Shamba halikupatikana'}), 404

    if request.method == 'POST':
        data = request.get_json() or {}
        phone = data.get('phone_number')
        name = data.get('name', 'Mkulima')
        if not phone:
            return jsonify({'status': 'error', 'message': 'Namba ya simu inatakiwa'}), 400

        sub = Subscriber(farm_id=farm.id, phone_number=phone, name=name)
        db.session.add(sub)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Mkulima ameongezwa kikamilifu'})

    subs = Subscriber.query.filter_by(farm_id=farm.id).all()
    return jsonify({
        'status': 'success',
        'subscribers': [{'id': s.id, 'name': s.name, 'phone': s.phone_number} for s in subs]
    })

# --- AUTOMATED SMS SCHEDULER ---

def send_daily_weather_sms():
    with app.app_context():
        farms = Farm.query.all()
        for farm in farms:
            station = Station.query.filter_by(farm_id=farm.id).first()
            if not station:
                continue
            latest = WeatherLog.query.filter_by(station_id=station.id).order_by(WeatherLog.timestamp.desc()).first()
            if not latest:
                continue

            subs = Subscriber.query.filter_by(farm_id=farm.id).all()
            if not subs:
                continue

            adv_list = generate_agri_advisory(latest.temperature, latest.humidity, latest.rain, latest.wind_speed)
            main_advisory = adv_list[0] if adv_list else "Hali ya hewa ni shwari."

            recipients = [s.phone_number for s in subs]
            msg = (
                f"SmartFarm [{farm.name}]:\n"
                f"Joto: {latest.temperature}°C, Unyevu: {latest.humidity}%, Mvua: {latest.rain}mm, Upepo: {latest.wind_speed}km/h.\n"
                f"USHAURI: {main_advisory}"
            )
            
            try:
                sms.send(msg, recipients)
            except Exception as e:
                print(f"Error sending SMS: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_weather_sms, 'cron', hour=7, minute=0)
scheduler.add_job(send_daily_weather_sms, 'cron', hour=18, minute=0)
scheduler.start()

# --- INITIALIZATION ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
