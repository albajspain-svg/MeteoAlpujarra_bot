import os
import json
import logging
from datetime import time, timedelta
import requests
import pytz
from math import sqrt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

# ================= CONFIGURACIÓN ==================
TEST_MODE = True          # ← CAMBIA A False cuando quieras horario real (07:57 y 19:57)
REAL_TIME = True          # True = cada 5 min (en test) | False = solo mañana y tarde

chat_info = {}
town_coords = {}

logging.basicConfig(level=logging.INFO)

TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos", "Busquístar", "Atalbéitar",
    "Pitres", "Mecina", "Fondales", "Ferreirola", "Capilerilla", "Mecinilla",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Turón", "Válor", "Yegen"
]

TEXTS = {  # ... (sin cambios, mantengo igual) 
    "es": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma", ...},  # resto igual
    # otros idiomas ...
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, "")

# ================= COORDENADAS ==================
def preload_town_coords():
    for town in TOWNS:
        try:
            res = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",
                timeout=10
            ).json()
            if res.get("results"):
                r = res["results"][0]
                town_coords[town] = (r["latitude"], r["longitude"])
            else:
                town_coords[town] = (None, None)
        except Exception as e:
            logging.warning(f"No se pudo obtener coordenadas de {town}: {e}")
            town_coords[town] = (None, None)

# ================= METEO (sin cambios importantes) ==================
def meteo(lat, lon):
    if lat is None or lon is None:
        return {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m&timezone=Europe/Madrid"
    try:
        return requests.get(url, timeout=10).json()
    except:
        return {}

# ... (wind_scale, thermal_feel, uv_desc, clothing_advice sin cambios)

# ================= ENVÍO DE MENSAJE ==================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return
    
    info = chat_info[chat_id]
    data = meteo(info["lat"], info["lon"])
    
    if not data or not data.get("daily", {}).get("temperature_2m_max"):
        await context.bot.send_message(chat_id, "⚠️ No se pudo obtener el tiempo en este momento.")
        return

    daily = data.get("daily", {})
    current = data.get("current_weather", {})
    
    max_temp = daily.get("temperature_2m_max", [0])[0]
    min_temp = daily.get("temperature_2m_min", [0])[0]
    rain_prob = daily.get("precipitation_probability_max", [0])[0]
    uv = daily.get("uv_index_max", [0])[0]
    wind = daily.get("wind_speed_10m", [0])[0]
    current_temp = current.get("temperature", (min_temp + max_temp) // 2)

    prefix = "🧪 PRUEBA " if TEST_MODE else ""
    moment = "Mañana (prueba)" if TEST_MODE else "Mañana"
    if not TEST_MODE and "weather_e" in context.job.name:
        moment = "Tarde (prueba)" if TEST_MODE else "Tarde"

    msg = f"{prefix}📍 {info['nombre']}\n\n"
    msg += f"🕗 {moment}:\n"
    msg += f"{thermal_feel(current_temp, wind)} | 🌡️ {current_temp}°C | Mín {min_temp}°C | Máx {max_temp}°C\n"
    msg += f"🌬️ {wind_scale(wind)} | {uv_desc(uv, chat_id)} | {clothing_advice(max_temp, rain_prob, chat_id)}\n"

    if not TEST_MODE and "weather_e" in context.job.name:
        msg += "\n(Tarde – pronóstico actualizado)"

    await context.bot.send_message(chat_id, msg)

# ================= HANDLERS (casi sin cambios) ==================
# start, buttons, ciudad ... (mantener igual)

# Solo modificamos la parte de programación de jobs en buttons
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.from_user.id

    if data.startswith("lang_"):
        lang = data.replace("lang_", "")
        chat_info.setdefault(chat_id, {})["lang"] = lang
        save_users()
        await query.edit_message_text(t(chat_id, "select"), reply_markup=kb_towns())

    elif data.startswith("town_"):
        town = data.replace("town_", "")
        lat, lon = town_coords.get(town, (None, None))
        if lat is None:
            await query.edit_message_text("No se encontraron coordenadas para este pueblo 😕")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        chat_info[chat_id]["lat"] = lat
        chat_info[chat_id]["lon"] = lon
        save_users()

        remove_jobs(context.application, chat_id)

        tz = pytz.timezone('Europe/Madrid')

        if TEST_MODE:
            # Modo pruebas → cada 5 minutos
            context.application.job_queue.run_repeating(
                send_weather,
                interval=300,           # 5 minutos
                first=10,               # empieza pronto
                name=f"weather_test_{chat_id}",
                data={"chat_id": chat_id}
            )
            await query.edit_message_text(f"🧪 Modo PRUEBAS activado para {town}\nMensajes cada 5 minutos")
        else:
            # Modo real → 3 minutos antes de las 8 y 20
            morning_time = time(7, 57, tzinfo=tz)
            evening_time = time(19, 57, tzinfo=tz)

            context.application.job_queue.run_daily(
                send_weather,
                time=morning_time,
                name=f"weather_m_{chat_id}",
                data={"chat_id": chat_id}
            )
            context.application.job_queue.run_daily(
                send_weather,
                time=evening_time,
                name=f"weather_e_{chat_id}",
                data={"chat_id": chat_id}
            )
            await query.edit_message_text(t(chat_id, "ok").format(town) + "\n(3 min antes de 8h y 20h)")

# ... resto del código igual (ciudad, load_users, save_users, main, etc.)

def main():
    print("⏳ Cargando coordenadas de pueblos...")
    preload_town_coords()
    load_users()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))
    print("🤖 MeteoAlpujarra PRO funcionando")
    app.run_polling()

if __name__ == "__main__":
    main()
