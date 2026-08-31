import json
import os
import urllib.parse
import urllib.request
import time

CITIES_FILE = "cities.txt"
STATE_FILE = "state.json"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

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
    61: "باران خفیف",
    63: "باران",
    65: "باران شدید",
    71: "برف خفیف",
    73: "برف",
    75: "برف شدید",
    80: "رگبار خفیف",
    81: "رگبار",
    82: "رگبار شدید",
    85: "رگبار برف",
    86: "رگبار برف شدید",
    95: "رعدوبرق",
    96: "رعدوبرق و تگرگ",
    99: "رعدوبرق و تگرگ شدید"
}


def load_cities():
    cities = []

    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()

            if name and not name.startswith("#"):
                cities.append(name)

    return cities


def geocode_city(city):
    params = urllib.parse.urlencode({
        "name": city,
        "count": 1,
        "language": "fa",
        "format": "json"
    })

    url = GEOCODING_URL + "?" + params

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WeatherTelegramBot/1.0"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    results = data.get("results", [])

    if not results:
        raise RuntimeError(f"مکان پیدا نشد: {city}")

    result = results[0]

    return {
        "name": city,
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "timezone": result.get("timezone", "auto")
    }


def get_weather(location):
    params = urllib.parse.urlencode({
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": "temperature_2m,weather_code",
        "temperature_unit": "celsius",
        "timezone": "auto"
    })

    url = WEATHER_URL + "?" + params

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WeatherTelegramBot/1.0"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    current = data["current"]

    temperature = round(float(current["temperature_2m"]), 1)
    code = int(current["weather_code"])

    return {
        "name": location["name"],
        "temperature": temperature,
        "weather_code": code,
        "description": WEATHER_CODES.get(code, "نامشخص")
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError("Telegram Secrets تنظیم نشده‌اند.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError(str(result))


def create_message(weather):
    lines = [
        "🌤 گزارش آب‌وهوا",
        "━━━━━━━━━━━━━━"
    ]

    for item in weather:
        if "error" in item:
            lines.append(
                f"❌ {item['name']}: دریافت اطلاعات ناموفق"
            )
        else:
            lines.append(
                f"📍 {item['name']}\n"
                f"🌡 دما: {item['temperature']}°C\n"
                f"☁️ وضعیت: {item['description']}"
            )

        lines.append("")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("🌐 Open-Meteo")

    return "\n".join(lines)


def main():

    print("Weather bot started.")

    cities = load_cities()

    if not cities:
        print("cities.txt خالی است.")
        return

    old_state = load_state()

    weather_results = []
    new_state = {}

    for city in cities:

        try:
            print(f"Checking: {city}")

            location = geocode_city(city)

            weather = get_weather(location)

            weather_results.append(weather)

            new_state[city] = {
                "temperature": weather["temperature"],
                "weather_code": weather["weather_code"]
            }

        except Exception as e:

            print(f"ERROR - {city}: {e}")

            weather_results.append({
                "name": city,
                "error": str(e)
            })

        time.sleep(0.5)

    if new_state == old_state:
        print("هیچ تغییری در هوا ایجاد نشده.")
        return

    message = create_message(weather_results)

    try:
        send_telegram(message)
        print("پیام تلگرام ارسال شد.")

        save_state(new_state)

    except Exception as e:
        print(f"Telegram ERROR: {e}")


if __name__ == "__main__":
    main()
