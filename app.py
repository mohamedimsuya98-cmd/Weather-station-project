from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import os

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODEL
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
# TRANSLATION FUNCTIONS
# =========================================================

def get_language():

    lang = request.args.get(
        "lang",
        "sw"
    )

    if lang not in ["sw", "en"]:
        lang = "sw"

    return lang


def translate_rain_status(value, lang):

    if value is None:
        return "--"

    value = str(value).strip()


    translations = {

        "Hakuna Mvua": {
            "sw": "Hakuna Mvua",
            "en": "No Rain"
        },

        "Mvua": {
            "sw": "Mvua",
            "en": "Rain"
        },

        "Mvua Ndogo": {
            "sw": "Mvua Ndogo",
            "en": "Light Rain"
        },

        "Mvua Kubwa": {
            "sw": "Mvua Kubwa",
            "en": "Heavy Rain"
        },

        "No Rain": {
            "sw": "Hakuna Mvua",
            "en": "No Rain"
        },

        "Rain": {
            "sw": "Mvua",
            "en": "Rain"
        },

        "Light Rain": {
            "sw": "Mvua Ndogo",
            "en": "Light Rain"
        },

        "Heavy Rain": {
            "sw": "Mvua Kubwa",
            "en": "Heavy Rain"
        }

    }


    return translations.get(
        value,
        {
            "sw": value,
            "en": value
        }
    )[lang]


def translate_wind_direction(value, lang):

    if value is None:
        return "--"

    value = str(value).strip()


    translations = {

        "Kaskazini": {
            "sw": "Kaskazini",
            "en": "North"
        },

        "Kusini": {
            "sw": "Kusini",
            "en": "South"
        },

        "Mashariki": {
            "sw": "Mashariki",
            "en": "East"
        },

        "Magharibi": {
            "sw": "Magharibi",
            "en": "West"
        },

        "Kaskazini-Mashariki": {
            "sw": "Kaskazini-Mashariki",
            "en": "Northeast"
        },

        "Kaskazini-Magharibi": {
            "sw": "Kaskazini-Magharibi",
            "en": "Northwest"
        },

        "Kusini-Mashariki": {
            "sw": "Kusini-Mashariki",
            "en": "Southeast"
        },

        "Kusini-Magharibi": {
            "sw": "Kusini-Magharibi",
            "en": "Southwest"
        },

        "North": {
            "sw": "Kaskazini",
            "en": "North"
        },

        "South": {
            "sw": "Kusini",
            "en": "South"
        },

        "East": {
            "sw": "Mashariki",
            "en": "East"
        },

        "West": {
            "sw": "Magharibi",
            "en": "West"
        },

        "Northeast": {
            "sw": "Kaskazini-Mashariki",
            "en": "Northeast"
        },

        "Northwest": {
            "sw": "Kaskazini-Magharibi",
            "en": "Northwest"
        },

        "Southeast": {
            "sw": "Kusini-Mashariki",
            "en": "Southeast"
        },

        "Southwest": {
            "sw": "Kusini-Magharibi",
            "en": "Southwest"
        }

    }


    return translations.get(
        value,
        {
            "sw": value,
            "en": value
        }
    )[lang]


def translate_wifi_status(is_online, lang):

    if is_online:

        return (
            "Imeunganishwa (Online)"
            if lang == "sw"
            else
            "Connected (Online)"
        )

    return (
        "Haijaunganishwa (Offline)"
        if lang == "sw"
        else
        "Disconnected (Offline)"
    )


def translate_no_device(lang):

    return (
        "Hakuna Kifaa"
        if lang == "sw"
        else
        "No Device"
    )


# =========================================================
# HOME
# =========================================================

@app.route('/')
def home():

    return render_template(
        'index.html',
        data=weather_data
    )


# =========================================================
# ESP32 -> FLASK
# =========================================================

@app.route(
    '/update',
    methods=['POST']
)
def update_weather():

    global weather_data
    global weather_history
    global last_update_time

    data = request.json


    if data:

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


        received_ssid = data.get(
            'wifi_ssid',
            'Haijulikani'
        )


        weather_data['wifi_ssid'] = received_ssid


        last_update_time = datetime.datetime.now()


        current_time = (
            last_update_time.strftime(
                "%H:%M:%S"
            )
        )


        current_date = (
            last_update_time.strftime(
                "%Y-%m-%d"
            )
        )


        # =========================================
        # HISTORY FOR GRAPH
        # =========================================

        weather_history[
            "timestamps"
        ].append(
            current_time
        )


        weather_history[
            "temperatures"
        ].append(
            float(
                weather_data['temperature']
            )
        )


        weather_history[
            "humidities"
        ].append(
            float(
                weather_data['humidity']
            )
        )


        if len(
            weather_history["timestamps"]
        ) > 20:

            weather_history[
                "timestamps"
            ].pop(0)

            weather_history[
                "temperatures"
            ].pop(0)

            weather_history[
                "humidities"
            ].pop(0)


        # =========================================
        # DATABASE
        # =========================================

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
                weather_data[
                    'rain_availability'
                ],

            wind_speed=float(
                weather_data['wind_speed']
            ),

            wind_direction=
                weather_data[
                    'wind_direction'
                ],

            wifi_ssid=received_ssid,

            timestamp=current_time,

            date_recorded=current_date

        )


        db.session.add(
            new_log
        )

        db.session.commit()


        return jsonify({

            "status":
                "success",

            "message":
                "Data imepokelewa!"

        }), 200


    return jsonify({

        "status":
            "error",

        "message":
            "Haikusomeka!"

    }), 400


