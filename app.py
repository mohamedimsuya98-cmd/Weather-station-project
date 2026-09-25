from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    # Hapa ndipo kwenye jina rasmi la shamba lako au kituo chako
    weather_data = {
        "location": "Shamba letu, Pwani",
        "temperature": 28.5,
        "humidity": 65,
        "rain_amount": 0.0,
        "rain_availability": "Hakuna Mvua",
        "wind_speed": 3.2,
        "wind_direction": "Kusini Mashariki"
    }
    return render_template('index.html', data=weather_data)

if __name__ == '__main__':
    app.run(debug=True)
