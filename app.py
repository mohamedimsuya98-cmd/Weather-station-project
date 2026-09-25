from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import time
from google import genai

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
    timestamp = db.Column(db.String(20), nullable=False)
    date_recorded = db.Column(db.String(20), nullable=False)

# Anzisha Database wakati app inapowaka
with app.app_context():
    db.create_all()

# Sanidi Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

weather_data = {
    "location": "Shamba Langu, Dar es Salaam",
    "temperature": "0.0",
    "humidity": "0",
    "rain_amount": "0.0",
    "rain_availability": "Hakuna Mvua",
    "wind_speed": "0.0",
    "wind_direction": "Kaskazini"
}

weather_history = {
    "timestamps": [],
    "temperatures": [],
    "humidities": []
}

@app.route('/')
def home():
    return render_template('index.html', data=weather_data)

@app.route('/update', methods=['POST'])
def update_weather():
    global weather_data, weather_history
    data = request.json
    
    if data:
        weather_data['temperature'] = data.get('temperature', weather_data['temperature'])
        weather_data['humidity'] = data.get('humidity', weather_data['humidity'])
        weather_data['rain_amount'] = data.get('rain_amount', weather_data['rain_amount'])
        weather_data['rain_availability'] = data.get('rain_availability', weather_data['rain_availability'])
        weather_data['wind_speed'] = data.get('wind_speed', weather_data['wind_speed'])
        weather_data['wind_direction'] = data.get('wind_direction', weather_data['wind_direction'])
        
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 1. Hifadhi kwenye kumbukumbu za muda mfupi (in-memory history kwa ajili ya chart)
        weather_history["timestamps"].append(current_time)
        weather_history["temperatures"].append(float(weather_data['temperature']))
        weather_history["humidities"].append(float(weather_data['humidity']))
        
        if len(weather_history["timestamps"]) > 20:
            weather_history["timestamps"].pop(0)
            weather_history["temperatures"].pop(0)
            weather_history["humidities"].pop(0)
            
        # 2. Hifadhi ya kudumu kwenye Database (SQLite)
        new_log = WeatherLog(
            temperature=float(weather_data['temperature']),
            humidity=float(weather_data['humidity']),
            rain_amount=float(weather_data['rain_amount']),
            rain_availability=weather_data['rain_availability'],
            wind_speed=float(weather_data['wind_speed']),
            wind_direction=weather_data['wind_direction'],
            timestamp=current_time,
            date_recorded=current_date
        )
        db.session.add(new_log)
        db.session.commit()
            
        return jsonify({"status": "success", "message": "Data imepokelewa na kuhifadhiwa!"}), 200
    
    return jsonify({"status": "error", "message": "Haikusomeka!"}), 400

@app.route('/get-data', methods=['GET'])
def get_data():
    response_data = weather_data.copy()
    response_data["history"] = weather_history
    return jsonify(response_data)

# Njia mpya ya kuchota historia yote iliyohifadhiwa kwenye database kwa ajili ya ukurasa wa Historia
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
            "timestamp": log.timestamp,
            "date": log.date_recorded
        })
    return jsonify(logs_list)

@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"status": "error", "analysis": "Samahani, API Key ya Gemini haijawekwa kwenye seva ya Render."})

    prompt = f"""
    Wewe ni mtaalamu wa kilimo cha kisasa. Hizi hapa ni taarifa za sasa kutoka kwenye kituo cha hali ya hewa shambani:
    - Joto: {weather_data['temperature']} °C
    - Unyevu wa hewa: {weather_data['humidity']} %
    - Kiwango cha mvua: {weather_data['rain_amount']} mm
    - Hali ya mvua: {weather_data['rain_availability']}
    - Kasi ya upepo: {weather_data['wind_speed']} m/s
    - Mwelekeo wa upepo: {weather_data['wind_direction']}

    Tafadhali toa ushauri mfupi na wa vitendo kwa mkulima kwa lugha ya Kiswahili ya kuvutia, ukizingatia kama kuna haja ya kumwagilia, kulinda mazao, au kuchukua hatua yoyote ya kiutendaji kulingana na takwimu hizi za sasa.
    """
    
    max_retries = 3
    delay = 2
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt
            )
            if response and response.text:
                return jsonify({"status": "success", "analysis": response.text})
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
                continue
            else:
                return jsonify({"status": "error", "analysis": f"Seva za AI zina msongamano kwa sasa. Jaribu tena baadae. Hitilafu: {str(e)}"})

    return jsonify({"status": "error", "analysis": "Kimeshindikana kupata jibu kutoka kwa AI."})

if __name__ == '__main__':
    app.run(debug=True)
