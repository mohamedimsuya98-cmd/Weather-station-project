from flask import Flask, render_template, render_template_string, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os
import requests
import africastalking

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Nenosiri la Admin
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "shamba1234")

# Taarifa za Africa's Talking kutoka kwenye Render Environment Variables
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")

if AT_API_KEY:
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms = africastalking.SMS
else:
    sms = None


# =========================================================
# DATABASE MODELS
# =========================================================

class WeatherLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    rain_amount = db.Column(db.Float, nullable=False)
    rain_availability = db.Column(db.String(50), nullable=False)
    wind_speed = db.Column(db.Float, nullable=False)
    wind_direction = db.Column(db.String(50), nullable=False)
    wifi_ssid = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.String(20), nullable=False)
    date_recorded = db.Column(db.String(20), nullable=False)


class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    date_joined = db.Column(db.String(20), nullable=False)


with app.app_context():
    db.create_all()


# =========================================================
# CURRENT WEATHER DATA & HISTORY
# =========================================================

weather_data = {
    "location": "Shamba Langu, Dar es Salaam",
    "temperature": "0.0",
    "humidity": "0",
    "rain_amount": "0.0",
    "rain_availability": "Hakuna Mvua",
    "wind_speed": "0.0",
    "wind_direction": "Kaskazini",
    "wifi_ssid": "Haijulikani"
}

weather_history = {
    "timestamps": [],
    "temperatures": [],
    "humidities": []
}

last_update_time = None


# =========================================================
# REAL SMS DISPATCHER FUNCTION (AFRICA'S TALKING)
# =========================================================

def send_alert_sms_to_farmers(message_text):
    with app.app_context():
        subscribers = Subscriber.query.all()
        if not subscribers or not sms:
            print("[SMS WARNING] Hakuna wakulima waliosajiliwa au API Key haijawekwa.")
            return

        recipients = [sub.phone_number for sub in subscribers]
        
        try:
            response = sms.send(message_text, recipients)
            print(f"[SMS IMETUMWA KWA MAFANIKIO]: {response}")
        except Exception as e:
            print(f"[SMS ERROR] Imeshindikana kutuma: {str(e)}")


# =========================================================
# AUTOMATED SCHEDULED NOTIFICATIONS (Morning & Evening SMS)
# =========================================================

def send_scheduled_weather_update():
    print("[SCHEDULER] Inatuma taarifa za hali ya hewa za asubuhi/jioni...")
    temp = weather_data.get('temperature', '0.0')
    humidity = weather_data.get('humidity', '0')
    rain_stat = weather_data.get('rain_availability', 'Hakuna Mvua')
    rain = weather_data.get('rain_amount', '0.0')

    message = (
        f"MUHTASARI WA SHAMBA:\n"
        f"Joto: {temp}C | Unyevu: {humidity}%\n"
        f"Mvua: {rain_stat} ({rain}mm)\n"
        f"Smart Farm Weather Station"
    )
    send_alert_sms_to_farmers(message)

# Weka ratiba ya kutuma saa 1:00 asubuhi (07:00) na saa 12:00 jioni (18:00)
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_scheduled_weather_update, trigger="cron", hour=7, minute=0)
scheduler.add_job(func=send_scheduled_weather_update, trigger="cron", hour=18, minute=0)
scheduler.start()


# =========================================================
# TRANSLATION FUNCTIONS
# =========================================================

def get_language():
    lang = request.args.get("lang", "sw")
    if lang not in ["sw", "en"]:
        lang = "sw"
    return lang


def translate_rain_status(value, lang):
    if value is None:
        return "--"
    value = str(value).strip()
    translations = {
        "Hakuna Mvua": {"sw": "Hakuna Mvua", "en": "No Rain"},
        "Mvua": {"sw": "Mvua", "en": "Rain"},
        "Mvua Ndogo": {"sw": "Mvua Ndogo", "en": "Light Rain"},
        "Mvua Kubwa": {"sw": "Mvua Kubwa", "en": "Heavy Rain"},
        "No Rain": {"sw": "Hakuna Mvua", "en": "No Rain"},
        "Rain": {"sw": "Mvua", "en": "Rain"},
        "Light Rain": {"sw": "Mvua Ndogo", "en": "Light Rain"},
        "Heavy Rain": {"sw": "Mvua Kubwa", "en": "Heavy Rain"}
    }
    return translations.get(value, {"sw": value, "en": value})[lang]


