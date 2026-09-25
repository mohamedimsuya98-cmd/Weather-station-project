from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Hapa tunatunza data za awali (Default) endapo ESP32 bado haijatuma data
weather_data = {
    "location": "Shamba Langu, Dar es Salaam",
    "temperature": "0.0",
    "humidity": "0",
    "rain_amount": "0.0",
    "rain_availability": "Hakuna Mvua",
    "wind_speed": "0.0",
    "wind_direction": "Kaskazini"
}

@app.route('/')
def home():
    # Inatuma data za sasa kwenda kwenye index.html
    return render_template('index.html', data=weather_data)

# Njia (API Endpoint) inayotumiwa na ESP32 kutuma data
@app.route('/update', methods=['POST'])
def update_weather():
    global weather_data
    data = request.json # Inapokea JSON kutoka ESP32
    
    if data:
        weather_data['temperature'] = data.get('temperature', weather_data['temperature'])
        weather_data['humidity'] = data.get('humidity', weather_data['humidity'])
        weather_data['rain_amount'] = data.get('rain_amount', weather_data['rain_amount'])
        weather_data['rain_availability'] = data.get('rain_availability', weather_data['rain_availability'])
        weather_data['wind_speed'] = data.get('wind_speed', weather_data['wind_speed'])
        weather_data['wind_direction'] = data.get('wind_direction', weather_data['wind_direction'])
        
        return jsonify({"status": "success", "message": "Data imepokelewa kikamilifu!"}), 200
    
    return jsonify({"status": "error", "message": "Hakuna data iliyotumwa!"}), 400

# Njia mpya inayoruhusu ukurasa kuchukua data moja kwa moja bila ku-refresh
@app.route('/get-data', methods=['GET'])
def get_data():
    return jsonify(weather_data)

if __name__ == '__main__':
    app.run(debug=True)
