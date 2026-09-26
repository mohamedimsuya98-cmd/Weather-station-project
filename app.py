```python
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
import requests

app = Flask(__name__)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# Sanidi Database ya SQLite ndani ya mradi
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ============================================================
# WEATHER DATABASE MODEL
# ============================================================

class WeatherLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

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

    # Wind direction ni TEXT/String
    # mfano: Kaskazini, Kusini, NE, SW
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


# Tengeneza database kama haipo
with app.app_context():
    db.create_all()


# ============================================================
# CURRENT WEATHER DATA
# ============================================================

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


# ============================================================
# TEMPORARY HISTORY FOR LIVE CHART
# ============================================================

weather_history = {

    "timestamps": [],

    "temperatures": [],

    "humidities": []
}


# ============================================================
# LAST UPDATE TIME
# ============================================================

last_update_time = None


# ============================================================
# HOME PAGE
# ============================================================

@app.route('/')
def home():

    return render_template(
        'index.html',
        data=weather_data
    )


# ============================================================
# RECEIVE WEATHER DATA FROM ESP32
# ============================================================

@app.route('/update', methods=['POST'])
def update_weather():

    global weather_data
    global weather_history
    global last_update_time

    try:

        data = request.json

        if not data:

            return jsonify({
                "status": "error",
                "message": "Hakuna data iliyopokelewa!"
            }), 400


        # ----------------------------------------------------
        # UPDATE CURRENT WEATHER DATA
        # ----------------------------------------------------

        weather_data['temperature'] = data.get(
            'temperature',
            weather_data['temperature']
        )

        weather_data['humidity'] = data.get(
            'humidity',
            weather_data['humidity']
        )

        weather_data['rain_amount'] = data.get(
            'rain_amount',
            weather_data['rain_amount']
        )

        weather_data['rain_availability'] = data.get(
            'rain_availability',
            weather_data['rain_availability']
        )

        weather_data['wind_speed'] = data.get(
            'wind_speed',
            weather_data['wind_speed']
        )

        weather_data['wind_direction'] = data.get(
            'wind_direction',
            weather_data['wind_direction']
        )


        # ----------------------------------------------------
        # WIFI SSID
        # ----------------------------------------------------

        received_ssid = data.get(
            'wifi_ssid',
            'Haijulikani'
        )

        weather_data['wifi_ssid'] = received_ssid


        # ----------------------------------------------------
        # CURRENT TIME
        # ----------------------------------------------------

        last_update_time = datetime.datetime.now()

        current_time = last_update_time.strftime(
            "%H:%M:%S"
        )

        current_date = last_update_time.strftime(
            "%Y-%m-%d"
        )


        # ----------------------------------------------------
        # LIVE HISTORY
        # ----------------------------------------------------

        weather_history["timestamps"].append(
            current_time
        )

        weather_history["temperatures"].append(
            float(weather_data['temperature'])
        )

        weather_history["humidities"].append(
            float(weather_data['humidity'])
        )


        # Keep only last 20 readings
        if len(weather_history["timestamps"]) > 20:

            weather_history["timestamps"].pop(0)

            weather_history["temperatures"].pop(0)

            weather_history["humidities"].pop(0)


        # ----------------------------------------------------
        # SAVE DATA TO DATABASE
        # ----------------------------------------------------

        new_log = WeatherLog(

            temperature=float(
                weather_data['temperature']
            ),

            humidity=float(
                weather_data['humidity']
            ),

            rain_amount=float(
                weather_data['rain_amount']
            ),

            rain_availability=
                weather_data['rain_availability'],

            wind_speed=float(
                weather_data['wind_speed']
            ),

            # IMPORTANT:
            # Wind direction ni String.
            # HATUTUMII float() hapa.
            wind_direction=
                weather_data['wind_direction'],

            wifi_ssid=received_ssid,

            timestamp=current_time,

            date_recorded=current_date
        )


        db.session.add(new_log)

        db.session.commit()


        return jsonify({

            "status": "success",

            "message":
                "Data imepokelewa na kuhifadhiwa!",

            "data": {

                "temperature":
                    weather_data['temperature'],

                "humidity":
                    weather_data['humidity'],

                "rain_amount":
                    weather_data['rain_amount'],

                "rain_availability":
                    weather_data['rain_availability'],

                "wind_speed":
                    weather_data['wind_speed'],

                "wind_direction":
                    weather_data['wind_direction'],

                "wifi_ssid":
                    weather_data['wifi_ssid']
            }

        }), 200


    except ValueError as e:

        db.session.rollback()

        return jsonify({

            "status": "error",

            "message":
                "Kuna value ya sensor isiyo sahihi.",

            "error":
                str(e)

        }), 400


    except Exception as e:

        db.session.rollback()

        return jsonify({

            "status": "error",

            "message":
                "Hitilafu wakati wa kuhifadhi data.",

            "error":
                str(e)

        }), 500


# ============================================================
# GET CURRENT WEATHER DATA
# ============================================================

@app.route('/get-data', methods=['GET'])
def get_data():

    global last_update_time

    response_data = weather_data.copy()

    response_data["history"] = weather_history


    # --------------------------------------------------------
    # CHECK WEATHER STATION ONLINE STATUS
    # --------------------------------------------------------

    is_online = False


    if last_update_time:

        time_difference = (
            datetime.datetime.now()
            - last_update_time
        ).total_seconds()


        if time_difference < 30:

            is_online = True


    # --------------------------------------------------------
    # WIFI STATUS
    # --------------------------------------------------------

    if is_online:

        response_data["wifi_status"] = (
            "Imeunganishwa (Online)"
        )

    else:

        response_data["wifi_status"] = (
            "Haijaunganishwa (Offline)"
        )

        response_data["wifi_ssid"] = (
            "Hakuna Kifaa"
        )


    return jsonify(response_data)


# ============================================================
# GET WEATHER LOGS
# ============================================================

@app.route('/get-logs', methods=['GET'])
def get_logs():

    try:

        logs = (
            WeatherLog.query
            .order_by(
                WeatherLog.id.desc()
            )
            .limit(50)
            .all()
        )


        logs_list = []


        for log in logs:

            logs_list.append({

                "id":
                    log.id,

                "temperature":
                    log.temperature,

                "humidity":
                    log.humidity,

                "rain_amount":
                    log.rain_amount,

                "rain_availability":
                    log.rain_availability,

                "wind_speed":
                    log.wind_speed,

                "wind_direction":
                    log.wind_direction,

                "wifi_ssid":
                    log.wifi_ssid,

                "timestamp":
                    log.timestamp,

                "date":
                    log.date_recorded
            })


        return jsonify(logs_list)


    except Exception as e:

        return jsonify({

            "status": "error",

            "message":
                str(e)

        }), 500


# ============================================================
# GET WEATHER STATISTICS
# ============================================================

@app.route('/get-stats', methods=['GET'])
def get_stats():

    try:

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


        # ----------------------------------------------------
        # EXTRACT DATA
        # ----------------------------------------------------

        temps = [
            log.temperature
            for log in logs
        ]

        humidities = [
            log.humidity
            for log in logs
        ]

        rains = [
            log.rain_amount
            for log in logs
        ]

        winds = [
            log.wind_speed
            for log in logs
        ]


        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        return jsonify({

            "avg_temp":
                round(
                    sum(temps)
                    / len(temps),
                    1
                ),

            "max_temp":
                round(
                    max(temps),
                    1
                ),

            "min_temp":
                round(
                    min(temps),
                    1
                ),

            "avg_humidity":
                round(
                    sum(humidities)
                    / len(humidities),
                    1
                ),

            "total_rain":
                round(
                    sum(rains),
                    2
                ),

            "avg_wind":
                round(
                    sum(winds)
                    / len(winds),
                    1
                ),

            "total_records":
                len(logs)
        })


    except Exception as e:

        return jsonify({

            "status": "error",

            "message":
                str(e)

        }), 500


# ============================================================
# GEMINI AI ANALYSIS
# ============================================================

@app.route('/analyze-ai', methods=['GET'])
def analyze_ai():

    # --------------------------------------------------------
    # GET GEMINI API KEY
    # --------------------------------------------------------

    gemini_api_key = os.environ.get(
        "GEMINI_API_KEY"
    )


    if not gemini_api_key:

        return jsonify({

            "status": "error",

            "analysis":
                "Samahani, GEMINI_API_KEY haijawekwa kwenye seva ya Render."
        }), 500


    # --------------------------------------------------------
    # GEMINI 2.5 FLASH
    # FREE TIER
    # --------------------------------------------------------

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-2.5-flash:"
        "generateContent"
        f"?key={gemini_api_key}"
    )


    headers = {

        "Content-Type":
            "application/json"
    }


    # --------------------------------------------------------
    # AI PROMPT
    # --------------------------------------------------------

    prompt = f"""

Wewe ni mtaalamu wa hali ya hewa na kilimo cha kisasa.

Changanua taarifa hizi kutoka kwenye kituo cha
hali ya hewa cha shamba:

JOTO:
{weather_data['temperature']} °C

UNYEVU WA HEWA:
{weather_data['humidity']} %

KIASI CHA MVUA:
{weather_data['rain_amount']} mm

HALI YA MVUA:
{weather_data['rain_availability']}

KASI YA UPEPO:
{weather_data['wind_speed']} m/s

MWELEKEO WA UPEPO:
{weather_data['wind_direction']}


Toa uchambuzi mfupi na wa vitendo kwa mkulima
kwa lugha ya Kiswahili.

Zingatia:

1. Hali ya sasa ya mazingira.
2. Maana ya temperature na humidity.
3. Hali ya mvua iliyopimwa.
4. Kama umwagiliaji unaweza kuhitajika.
5. Athari zinazoweza kutokana na upepo.
6. Hatua ambazo mkulima anaweza kuzingatia.
7. Tahadhari yoyote muhimu kwa mazao.

Usidai kuwa unajua hali ya hewa ya baadaye
kwa uhakika ikiwa hakuna forecast data.

Tumia data iliyopimwa na weather station kama
msingi wa uchambuzi.

Jibu kwa lugha rahisi, fupi na ya kitaalamu.
"""


    # --------------------------------------------------------
    # GEMINI REQUEST PAYLOAD
    # --------------------------------------------------------

    payload = {

        "contents": [

            {

                "parts": [

                    {
                        "text": prompt
                    }

                ]
            }

        ],

        "generationConfig": {

            "temperature": 0.4,

            "maxOutputTokens": 600
        }
    }


    # --------------------------------------------------------
    # SEND REQUEST TO GEMINI
    # --------------------------------------------------------

    try:

        response = requests.post(

            url,

            json=payload,

            headers=headers,

            timeout=30
        )


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            res_json = response.json()


            candidates = res_json.get(
                "candidates",
                []
            )


            if not candidates:

                return jsonify({

                    "status": "error",

                    "analysis":
                        "Gemini haikurudisha majibu."
                }), 500


            analysis_text = (
                candidates[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )


            if not analysis_text:

                return jsonify({

                    "status": "error",

                    "analysis":
                        "Gemini imerudisha majibu tupu."
                }), 500


            return jsonify({

                "status": "success",

                "analysis":
                    analysis_text
            })


        # ----------------------------------------------------
        # API ERROR
        # ----------------------------------------------------

        else:

            return jsonify({

                "status": "error",

                "analysis":
                    "Hitilafu kutoka Gemini API.",

                "details":
                    response.text

            }), response.status_code


    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    except requests.exceptions.Timeout:

        return jsonify({

            "status": "error",

            "analysis":
                "Gemini imechukua muda mrefu kujibu. Jaribu tena."
        }), 504


    # --------------------------------------------------------
    # CONNECTION ERROR
    # --------------------------------------------------------

    except requests.exceptions.RequestException as e:

        return jsonify({

            "status": "error",

            "analysis":
                "Imeshindikana kuunganisha na Gemini.",

            "details":
                str(e)

        }), 500


    # --------------------------------------------------------
    # OTHER ERROR
    # --------------------------------------------------------

    except Exception as e:

        return jsonify({

            "status": "error",

            "analysis":
                "Hitilafu isiyotarajiwa imetokea.",

            "details":
                str(e)

        }), 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == '__main__':

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(

        host='0.0.0.0',

        port=port,

        debug=False
    )
```
