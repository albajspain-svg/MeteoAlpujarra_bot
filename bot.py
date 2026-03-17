import os
import json
import logging
from datetime import time
import requests
import pytz
from math import sqrt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

TEST_MODE = True

chat_info = {}
town_coords = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos", "Busquístar", "Atalbéitar",
    "Pitres", "Mecina", "Fondales", "Ferreirola", "Capilerilla", "Mecinilla",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Turón", "Válor", "Yegen"
]

TEXTS = {
    "es": {
        "welcome": "🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma",
        "select": "Elige tu pueblo:",
        "ok": "✅ Activado para {}",
        "city": "Escribe /ciudad Nombre",
        "morning": "☀️ Mañana",
        "afternoon": "🌇 Tarde",
        "uv_low": "UV bajo 🌤️",
        "uv_medium": "UV medio ☀️",
        "uv_high": "UV alto 🧴",
        "advice_hot": "Hace calor 😎, ropa ligera y bebe agua",
        "advice_cold": "Hace frío 🧥, abrígate bien",
        "advice_rain": "Llueve 🌧️, lleva paraguas/impermeable"
    }
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

def preload_town_coords():
    for town in TOWNS:
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1&country=ES&language=es"
            res = requests.get(url, timeout=10).json()
            if res.get("results"):
                r = res["results"][0]
                town_coords[town] = (r["latitude"], r["longitude"])
                logging.info(f"Coordenadas OK: {town} → {r['latitude']}, {r['longitude']}")
            else:
                town_coords[town] = (None, None)
                logging.warning(f"Sin coordenadas válidas para {town}")
        except Exception as e:
            town_coords[town] = (None, None)
            logging.error(f"Error geocoding {town}: {str(e)}")

def meteo(lat, lon):
    if not lat or not lon:
        return {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m&timezone=Europe/Madrid"
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()
        logging.info(f"API meteo respuesta para {lat},{lon}: {data.get('daily', 'sin daily')}")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Fallo API Open-Meteo: {str(e)}")
        return {}
    except Exception as e:
        logging.error(f"Error inesperado en meteo: {str(e)}")
        return {}

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return

    info = chat_info[chat_id]
    lat = info.get("lat")
    lon = info.get("lon")
    nombre = info.get("nombre", "Pueblo desconocido")

    data = meteo(lat, lon)

    if not data or "daily" not in data or len(data["daily"].get("time", [])) == 0:
        msg = f"⚠️ {nombre}\nNo se pudo obtener el tiempo ahora.\nPosible causa: coordenadas inválidas o API sin respuesta."
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            logging.error(f"No pude enviar aviso a {chat_id}: {e}")
        return

    # Datos OK
    daily = data["daily"]
    current = data.get("current_weather", {})

    max_t = daily["temperature_2m_max"][0]
    min_t = daily["temperature_2m_min"][0]
    rain_p = daily["precipitation_probability_max"][0]
    uv = daily["uv_index_max"][0]
    wind = daily["wind_speed_10m"][0]
    curr_t = current.get("temperature", (min_t + max_t) // 2)

    prefix = "🧪 PRUEBA " if TEST_MODE else ""
    is_tarde = (not TEST_MODE) and "weather_e" in context.job.name

    msg = f"{prefix}📍 {nombre}\n\n"
    msg += f"🕗 {'Tarde' if is_tarde else 'Mañana'}\n"
    msg += f"🌡️ {curr_t}°C   Mín {min_t}°C   Máx {max_t}°C\n"
    msg += f"🌬️ {wind:.0f} km/h   {uv_desc(uv, chat_id)}\n"
    msg += f"{clothing_advice(max_t, rain_p, chat_id)}"

    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, disable_notification=TEST_MODE)
    except Exception as e:
        logging.error(f"Error enviando mensaje: {e}")

# ... (el resto de funciones igual: wind_scale, thermal_feel, uv_desc, clothing_advice, test_send, start, kb_lang, kb_towns, remove_jobs, buttons, ciudad, load_users, save_users)

def main():
    if not TOKEN:
        print("Falta TOKEN")
        return

    print("Cargando coordenadas...")
    preload_town_coords()
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CommandHandler("test", test_send))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot iniciado")
    app.run_polling()

if __name__ == "__main__":
    main()