# =========================================================
# LIVE DATA
# =========================================================

@app.route(
    '/get-data',
    methods=['GET']
)
def get_data():

    global last_update_time


    lang = get_language()


    # SEHEMU ILIYOSAHIHISHWA: Imewekwa kwenye mstari mmoja
    response_data = weather_data.copy()


    response_data[
        "history"
    ] = weather_history


    # =========================================
    # CONNECTION STATUS
    # =========================================

    is_online = False


    if last_update_time:

        time_difference = (
            datetime.datetime.now()
            - last_update_time
        ).total_seconds()


        if time_difference < 30:

            is_online = True


    response_data[
        "is_online"
    ] = is_online


    response_data[
        "wifi_status"
    ] = translate_wifi_status(
        is_online,
        lang
    )


    if is_online:

        response_data[
            "wifi_ssid"
        ] = weather_data.get(
            "wifi_ssid",
            translate_no_device(lang)
        )

    else:

        response_data[
            "wifi_ssid"
        ] = translate_no_device(
            lang
        )


    # =========================================
    # DYNAMIC TRANSLATIONS
    # =========================================

    response_data[
        "rain_availability"
    ] = translate_rain_status(

        weather_data.get(
            "rain_availability"
        ),

        lang

    )


    response_data[
        "wind_direction"
    ] = translate_wind_direction(

        weather_data.get(
            "wind_direction"
        ),

        lang

    )


    return jsonify(
        response_data
    )


# =========================================================
# HISTORY
# =========================================================

@app.route(
    '/get-logs',
    methods=['GET']
)
def get_logs():

    lang = get_language()


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
                translate_rain_status(
                    log.rain_availability,
                    lang
                ),

            "wind_speed":
                log.wind_speed,

            "wind_direction":
                translate_wind_direction(
                    log.wind_direction,
                    lang
                ),

            "wifi_ssid":
                log.wifi_ssid,

            "timestamp":
                log.timestamp,

            "date":
                log.date_recorded

        })


    return jsonify(
        logs_list
    )


# =========================================================
# STATISTICS
# =========================================================

@app.route(
    '/get-stats',
    methods=['GET']
)
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

            "insight":
                "Hakuna kumbukumbu za kutosha bado kwenye mfumo."

        })


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


    avg_temp = round(
        sum(temps) / len(temps),
        1
    )


    max_temp = round(
        max(temps),
        1
    )


    min_temp = round(
        min(temps),
        1
    )


    avg_humidity = round(
        sum(humidities)
        / len(humidities),
        1
    )


    total_rain = round(
        sum(rains),
        2
    )


    avg_wind = round(
        sum(winds)
        / len(winds),
        1
    )


    total_records = len(
        logs
    )


    insight = (
        f"📈 **Uchambuzi wa Mwenendo "
        f"wa Shamba "
        f"(Jumla ya kumbukumbu: "
        f"{total_records}):**\n\n"
    )


    if max_temp > 33:

        insight += (
            f"• **Tahadhari ya Joto Kali:** "
            f"Kiwango cha juu kimefika "
            f"{max_temp}°C. "
            f"Udongo unakauka kwa kasi; "
            f"ongeza umwagiliaji jioni.\n"
        )

    elif min_temp < 18 and min_temp > 0:

        insight += (
            f"• **Tahadhari ya Baridi:** "
            f"Joto limeshuka hadi "
            f"{min_temp}°C, "
            f"punguza kasi ya kumwagilia "
            f"maji ya baridi.\n"
        )

    else:

        insight += (
            f"• **Hali ya Joto:** "
            f"Wastani wa joto upo vizuri "
            f"({avg_temp}°C), "
            f"ukiwa na upeo wa "
            f"{max_temp}°C.\n"
        )


    if total_rain > 10:

        insight += (
            f"• **Mwenendo wa Mvua:** "
            f"Jumla ya mvua "
            f"({total_rain} mm) "
            f"inatosha; simamisha "
            f"umwagiliaji kwa muda.\n"
        )

    elif total_rain > 0:

        insight += (
            f"• **Mwenendo wa Mvua:** "
            f"Mvua ndogo imerekodiwa "
            f"({total_rain} mm).\n"
        )

    else:

        insight += (
            f"• **Mwenendo wa Mvua:** "
            f"Hakuna mvua iliyorekodiwa, "
            f"tegemea umwagiliaji wa bandia.\n"
        )


    if avg_wind > 5.0:

        insight += (
            f"• **Tahadhari ya Upepo:** "
            f"Upepo ni mkali "
            f"({avg_wind} m/s). "
            f"Kuwa makini na ulinzi wa mimea."
        )

    else:

        insight += (
            f"• **Hali ya Upepo:** "
            f"Kasi ya wastani ya upepo "
            f"({avg_wind} m/s) "
            f"iko salama."
        )


    return jsonify({

        "avg_temp":
            avg_temp,

        "max_temp":
            max_temp,

        "min_temp":
            min_temp,

        "avg_humidity":
            avg_humidity,

        "total_rain":
            total_rain,

        "avg_wind":
            avg_wind,

        "total_records":
            total_records,

        "insight":
            insight

    })