def translate_wind_direction(value, lang):
    if value is None:
        return "--"
    value = str(value).strip()
    translations = {
        "Kaskazini": {"sw": "Kaskazini", "en": "North"},
        "Kusini": {"sw": "Kusini", "en": "South"},
        "Mashariki": {"sw": "Mashariki", "en": "East"},
        "Magharibi": {"sw": "Magharibi", "en": "West"},
        "Kaskazini-Mashariki": {"sw": "Kaskazini-Mashariki", "en": "Northeast"},
        "Kaskazini-Magharibi": {"sw": "Kaskazini-Magharibi", "en": "Northwest"},
        "Kusini-Mashariki": {"sw": "Kusini-Mashariki", "en": "Southeast"},
        "Kusini-Magharibi": {"sw": "Kusini-Magharibi", "en": "Southwest"},
        "North": {"sw": "Kaskazini", "en": "North"},
        "South": {"sw": "Kusini", "en": "South"},
        "East": {"sw": "Mashariki", "en": "East"},
        "West": {"sw": "Magharibi", "en": "West"},
        "Northeast": {"sw": "Kaskazini-Mashariki", "en": "Northeast"},
        "Northwest": {"sw": "Kaskazini-Magharibi", "en": "Northwest"},
        "Southeast": {"sw": "Kusini-Mashariki", "en": "Southeast"},
        "Southwest": {"sw": "Kusini-Magharibi", "en": "Southwest"}
    }
    return translations.get(value, {"sw": value, "en": value})[lang]


def translate_wifi_status(is_online, lang):
    if is_online:
        return "Imeunganishwa (Online)" if lang == "sw" else "Connected (Online)"
    return "Haijaunganishwa (Offline)" if lang == "sw" else "Disconnected (Offline)"


def translate_no_device(lang):
    return "Hakuna Kifaa" if lang == "sw" else "No Device"


# =========================================================
# HOME (Frontend ya Kawaida)
# =========================================================

@app.route('/')
def home():
    return render_template('index.html', data=weather_data)


