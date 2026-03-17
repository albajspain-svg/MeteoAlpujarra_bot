import os
import json
import logging
from datetime import time, datetime
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"
TEST_MODE = True

chat_info = {}

# ====================== LOG ======================
logging.basicConfig(level=logging.INFO)

# ====================== DB ======================
def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            chat_info = {int(k): v for k, v in data.items()}
    except:
        chat_info = {}

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in chat_info.items()}, f, indent=2)

# ====================== PUEBLOS ======================
TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos",
    "Busquístar", "Atalbéitar", "Pitres", "Mecina Fondales",
    "Ferreirola", "Fondales", "Capilerilla",
    "Los Tablones", "Bayacas", "Las Barreras",
    "El Morreón", "Los Cigarrones"
]

# ====================== METEO ======================
def meteo(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weathercode,wind_speed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&timezone=auto"
    )
    try:
        return requests.get(url, timeout=10).json()
    except:
        return {}

def weather_desc(code):
    return {
        0: "☀️ Despejado",
        1: "🌤️ Poco nuboso",
        2: "⛅ Parcialmente nublado",
        3: "☁️ Nublado",
        45: "🌫️ Niebla",
        61: "🌧️ Lluvia",
        71: "❄️ Nieve",
    }.get(code, "🌡️ Clima variable")

def wind_scale(kmh):
    if kmh is None:
        return "?"
    scale = min(10, round(kmh / 6))
    if scale <= 2:
        desc = "Calma"
    elif scale <= 5:
        desc = "Suave"
    elif scale <= 7:
        desc = "Moderado"
    else:
        desc = "Fuerte"
    return f"{scale}/10 ({desc})"

# ====================== UI ======================
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def kb_towns():
    rows = [[InlineKeyboardButton(t, callback_data=f"town_{t}")] for t in TOWNS]
    rows.append([InlineKeyboardButton("🌍 Otro", callback_data="otros")])
    return InlineKeyboardMarkup(rows)

# ====================== JOBS ======================
def remove_jobs(app, chat_id):
    if not app.job_queue:
        return
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]

    if chat_id not in chat_info:
        return

    info = chat_info[chat_id]
    data = meteo(info["lat"], info["lon"])

    current = data.get("current", {})
    daily = data.get("daily", {})

    wind = current.get("wind_speed_10m")

    try:
        msg = (
            f"📍 {info['nombre']}\n\n"
            f"🌡️ Ahora: {current.get('temperature_2m','?')}°C\n"
            f"{weather_desc(current.get('weathercode'))}\n"
            f"🌬️ Viento: {wind} km/h · {wind_scale(wind)}\n\n"

            f"📅 Hoy\n"
            f"⬆️ {daily['temperature_2m_max'][0]}°C\n"
            f"⬇️ {daily['temperature_2m_min'][0]}°C\n"
            f"🌧️ {daily['precipitation_probability_max'][0]}%\n\n"

            f"📅 Mañana\n"
            f"⬆️ {daily['temperature_2m_max'][1]}°C\n"
            f"⬇️ {daily['temperature_2m_min'][1]}°C\n"
            f"🌧️ {daily['precipitation_probability_max'][1]}%\n\n"

            f"🕒 {datetime.now().strftime('%H:%M')}"
        )
    except:
        msg = "❌ Error obteniendo datos"

    await context.bot.send_message(chat_id, msg)

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌦️ MeteoAlpujarra\n\nSelecciona idioma:",
        reply_markup=kb_lang()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.from_user.id

    if data.startswith("lang_"):
        await query.edit_message_text(
            "Elige tu pueblo:",
            reply_markup=kb_towns()
        )

    elif data.startswith("town_"):
        town = data.replace("town_", "")

        res = requests.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",
            timeout=10
        ).json()

        if not res.get("results"):
            await query.edit_message_text("❌ No encontrado")
            return

        r = res["results"][0]

        chat_info[chat_id] = {
            "nombre": r["name"],
            "lat": r["latitude"],
            "lon": r["longitude"]
        }
        save_users()

        remove_jobs(context.application, chat_id)

        context.application.job_queue.run_repeating(
            send_weather,
            interval=300 if TEST_MODE else 43200,
            first=5,
            name=f"weather_{chat_id}",
            data={"chat_id": chat_id}
        )

        await query.edit_message_text(f"✅ Activado para {r['name']}")

    elif data == "otros":
        await query.edit_message_text("Escribe /ciudad Nombre")

# ====================== COMANDOS ======================
async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usa /ciudad Nombre")
        return

    town = " ".join(context.args)

    res = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",
        timeout=10
    ).json()

    if not res.get("results"):
        await update.message.reply_text("❌ No encontrado")
        return

    r = res["results"][0]
    chat_id = update.effective_chat.id

    chat_info[chat_id] = {
        "nombre": r["name"],
        "lat": r["latitude"],
        "lon": r["longitude"]
    }
    save_users()

    await update.message.reply_text(f"✅ {r['name']} guardado")

# ====================== MAIN ======================
def main():
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 MeteoAlpujarra PRO MAX funcionando")

    app.run_polling()

if __name__ == "__main__":
    main()
