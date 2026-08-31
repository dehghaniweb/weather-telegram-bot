import json
import os
import urllib.parse
import urllib.request

CITIES_FILE = "cities.txt"
STATE_FILE = "state.json"

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
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split("|")

            if len(parts) != 3:
                print(f"خطای فرمت شهر: {line}")
                continue

            try:
                name = parts[0].strip()
                latitude = float(parts[1])
                longitude = float(parts[2])

                cities.append({
                    "name": name,
                    "latitude": latitude,
                    "longitude": longitude
                })

            except ValueError:
                print(f"مختصات نامعتبر: {line}")

    return cities


def get_weather(city):

    params = urllib.parse.urlencode({
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "current": "temperature_2m,weather_code",
        "temperature_unit": "celsius",
        "timezone": "auto"
    })

    url = WEATHER_URL + "?" + params

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WeatherTelegramBot/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )

    current = data["current"]

    temperature = round(
        float(current["temperature_2m"]),
        1
    )

    weather_code = int(
        current["weather_code"]
    )

    return {
        "name": city["name"],
        "temperature": temperature,
        "weather_code": weather_code,
        "description": WEATHER_CODES.get(
            weather_code,
            "نامشخص"
        )
    }


def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {}


def save_state(state):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


def send_telegram(message):

    token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN تنظیم نشده است."
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID تنظیم نشده است."
        )

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram error: {result}"
        )


def create_message(weather):

    lines = [
        "🌤 گزارش آب‌وهوا",
        "━━━━━━━━━━━━━━"
    ]

    for item in weather:

        if item.get("error"):

            lines.append(
                f"❌ {item['name']}: "
                f"خطا در دریافت اطلاعات"
            )

        else:

            lines.append(
                f"📍 {item['name']}\n"
                f"🌡 دما: "
                f"{item['temperature']}°C\n"
                f"☁️ وضعیت: "
                f"{item['description']}"
            )

        lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━"
    )

    lines.append(
        "🌐 Open-Meteo"
    )

    return "\n".join(lines)


def main():

    print("Weather bot started.")

    cities = load_cities()

    if not cities:
        print(
            "هیچ شهری در cities.txt پیدا نشد."
        )
        return

    old_state = load_state()

    weather_results = []
    new_state = {}

    for city in cities:

        try:

            print(
                f"Checking: {city['name']}"
            )

            weather = get_weather(city)

            weather_results.append(
                weather
            )

            new_state[
                city["name"]
            ] = {
                "temperature":
                    weather["temperature"],

                "weather_code":
                    weather["weather_code"]
            }

        except Exception as e:

            print(
                f"ERROR - "
                f"{city['name']}: {e}"
            )

            weather_results.append({
                "name": city["name"],
                "error": str(e)
            })

    # اگر از طریق دکمه تلگرام اجرا شده باشد،
    # همیشه گزارش را ارسال کن.
    manual_request = os.environ.get(
        "MANUAL_REQUEST",
        "false"
    ).lower() == "true"

    if not manual_request and new_state == old_state:

        print(
            "هیچ تغییری در وضعیت هوا "
            "ایجاد نشده است."
        )

        return

    message = create_message(
        weather_results
    )

    try:

        send_telegram(message)

        print(
            "پیام تلگرام با موفقیت ارسال شد."
        )

        save_state(new_state)

    except Exception as e:

        print(
            f"Telegram ERROR: {e}"
        )


if __name__ == "__main__":
    main()
