from flask import Flask, render_template, request, jsonify
import datetime
import os
from google import genai

app = Flask(__name__)

# Sanidi Gemini Client (Hakikisha unaweka API Key yako au mazingira ya Render)
# Unaweza kuweka key yako moja kwa moja kwenye mabano au kuhakikisha GEMINI_API_KEY ipo kwenye Render Environment Variables
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
        
        weather_history["timestamps"].append(current_time)
        weather_history["temperatures"].append(float(weather_data['temperature']))
        weather_history["humidities"].append(float(weather_data['humidity']))
        
        if len(weather_history["timestamps"]) > 20:
            weather_history["timestamps"].pop(0)
            weather_history["temperatures"].pop(0)
            weather_history["humidities"].pop(0)
            
        return jsonify({"status": "success", "message": "Data imepokelewa!"}), 200
    
    return jsonify({"status": "error", "message": "Haikusomeka!"}), 400

@app.route('/get-data', methods=['GET'])
def get_data():
    response_data = weather_data.copy()
    response_data["history"] = weather_history
    return jsonify(response_data)

# Sehemu mpya ya kuchakata uchambuzi wa AI kihalisia
@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():
    try:
        # Tunga ujumbe wa kumuagiza AI kulingana na data za sasa za shambani
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
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        return jsonify({"status": "success", "analysis": response.text})
    except Exception as e:
        return jsonify({"status": "error", "analysis": f"Imeshindikana kuchambua kwa sasa: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
