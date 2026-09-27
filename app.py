from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import requests  # Imeongezwa kwa ajili ya kutuma maombi ya SMS API

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODELS
# =========================================================

class WeatherLog(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    temperature = db.Column(
        db.Float,
        nullable=False
    )
    humidity = db.Column(
        db.Float,
        nullable=False
    )
    rain_amount = db.Column(
        db.Float,
        nullable=False
    )
    rain_availability = db.Column(
        db.String(50),
        nullable=False
    )
    wind_speed = db.Column(
        db.Float,
        nullable=False
    )
    wind_direction = db.Column(
        db.String(50),
        nullable=False
    )
    wifi_ssid = db.Column(
        db.String(50),
        nullable=True
    )
    timestamp = db.Column(
        db.String(20),
        nullable=False
    )
    date_recorded = db.Column(
        db.String(20),
        nullable=False
    )


# Jedwali la kuhifadhi namba za simu za wakulima
class Subscriber(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    name = db.Column(
        db.String(100),
        nullable=False
    )
    phone_number = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )
    date_joined = db.Column(
        db.String(20),
        nullable=False
    )


with app.app_context():
    db.create_all()


# =========================================================
# CURRENT WEATHER DATA
# =========================================================

weather_data = {
    "location":
        "Shamba Langu, Dar es Salaam",
    "temperature":
        "0.0",
    "humidity":
        "0",
    "rain_amount":
        "0.0",
    "rain_availability":
        "Hakuna Mvua",
    "wind_speed":
        "0.0",
    "wind_direction":
        "Kaskazini",
    "wifi_ssid":
        "Haijulikani"
}


# =========================================================
# TEMPORARY CHART HISTORY
# =========================================================

weather_history = {
    "timestamps": [],
    "temperatures": [],
    "humidities": []
}

last_update_time = None


# =========================================================
# SMS DISPATCHER FUNCTION
# =========================================================

def send_alert_sms_to_farmers(message_text):
    """
    Hii kazi inatafuta namba zote zilizosajiliwa kwenye database
    na kutuma ujumbe mfupi wa tahadhari.
    """
    subscribers = Subscriber.query.all()
    if not subscribers:
        return  # Hakuna namba iliyosajiliwa bado

    # Mfano wa kutumia API ya SMS (Badilisha URL na Headers kulingana na mtoa hudumu wako kama Africa's Talking)
    sms_api_url = os.environ.get("SMS_API_URL", "")
    api_key = os.environ.get("SMS_API_KEY", "")

    for sub in subscribers:
        phone = sub.phone_number
        try:
            # Kama unatumia gateway maalum, unaweka code za request hapa hapa:
            # payload = {"to": phone, "message": message_text}
            # requests.post(sms_api_url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
            
            # Kwa sasa tunaprint kwenye server logs kama mfano halisi wa utekelezaji
            print(f"[SMS ALERT] Imetumwa kwenda kwa {sub.name} ({phone}): {message_text}")
        except Exception as e:
            print(f"[SMS ERROR] Imeshindikana kutuma kwenda kwa {phone}: {str(e)}")


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
# HOME
# =========================================================

@app.route('/')
def home():
    return render_template('index.html', data=weather_data)


# =========================================================
# SUBSCRIBER MANAGEMENT ROUTES (API)
# =========================================================

@app.route('/add-subscriber', methods=['POST'])
def add_subscriber():
    """Njia ya kuongeza namba mpya ya simu ya mkulima"""
    req_data = request.json
    if not req_data or 'phone_number' not in req_data or 'name' not in req_data:
        return jsonify({"status": "error", "message": "Jina na namba ya simu zinahitajika!"}), 400

    name = req_data.get('name').strip()
    phone = req_data.get('phone_number').strip()

    # Angalia kama namba ishakuwepo
    existing = Subscriber.query.filter_by(phone_number=phone).first()
    if existing:
        return jsonify({"status": "error", "message": "Namba hii ya simu imeshasajiliwa tayari!"}), 400

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    new_sub = Subscriber(name=name, phone_number=phone, date_joined=current_date)
    
    db.session.add(new_sub)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Mkulima {name} amesajiliwa mafanikio!"}), 201


@app.route('/remove-subscriber', methods=['POST', 'DELETE'])
def remove_subscriber():
    """Njia ya kuondoa namba ya simu ya mkulima"""
    req_data = request.json
    if not req_data or 'phone_number' not in req_data:
        return jsonify({"status": "error", "message": "Namba ya simu inahitajika!"}), 400

    phone = req_data.get('phone_number').strip()
    sub = Subscriber.query.filter_by(phone_number=phone).first()

    if not sub:
        return jsonify({"status": "error", "message": "Namba haipatikani kwenye mfumo!"}), 404

    db.session.delete(sub)
    db.session.commit()

    return jsonify({"status": "success", "message": "Namba imeondolewa kwa mafanikio!"}), 200


@app.route('/get-subscribers', methods=['GET'])
def get_subscribers():
    """Kuona orodha ya wakulima wote waliosajiliwa"""
    subs = Subscriber.query.all()
    sub_list = [{"name": s.name, "phone_number": s.phone_number, "date_joined": s.date_joined} for s in subs]
    return jsonify(sub_list), 200


# =========================================================
# ESP32 -> FLASK
# =========================================================

@app.route('/update', methods=['POST'])
def update_weather():
    global weather_data
    global weather_history
    global last_update_time

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

        # =========================================
        # HISTORY FOR GRAPH
        # =========================================
        weather_history["timestamps"].append(current_time)
        weather_history["temperatures"].append(float(weather_data['temperature']))
        weather_history["humidities"].append(float(weather_data['humidity']))

        if len(weather_history["timestamps"]) > 20:
            weather_history["timestamps"].pop(0)
            weather_history["temperatures"].pop(0)
            weather_history["humidities"].pop(0)

        # =========================================
        # DATABASE LOGGING
        # =========================================
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

        # =========================================
        # AUTOMATED SMS ALERT CHECK (DHARURA)
        # =========================================
        try:
            temp_val = float(weather_data['temperature'])
            rain_val = float(weather_data['rain_amount'])
            rain_stat = str(weather_data['rain_availability']).lower()

            # Kama kuna mvua kubwa au joto limezidi kiwango cha hatari (>34°C)
            if rain_val > 5.0 or "mvua kubwa" in rain_stat or "heavy" in rain_stat:
                alert_msg = f"TAHADHARI YA SHAMBA: Mvua kubwa imegunduliwa shambani ({rain_val}mm). Tafadhari chukua hatua za usalama."
                send_alert_sms_to_farmers(alert_msg)
            elif temp_val > 34.0:
                alert_msg = f"TAHADHARI YA JOTO KALI: Joto shambani limefika {temp_val}°C. Ongeza umwagiliaji."
                send_alert_sms_to_farmers(alert_msg)
        except Exception as err:
            print("Hitilafu kwenye uchambuzi wa SMS:", str(err))

        return jsonify({
            "status": "success",
            "message": "Data imepokelewa na kuchakatwa!"
        }), 200

    return jsonify({
        "status": "error",
        "message": "Haikusomeka!"
    }), 400


# =========================================================
# LIVE DATA
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
    
    if is_online:
        response_data["wifi_ssid"] = weather_data.get("wifi_ssid", translate_no_device(lang))
    else:
        response_data["wifi_ssid"] = translate_no_device(lang)

    response_data["rain_availability"] = translate_rain_status(weather_data.get("rain_availability"), lang)
    response_data["wind_direction"] = translate_wind_direction(weather_data.get("wind_direction"), lang)

    return jsonify(response_data)


# =========================================================
# HISTORY
# =========================================================

@app.route('/get-logs', methods=['GET'])
def get_logs():
    lang = get_language()
    logs = WeatherLog.query.order_by(WeatherLog.id.desc()).limit(50).all()

    logs_list = []
    for log in logs:
        logs_list.append({
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
        })

    return jsonify(logs_list)


# =========================================================
# STATISTICS
# =========================================================

@app.route('/get-stats', methods=['GET'])
def get_stats():
    logs = WeatherLog.query.all()

    if not logs:
        return jsonify({
            "avg_temp": 0.0,
            "max_temp": 0.0,
            "min_temp": 0.0,
            "avg_humidity": 0.0,
            "total_rain": 0.0,
            "avg_wind": 0.0,
            "total_records": 0,
            "insight": "Hakuna kumbukumbu za kutosha bado kwenye mfumo."
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

    insight = f"📈 **Uchambuzi wa Mwenendo wa Shamba (Jumla ya kumbukumbu: {total_records}):**\n\n"

    if max_temp > 33:
        insight += f"• **Tahadhari ya Joto Kali:** Kiwango cha juu kimefika {max_temp}°C. Udongo unakauka kwa kasi; ongeza umwagiliaji jioni.\n"
    elif min_temp < 18 and min_temp > 0:
        insight += f"• **Tahadhari ya Baridi:** Joto limeshuka hadi {min_temp}°C, punguza kasi ya kumwagilia maji ya baridi.\n"
    else:
        insight += f"• **Hali ya Joto:** Wastani wa joto upo vizuri ({avg_temp}°C), ukiwa na upeo wa {max_temp}°C.\n"

    if total_rain > 10:
        insight += f"• **Mwenendo wa Mvua:** Jumla ya mvua ({total_rain} mm) inatosha; simamisha umwagiliaji kwa muda.\n"
    elif total_rain > 0:
        insight += f"• **Mwenendo wa Mvua:** Mvua ndogo imerekodiwa ({total_rain} mm).\n"
    else:
        insight += f"• **Mwenendo wa Mvua:** Hakuna mvua iliyorekodiwa, tegemea umwagiliaji wa bandia.\n"

    if avg_wind > 5.0:
        insight += f"• **Tahadhari ya Upepo:** Upepo ni mkali ({avg_wind} m/s). Kuwa makini na ulinzi wa mimea."
    else:
        insight += f"• **Hali ya Upepo:** Kasi ya wastani ya upepo ({avg_wind} m/s) iko salama."

    return jsonify({
        "avg_temp": avg_temp,
        "max_temp": max_temp,
        "min_temp": min_temp,
        "avg_humidity": avg_humidity,
        "total_rain": total_rain,
        "avg_wind": avg_wind,
        "total_records": total_records,
        "insight": insight
    })


# =========================================================
# AI ANALYSIS ENDPOINT
# =========================================================

@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():
    try:
        temp = float(weather_data.get('temperature', 0.0))
        humidity = float(weather_data.get('humidity', 0.0))
        rain_amt = float(weather_data.get('rain_amount', 0.0))
        rain_status = weather_data.get('rain_availability', 'Hakuna Mvua')
        wind_spd = float(weather_data.get('wind_speed', 0.0))
        wind_dir = weather_data.get('wind_direction', 'Kaskazini')

        if temp == 0.0 and humidity == 0.0 and rain_amt == 0.0 and wind_spd == 0.0:
            analysis = (
                "⚠️ **Tahadhari ya Mfumo:** Hakuna data halisi zilizopokelewa "
                "kutoka kwenye kihisi (Sensor) au kifaa cha ESP8266/ESP32.\n\n"
                "**Njia ya Kurekebisha:**\n"
                "1. Hakikisha kifaa chako cha ESP kimeunganishwa kwenye intaneti.\n"
                "2. Hakikisha kinatuma maombi ya `POST` kwenda kwenye anuani sahihi ya `/update`."
            )
            return jsonify({"status": "warning", "analysis": analysis})

        analysis = "🌿 **Uchambuzi wa Kitaalamu wa Hali ya Hewa (Live Expert System):**\n\n"

        if temp > 32 and humidity < 45:
            analysis += f"1. **Hali ya Hewa & Unyevu:** ⚠️ Joto lipo juu sana ({temp}°C) na unyevu ni mdogo ({humidity}%). **Ushauri:** Ongeza kiwango cha kumwagilia.\n"
        elif temp > 32 and humidity >= 45:
            analysis += f"1. **Hali ya Hewa & Unyevu:** ☀️ Joto ni kali ({temp}°C) lakini unyevu uko sawa ({humidity}%).\n"
        elif temp < 20 and humidity > 75:
            analysis += f"1. **Hali ya Hewa & Unyevu:** 💧 Joto ni la chini ({temp}°C) na unyevu uko juu ({humidity}%). **Tahadhari:** Angalia magonjwa ya ukungu.\n"
        else:
            analysis += f"1. **Hali ya Hewa & Unyevu:** 🌱 Hali ya joto ({temp}°C) na unyevu ({humidity}%) ziko katika uwiano mzuri.\n"

        if rain_amt > 0 or "Mvua" in rain_status:
            analysis += f"2. **Hali ya Mvua:** Mvua imepimwa kiasi cha {rain_amt} mm ({rain_status}).\n"
        else:
            analysis += f"2. **Hali ya Mvua:** Hakuna mvua iliyorekodiwa ({rain_status}).\n"

        if wind_spd > 4.5:
            analysis += f"3. **Hali ya Upepo:** 💨 Kasi ya upepo ni kali ({wind_spd} m/s kutoka {wind_dir}).\n"
        else:
            analysis += f"3. **Hali ya Upepo:** Kasi ya upepo ni tulivu ({wind_spd} m/s kutoka {wind_dir}), hakuna hatari.\n"

        analysis += "\n_Mfumo huu umesanifiwa kutoa tathmini kwa usahihi bila kukosa mtandao._"

        return jsonify({"status": "success", "analysis": analysis})

    except Exception as e:
        return jsonify({"status": "error", "analysis": f"Imeshindikana kuchambua data: {str(e)}"})


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
