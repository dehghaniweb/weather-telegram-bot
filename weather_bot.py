import json
import os
import urllib.parse
import urllib.request


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TELEGRAM_URL = "https://api.telegram.org/bot{}/sendMessage"

CITIES_FILE = "cities.txt"
STATE_FILE = "state.json"


# --------------------------------------------------
# Weather code -> Persian description
# --------------------------------------------------

WEATHER_CODES = {
    0: "صاف",
    1: "عمدتاً صاف",
    2: "نیمه‌ابری",
    3: "ابری",
    45: "مه‌آلود",
    48: "مه یخ‌زننده",
    51: "نم‌نم باران",
    53: "باران خفیف",
    55: "باران",
    56: "نم‌نم باران یخ‌زننده",
    57: "باران یخ‌زننده",
    61: "باران خفیف",
    63: "باران",
    65: "باران شدید",
    66: "باران یخ‌زننده خفیف",
    67: "باران یخ‌زننده شدید",
    71: "برف خفیف",
    73: "برف",
    75: "برف شدید",
    77: "دانه‌های برف",
    80: "رگبار خفیف",
    81: "رگبار",
    82: "رگبار شدید",
    85: "رگبار برف خفیف",
    86: "رگبار برف شدید",
    95: "رعدوبرق",
    96: "رعدوبرق و تگرگ خفیف",
    99: "رعدوبرق و تگرگ شدید",
}


# --------------------------------------------------
# Read cities.txt
# --------------------------------------------------

def load_cities():
    cities = []

    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            parts = line.split("|")

            if len(parts) != 3:
                print(f"Invalid city line: {line}")
                continue

            name = parts[0].strip()

            try:
                latitude = float(parts[1].strip())
                longitude = float(parts[2].strip())
            except ValueError:
                print(f"Invalid coordinates: {line}")
                continue

            cities.append({
                "name": name,
                "latitude": latitude,
                "longitude": longitude
            })

    return cities


# --------------------------------------------------
# Get weather from Open-Meteo
# --------------------------------------------------

def get_weather(cities):
    if not cities:
        raise RuntimeError("No cities found.")

    latitudes = ",".join(str(c["latitude"]) for c in cities)
    longitudes = ",".join(str(c["longitude"]) for c in cities)

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "current": "temperature_2m,weather_code",
        "temperature_unit": "celsius",
        "timezone": "auto"
    }

    url = OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TelegramWeatherBot/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    # Multiple locations -> list
    if isinstance(data, list):
        results = data
    else:
        results = [data]

    weather = []

    for city, result in zip(cities, results):

        try:
            current = result["current"]

            temperature = current["temperature_2m"]
            weather_code = current["weather_code"]

            weather.append({
                "name": city["name"],
                "temperature": round(float(temperature), 1),
                "weather_code": int(weather_code),
                "description": WEATHER_CODES.get(
                    int(weather_code),
                    "نامشخص"
                ),
                "error": None
            })

        except Exception as e:

            weather.append({
                "name": city["name"],
                "temperature": None,
                "weather_code": None,
                "description": None,
                "error": str(e)
            })

    return weather


# --------------------------------------------------
# Load previous state
# --------------------------------------------------

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


# --------------------------------------------------
# Save current state
# --------------------------------------------------

def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


# --------------------------------------------------
# Send Telegram message
# --------------------------------------------------

def send_telegram(message):

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not set.")

    url = TELEGRAM_URL.format(token)

    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TelegramWeatherBot/1.0"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram error: {result}"
        )


# --------------------------------------------------
# Create readable Telegram message
# --------------------------------------------------

def create_message(weather):

    lines = [
        "🌤 گزارش آب‌وهوا",
        "━━━━━━━━━━━━━━"
    ]

    for item in weather:

        if item["error"]:

            lines.append(
                f"❌ {item['name']}: خطا در دریافت اطلاعات"
            )

        else:

            lines.append(
                f"📍 {item['name']}\n"
                f"🌡 دما: {item['temperature']}°C\n"
                f"☁️ وضعیت: {item['description']}"
            )

        lines.append("")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("Source: Open-Meteo")

    return "\n".join(lines)


# --------------------------------------------------
# Check whether weather changed
# --------------------------------------------------

def has_changed(weather, old_state):

    new_state = {}

    for item in weather:

        name = item["name"]

        if item["error"]:

            value = {
                "status": "error"
            }

        else:

            value = {
                "temperature": item["temperature"],
                "weather_code": item["weather_code"]
            }

        new_state[name] = value

    changed = new_state != old_state

    return changed, new_state


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Starting weather bot...")

    cities = load_cities()

    print(f"Loaded {len(cities)} cities.")

    if not cities:
        raise RuntimeError("cities.txt is empty.")

    old_state = load_state()

    try:

        weather = get_weather(cities)

    except Exception as e:

        print(f"Open-Meteo error: {e}")

        # Do not stop the workflow
        return

    changed, new_state = has_changed(
        weather,
        old_state
    )

    if not changed:

        print("No weather changes. Telegram message will not be sent.")

        return

    message = create_message(weather)

    try:

        send_telegram(message)

        print("Telegram message sent successfully.")

        # Save only after successful Telegram delivery
        save_state(new_state)

    except Exception as e:

        print(f"Telegram error: {e}")


if __name__ == "__main__":
    main()
