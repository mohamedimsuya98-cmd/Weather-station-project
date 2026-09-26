from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os

app = Flask(__name__)

# Sanidi Database ya SQLite ndani ya mradi
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

with app.app_context():
    db.create_all()

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

@app.route('/')
def home():
    return render_template('index.html', data=weather_data)

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
            
        return jsonify({"status": "success", "message": "Data imepokelewa!"}), 200
    
    return jsonify({"status": "error", "message": "Haikusomeka!"}), 400

@app.route('/get-data', methods=['GET'])
def get_data():
    global last_update_time
    response_data = weather_data.copy()
    response_data["history"] = weather_history
    
    is_online = False
    if last_update_time:
        time_difference = (datetime.datetime.now() - last_update_time).total_seconds()
        if time_difference < 30:
            is_online = True

    if is_online:
        response_data["wifi_status"] = "Imeunganishwa (Online)"
    else:
        response_data["wifi_status"] = "Haijaunganishwa (Offline)"
        response_data["wifi_ssid"] = "Hakuna Kifaa"

    return jsonify(response_data)

@app.route('/get-logs', methods=['GET'])
def get_logs():
    logs = WeatherLog.query.order_by(WeatherLog.id.desc()).limit(50).all()
    logs_list = []
    for log in logs:
        logs_list.append({
            "id": log.id,
            "temperature": log.temperature,
            "humidity": log.humidity,
            "rain_amount": log.rain_amount,
            "rain_availability": log.rain_availability,
            "wind_speed": log.wind_speed,
            "wind_direction": log.wind_direction,
            "wifi_ssid": log.wifi_ssid,
            "timestamp": log.timestamp,
            "date": log.date_recorded
        })
    return jsonify(logs_list)

@app.route('/get-stats', methods=['GET'])
def get_stats():
    logs = WeatherLog.query.all()
    if not logs:
        return jsonify({
            "avg_temp": 0.0, "max_temp": 0.0, "min_temp": 0.0, 
            "avg_humidity": 0.0, "total_rain": 0.0, "avg_wind": 0.0, 
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

@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():
    try:
        temp = float(weather_data['temperature'])
        humidity = float(weather_data['humidity'])
        rain_amt = float(weather_data['rain_amount'])
        rain_status = weather_data['rain_availability']
        wind_spd = float(weather_data['wind_speed'])
        wind_dir = weather_data['wind_direction']
        
        analysis = f"🌿 **Uchambuzi wa Kitaalamu wa Hali ya Hewa (Live Expert System):**\n\n"
        
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
