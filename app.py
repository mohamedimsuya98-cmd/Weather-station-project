from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import requests

app = Flask(__name__)

# Sanidi Database ya SQLite ndani ya mradi
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Unda mfumo wa hifadhi (Model) ya data za hali ya hewa
class WeatherLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    rain_amount = db.Column(db.Float, nullable=False)
    rain_availability = db.Column(db.String(50), nullable=False)
    wind_speed = db.Column(db.Float, nullable=False)
    wind_direction = db.Column(db.String(50), nullable=False)
    wifi_ssid = db.Column(db.String(50), nullable=True)  # Sehemu ya kuhifadhi jina la Wi-Fi kwenye DB
    timestamp = db.Column(db.String(20), nullable=False)
    date_recorded = db.Column(db.String(20), nullable=False)

# Anzisha Database wakati app inapowaka
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

# Variable ya kuhifadhi muda wa mwisho ESP32 ilipotuma data
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
        
        # Kupokea jina la Wi-Fi kutoka kwa ESP32
        received_ssid = data.get('wifi_ssid', 'Haijulikani')
        weather_data['wifi_ssid'] = received_ssid
        
        # Sasisha muda wa mwisho kifaa kilipowasiliana na seva
        last_update_time = datetime.datetime.now()
        
        current_time = last_update_time.strftime("%H:%M:%S")
        current_date = last_update_time.strftime("%Y-%m-%d")
        
        # 1. Hifadhi kwenye kumbukumbu za muda mfupi (in-memory history kwa ajili ya chart)
        weather_history["timestamps"].append(current_time)
        weather_history["temperatures"].append(float(weather_data['temperature']))
        weather_history["humidities"].append(float(weather_data['humidity']))
        
        if len(weather_history["timestamps"]) > 20:
            weather_history["timestamps"].pop(0)
            weather_history["temperatures"].pop(0)
            weather_history["humidities"].pop(0)
            
        # 2. Hifadhi ya kudumu kwenye Database (SQLite) pamoja na wifi_ssid
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
            
        return jsonify({"status": "success", "message": "Data na jina la Wi-Fi zimepokelewa na kuhifadhiwa!"}), 200
    
    return jsonify({"status": "error", "message": "Haikusomeka!"}), 400

@app.route('/get-data', methods=['GET'])
def get_data():
    global last_update_time
    response_data = weather_data.copy()
    response_data["history"] = weather_history
    
    # Angalia kama kifaa kimetuma data ndani ya sekunde 30 zilizopita
    is_online = False
    if last_update_time:
        time_difference = (datetime.datetime.now() - last_update_time).total_seconds()
        if time_difference < 30:
            is_online = True

    # Tuma taarifa za mtandao kulingana na hali halisi ya ESP32
    if is_online:
        response_data["wifi_status"] = "Imeunganishwa (Online)"
    else:
        response_data["wifi_status"] = "Haijaunganishwa (Offline)"
        response_data["wifi_ssid"] = "Hakuna Kifaa"

    return jsonify(response_data)

# Njia ya kuchota historia yote iliyohifadhiwa kwenye database kwa ajili ya ukurasa wa Historia
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

# Njia ya kuchakata na kurudisha takwimu za kina (Stats)
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
            "total_records": 0
        })
    
    temps = [log.temperature for log in logs]
    humidities = [log.humidity for log in logs]
    rains = [log.rain_amount for log in logs]
    winds = [log.wind_speed for log in logs]
    
    stats_data = {
        "avg_temp": round(sum(temps) / len(temps), 1),
        "max_temp": round(max(temps), 1),
        "min_temp": round(min(temps), 1),
        "avg_humidity": round(sum(humidities) / len(humidities), 1),
        "total_rain": round(sum(rains), 2),
        "avg_wind": round(sum(winds) / len(winds), 1),
        "total_records": len(logs)
    }
    return jsonify(stats_data)

# Sehemu ya kutumia Groq AI badala ya Gemini
@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"status": "error", "analysis": "Samahani, GROQ_API_KEY haijawekwa kwenye seva ya Render."})

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Wewe ni mtaalamu wa kilimo cha kisasa. Hizi hapa ni taarifa za sasa kutoka kwenye kituo cha hali ya hewa shambani:
    - Joto: {weather_data['temperature']} °C
    - Unyevu wa hewa: {weather_data['humidity']} %
    - Kiwango cha mvua: {weather_data['rain_amount']} mm
    - Hali ya mvua: {weather_data['rain_availability']}
    - Kasi ya upepo: {weather_data['wind_speed']} m/s
    - Mwelekeo wa upepo: {weather_data['wind_direction']}
    - Wi-Fi SSID: {weather_data['wifi_ssid']}

    Tafadhali toa ushauri mfupi na wa vitendo kwa mkulima kwa lugha ya Kiswahili ya kuvutia, ukizingatia kama kuna haja ya kumwagilia, kulinda mazao, au kuchukua hatua yoyote ya kiutendaji kulingana na takwimu hizi za sasa.
    """

payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            res_json = response.json()
            analysis_text = res_json['choices'][0]['message']['content']
            return jsonify({"status": "success", "analysis": analysis_text})
        else:
            return jsonify({"status": "error", "analysis": f"Hitilafu kutoka Groq: {response.text}"})
    except Exception as e:
        return jsonify({"status": "error", "analysis": f"Imeshindikana kuunganisha na AI: {str(e)}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