# =========================================================
# AI ANALYSIS ENDPOINT
# =========================================================

@app.route(
    '/analyze-ai',
    methods=['GET']
)
def analyze_ai():

    try:

        temp = float(
            weather_data.get(
                'temperature',
                0.0
            )
        )


        humidity = float(
            weather_data.get(
                'humidity',
                0.0
            )
        )


        rain_amt = float(
            weather_data.get(
                'rain_amount',
                0.0
            )
        )


        rain_status = weather_data.get(
            'rain_availability',
            'Hakuna Mvua'
        )


        wind_spd = float(
            weather_data.get(
                'wind_speed',
                0.0
            )
        )


        wind_dir = weather_data.get(
            'wind_direction',
            'Kaskazini'
        )


        if (
            temp == 0.0
            and humidity == 0.0
            and rain_amt == 0.0
            and wind_spd == 0.0
        ):

            analysis = (

                "⚠️ **Tahadhari ya Mfumo:** "
                "Hakuna data halisi zilizopokelewa "
                "kutoka kwenye kihisi (Sensor) "
                "au kifaa cha ESP8266/ESP32.\n\n"

                "**Njia ya Kurekebisha:**\n"

                "1. Hakikisha kifaa chako cha ESP "
                "kimeunganishwa kwenye intaneti.\n"

                "2. Hakikisha kinatuma maombi ya "
                "`POST` kwenda kwenye anuani sahihi "
                "ya `/update`."

            )


            return jsonify({

                "status":
                    "warning",

                "analysis":
                    analysis

            })


        analysis = (
            "🌿 **Uchambuzi wa Kitaalamu "
            "wa Hali ya Hewa "
            "(Live Expert System):**\n\n"
        )


        if temp > 32 and humidity < 45:

            analysis += (
                f"1. **Hali ya Hewa & Unyevu:** "
                f"⚠️ Joto lipo juu sana "
                f"({temp}°C) na unyevu ni mdogo "
                f"({humidity}%). "
                f"**Ushauri:** Ongeza kiwango "
                f"cha kumwagilia.\n"
            )

        elif temp > 32 and humidity >= 45:

            analysis += (
                f"1. **Hali ya Hewa & Unyevu:** "
                f"☀️ Joto ni kali "
                f"({temp}°C) lakini unyevu "
                f"uko sawa ({humidity}%).\n"
            )

        elif temp < 20 and humidity > 75:

            analysis += (
                f"1. **Hali ya Hewa & Unyevu:** "
                f"💧 Joto ni la chini "
                f"({temp}°C) na unyevu uko juu "
                f"({humidity}%). "
                f"**Tahadhari:** Angalia "
                f"magonjwa ya ukungu.\n"
            )

        else:

            analysis += (
                f"1. **Hali ya Hewa & Unyevu:** "
                f"🌱 Hali ya joto "
                f"({temp}°C) na unyevu "
                f"({humidity}%) ziko katika "
                f"uwiano mzuri.\n"
            )


        if (
            rain_amt > 0
            or "Mvua" in rain_status
        ):

            analysis += (
                f"2. **Hali ya Mvua:** "
                f"Mvua imepimwa kiasi cha "
                f"{rain_amt} mm "
                f"({rain_status}).\n"
            )

        else:

            analysis += (
                f"2. **Hali ya Mvua:** "
                f"Hakuna mvua iliyorekodiwa "
                f"({rain_status}).\n"
            )


        if wind_spd > 4.5:

            analysis += (
                f"3. **Hali ya Upepo:** "
                f"💨 Kasi ya upepo ni kali "
                f"({wind_spd} m/s kutoka "
                f"{wind_dir}).\n"
            )

        else:

            analysis += (
                f"3. **Hali ya Upepo:** "
                f"Kasi ya upepo ni tulivu "
                f"({wind_spd} m/s kutoka "
                f"{wind_dir}), hakuna hatari.\n"
            )


        analysis += (
            "\n_Mfumo huu umesanifiwa "
            "kutoa tathmini kwa usahihi "
            "bila kukosa mtandao._"
        )


        return jsonify({

            "status":
                "success",

            "analysis":
                analysis

        })


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "analysis":
                f"Imeshindikana kuchambua "
                f"data: {str(e)}"

        })


# =========================================================
# RUN SERVER
# =========================================================

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
