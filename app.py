from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Hapa zinapohifadhiwa data za mwisho zilizotumwa na Weather Station
latest_weather_data = {
    "temperature": 0.0,
    "humidity": 0.0,
    "wind_speed": 0.0,
    "soil_moisture": 0.0
}

@app.route('/')
def index():
    # Kuonyesha Dashboard na data pamoja na uchambuzi wa AI
    ai_recommendation = analyze_with_ai(latest_weather_data)
    return render_template('index.html', data=latest_weather_data, recommendation=ai_recommendation)

@app.route('/update', methods=['POST'])
def update_data():
    global latest_weather_data
    content = request.json
    if content:
        latest_weather_data['temperature'] = content.get('temperature', 0)
        latest_weather_data['humidity'] = content.get('humidity', 0)
        latest_weather_data['wind_speed'] = content.get('wind_speed', 0)
        latest_weather_data['soil_moisture'] = content.get('soil_moisture', 0)
        return jsonify({"status": "success", "message": "Data zimepokelewa vizuri!"}), 200
    return jsonify({"status": "error", "message": "Data hazijasomeka!"}), 400

def analyze_with_ai(data):
    temp = data['temperature']
    humidity = data['humidity']
    soil = data['soil_moisture']
    
    # Mantiki ya AI ya awali ya kuchambua hali ya hewa
    if soil < 30 and temp > 30:
        return "Hali ya hewa ni ya ukame na joto kali. Mazao yanayofaa ni mtama au mihogo. Inashauriwa kutumia mfumo wa matone (drip irrigation) kumwagilia mara mbili kwa siku."
    elif humidity > 80:
        return "Unyevunyevu uko juu sana. Hali hii inaweza kuleta fangasi kwenye mazao ya mahindi au nyanya. Zingatia kupuliza dawa ya kinga na kuhakikisha nafasi kati ya mimea inatosha."
    else:
        return "Hali ya hewa ni nzuri na ya wastani. Inafaa kwa kilimo cha mboga mboga na mahindi. Hakikisha palizi inafanyika kwa wakati."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)