# =========================================================
# SECURE ADMIN PANEL ROUTE
# =========================================================

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    auth = request.authorization
    if not auth or auth.password != ADMIN_PASSWORD or auth.username != "admin":
        res = make_response("Ufikiaji Umezuiwa. Tafadhali ingiza jina la mtumiaji (admin) na nenosiri sahihi.", 401)
        res.headers['WWW-Authenticate'] = 'Basic realm="Admin Login Required"'
        return res

    message = ""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone_number', '').strip()
            if name and phone:
                existing = Subscriber.query.filter_by(phone_number=phone).first()
                if not existing:
                    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                    new_sub = Subscriber(name=name, phone_number=phone, date_joined=current_date)
                    db.session.add(new_sub)
                    db.session.commit()
                    message = f"Mkulima {name} amesajiliwa kikamilifu!"
                else:
                    message = "Hitilafu: Namba hii ya simu ipo tayari kwenye mfumo."
            else:
                message = "Tafadhali jaza jina na namba zote."
        elif action == 'delete':
            phone = request.form.get('phone_number', '').strip()
            sub = Subscriber.query.filter_by(phone_number=phone).first()
            if sub:
                db.session.delete(sub)
                db.session.commit()
                message = "Namba imeondolewa kikamilifu kwenye mfumo."
            else:
                message = "Hitilafu: Namba haikupatikana."

    subscribers = Subscriber.query.all()

    admin_html = """
    <!DOCTYPE html>
    <html lang="sw">
    <head>
        <meta charset="UTF-8">
        <title>Smart Farm - Admin Panel</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
            .container { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            h2 { color: #1b4332; }
            .msg { background: #d8f3dc; color: #081c15; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
            form { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
            input, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; border: 1px solid #ccc; border-radius: 5px; }
            button { background: #2d6a4f; color: white; border: none; font-weight: bold; cursor: pointer; }
            button:hover { background: #1b4332; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background: #2d6a4f; color: white; }
            .del-btn { background: #d90429; width: auto; padding: 5px 10px; }
            .del-btn:hover { background: #8d0801; }
            .back-link { display: inline-block; margin-top: 20px; color: #2d6a4f; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Panel ya Utawala (Admin SMS Subscribers)</h2>
            <p>Hapa unaweza kusajili au kuondoa namba za wakulima watakaopata taarifa za dharura kupitia SMS.</p>
            
            {% if message %}
                <div class="msg">{{ message }}</div>
            {% endif %}

            <h3>Sajili Mkulima Mpya</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <input type="text" name="name" placeholder="Jina la Mkulima (Mf: Juma Ally)" required>
                <input type="text" name="phone_number" placeholder="Namba ya Simu (Mf: +255712345678)" required>
                <button type="submit">Ongeza Mkulima</button>
            </form>

            <h3>Wakulima Waliosajiliwa Sasa ({{ subscribers|length }})</h3>
            <table>
                <tr>
                    <th>Jina</th>
                    <th>Namba ya Simu</th>
                    <th>Tarehe Iliyosajiliwa</th>
                    <th>Kitendo</th>
                </tr>
                {% for sub in subscribers %}
                <tr>
                    <td>{{ sub.name }}</td>
                    <td>{{ sub.phone_number }}</td>
                    <td>{{ sub.date_joined }}</td>
                    <td>
                        <form method="POST" style="margin:0; background:none; padding:0;">
                            <input type="hidden" name="action" value="delete">
                            <input type="hidden" name="phone_number" value="{{ sub.phone_number }}">
                            <button type="submit" class="del-btn">Futa</button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="4" style="text-align: center;">Hakuna wakulima waliosajiliwa bado.</td>
                </tr>
                {% endfor %}
            </table>

            <a href="/" class="back-link">&larr; Rudi kwenye Dashboard Kuu</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(admin_html, message=message, subscribers=subscribers)


# =========================================================
# AFRICA'S TALKING INBOUND SMS WEBHOOK (On-Demand Status)
# =========================================================
@app.route('/sms-incoming', methods=['POST', 'GET'])
def sms_incoming():
    sender = request.form.get('from') or (request.json.get('from') if request.is_json else '')
    text = request.form.get('text') or (request.json.get('text') if request.is_json else '')
    
    sender = sender.strip()
    text = text.strip().lower()
    
    print(f"[SMS INCOMING] Kutoka: {sender}, Ujumbe: {text}")
    
    temp = weather_data.get('temperature', '0.0')
    humidity = weather_data.get('humidity', '0')
    rain = weather_data.get('rain_amount', '0.0')
    rain_stat = weather_data.get('rain_availability', 'Hakuna Mvua')
    
    if not text or "hali" in text or "status" in text or "weather" in text or "mvua" in text or "joto" in text:
        response_message = (
            f"Hali ya Hewa Shambani:\n"
            f"Joto: {temp}C\n"
            f"Unyevu: {humidity}%\n"
            f"Mvua: {rain_stat} ({rain}mm)\n"
            f"Smart Farm Weather Station"
        )
    else:
        response_message = (
            "Karibu Smart Farm! "
            "Tuma neno 'HALI' kupata taarifa za hivi punde za hali ya hewa."
        )

    if sms and sender:
        try:
            sms.send(response_message, [sender])
            print(f"[SMS INCOMING] Jibu limetumwa kwa {sender}")
        except Exception as e:
            print(f"[SMS INCOMING ERROR] Imeshindikana kujibu: {str(e)}")
            
    return jsonify({"status": "success", "message": "Processed"}), 200


# =========================================================
# ESP32 -> FLASK UPDATE
# =========================================================

@app.route('/update', methods=['POST'])
def update_weather():
    global weather_data, weather_history, last_update_time
    data = request.json

    if data:
        weather_data['temperature'] = data.get('temperature', weather_data['temperature'])
        weather_data['humidity'] = data.get('humidity', weather_data['humidity'])
        weather_data['rain_amount'] = data.get('rain_amount', weather_data['rain_amount'])
        weather_data['rain_availability'] = data.get('rain_availability', weather_data['rain_availability'])
        weather_data['wind_speed'] = data.get('wind_speed', weather_data['wind_speed'])
        weather_data['wind_direction'] = data.get('wind_direction', weather_data['wind_direction'])
        
        received_ssid = data.get('wifi_ssid', 'Haijulikani')
        weather_data['wifi_ssid'] = received_ssid

        last_update_time = datetime.datetime.now()
        current_time = last_update_time.strftime("%H:%M:%S")
        current_date = last_update_time.strftime("%Y-%m-%d")

        weather_history["timestamps"].append(current_time)
        weather_history["temperatures"].append(float(weather_data['temperature']))
        weather_history["humidities"].append(float(weather_data['humidity']))

        if len(weather_history["timestamps"]) > 20:
            weather_history["timestamps"].pop(0)
            weather_history["temperatures"].pop(0)
            weather_history["humidities"].pop(0)

        new_log = WeatherLog(
            temperature=float(weather_data['temperature']),
            humidity=float(weather_data['humidity']),
            rain_amount=float(weather_data['rain_amount']),
            rain_availability=weather_data['rain_availability'],
            wind_speed=float(weather_data['wind_speed']),
            wind_direction=weather_data['wind_direction'],
            wifi_ssid=received_ssid,
            timestamp=current_time,
            date_recorded=current_date
        )
        db.session.add(new_log)
        db.session.commit()

        # Angalia dharura ya kutuma SMS ya haraka
        try:
            temp_val = float(weather_data['temperature'])
            rain_val = float(weather_data['rain_amount'])
            rain_stat = str(weather_data['rain_availability']).lower()

            if rain_val > 5.0 or "mvua kubwa" in rain_stat or "heavy" in rain_stat:
                alert_msg = f"TAHADHARI YA SHAMBA: Mvua kubwa imegunduliwa shambani ({rain_val}mm). Tafadhali chukua hatua."
                send_alert_sms_to_farmers(alert_msg)
            elif temp_val > 34.0:
                alert_msg = f"TAHADHARI YA JOTO KALI: Joto shambani limefika {temp_val}C. Ongeza umwagiliaji."
                send_alert_sms_to_farmers(alert_msg)
        except Exception as err:
            print("Hitilafu kwenye uchambuzi wa SMS:", str(err))

        return jsonify({"status": "success", "message": "Data imepokelewa!"}), 200

    return jsonify({"status": "error", "message": "Haikusomeka!"}), 400


# =========================================================
# API ENDPOINTS
# =========================================================

@app.route('/get-data', methods=['GET'])
def get_data():
    global last_update_time
    lang = get_language()
    response_data = weather_data.copy()
    response_data["history"] = weather_history

    is_online = False
    if last_update_time:
        time_difference = (datetime.datetime.now() - last_update_time).total_seconds()
        if time_difference < 30:
            is_online = True

    response_data["is_online"] = is_online
    response_data["wifi_status"] = translate_wifi_status(is_online, lang)
    response_data["wifi_ssid"] = weather_data.get("wifi_ssid", translate_no_device(lang)) if is_online else translate_no_device(lang)
    response_data["rain_availability"] = translate_rain_status(weather_data.get("rain_availability"), lang)
    response_data["wind_direction"] = translate_wind_direction(weather_data.get("wind_direction"), lang)

    return jsonify(response_data)


@app.route('/get-logs', methods=['GET'])
def get_logs():
    lang = get_language()
    logs = WeatherLog.query.order_by(WeatherLog.id.desc()).limit(50).all()
    logs_list = [{
        "id": log.id,
        "temperature": log.temperature,
        "humidity": log.humidity,
        "rain_amount": log.rain_amount,
        "rain_availability": translate_rain_status(log.rain_availability, lang),
        "wind_speed": log.wind_speed,
        "wind_direction": translate_wind_direction(log.wind_direction, lang),
        "wifi_ssid": log.wifi_ssid,
        "timestamp": log.timestamp,
        "date": log.date_recorded
    } for log in logs]
    return jsonify(logs_list)


@app.route('/get-stats', methods=['GET'])
def get_stats():
    logs = WeatherLog.query.all()
    if not logs:
        return jsonify({
            "avg_temp": 0.0, "max_temp": 0.0, "min_temp": 0.0,
            "avg_humidity": 0.0, "total_rain": 0.0, "avg_wind": 0.0,
            "total_records": 0, "insight": "Hakuna kumbukumbu za kutosha bado."
        })

    temps = [log.temperature for log in logs]
    humidities = [log.humidity for log in logs]
    rains = [log.rain_amount for log in logs]
    winds = [log.wind_speed for log in logs]

    avg_temp = round(sum(temps) / len(temps), 1)
    max_temp = round(max(temps), 1)
    min_temp = round(min(temps), 1)
    avg_humidity = round(sum(humidities) / len(humidities), 1)
    total_rain = round(sum(rains), 2)
    avg_wind = round(sum(winds) / len(winds), 1)
    total_records = len(logs)

    insight = f"📈 **Uchambuzi wa Mwenendo wa Shamba (Jumla: {total_records}):**\n\n"
    if max_temp > 33:
        insight += f"• Joto kali limefika {max_temp}C. Ongeza umwagiliaji.\n"
    else:
        insight += f"• Wastani wa joto upo vizuri ({avg_temp}C).\n"

    return jsonify({
        "avg_temp": avg_temp, "max_temp": max_temp, "min_temp": min_temp,
        "avg_humidity": avg_humidity, "total_rain": total_rain, "avg_wind": avg_wind,
        "total_records": total_records, "insight": insight
    })


@app.route('/analyze-ai5', methods=['GET'])
def analyze_ai():
    temp = float(weather_data.get('temperature', 0.0))
    humidity = float(weather_data.get('humidity', 0.0))
    analysis = f"🌿 **Uchambuzi wa Kitaalamu:** Hali ya hewa ipo sawa. Joto: {temp}C, Unyevu: {humidity}%."
    return jsonify({"status": "success", "analysis": analysis})


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
