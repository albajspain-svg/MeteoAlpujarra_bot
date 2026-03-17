import os
import json
import logging
from datetime import time
import requests
import pytz
from math import sqrt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

# ================= CONFIGURACIÓN ==================
TEST_MODE = True          # ← Cambia a False cuando quieras horario real (07:57 y 19:57)

chat_info = {}
town_coords = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

# ================= COORDENADAS (CORREGIDO) ==================
def preload_town_coords():
    for town in TOWNS:
        try:
            res = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1&country=ES&language=es",
                timeout=10
            ).json()
            if res.get("results"):
                r = res["results"][0]
                town_coords[town] = (r["latitude"], r["longitude"])
                logging.info(f"✅ {town} → {r['latitude']}, {r['longitude']}")
            else:
                town_coords[town] = (None, None)
                logging.warning(f"❌ Sin coordenadas: {town}")
        except Exception as e:
            town_coords[town] = (None, None)
            logging.error(f"Error geocoding {town}: {e}")

# ================= METEO ==================
def meteo(lat, lon):
    if lat is None or lon is None:
        return {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m&timezone=Europe/Madrid"
    try:
        return requests.get(url, timeout=12).json()
    except Exception as e:
        logging.error(f"Error API Open-Meteo: {e}")
        return {}

# ================= FUNCIONES AUXILIARES ==================
def wind_scale(kmh):
    if kmh is None: return "?"
    scale = min(10, round(kmh / 6))
    return f"{kmh} km/h | {scale}/10"

def thermal_feel(temp, wind):
    if temp is None or wind is None: return ""
    feel = temp - sqrt(wind) / 3
    return f"🌡️ Sens. térmica: {round(feel)}°C"

def uv_desc(uv, chat_id):
    if uv < 3: return t(chat_id, "uv_low")
    if uv < 6: return t(chat_id, "uv_medium")
    return t(chat_id, "uv_high")

def clothing_advice(temp, rain, chat_id):
    if rain > 30: return t(chat_id, "advice_rain")
    if temp >= 28: return t(chat_id, "advice_hot")
    if temp <= 15: return t(chat_id, "advice_cold")
    return ""

# ================= ENVÍO (SIEMPRE ENVÍA ALGO) ==================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return

    info = chat_info[chat_id]
    data = meteo(info.get("lat"), info.get("lon"))

    if not data or "daily" not in data or not data["daily"].get("temperature_2m_max"):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ {info.get('nombre', 'Pueblo')}:\nNo se pudo obtener el tiempo ahora.\nReintenta en unos minutos."
            )
            logging.warning(f"No datos meteo para {info.get('nombre')}")
        except Exception as e:
            logging.error(f"Error enviando aviso: {e}")
        return

    # Datos correctos → mensaje normal
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

    msg = f"{prefix}📍 {info['nombre']}\n\n"
    msg += f"🕗 {'Tarde' if is_tarde else 'Mañana'}\n"
    msg += f"{thermal_feel(curr_t, wind)}\n"
    msg += f"🌡️ {curr_t}°C   Mín {min_t}°C   Máx {max_t}°C\n"
    msg += f"🌬️ {wind_scale(wind)}   {uv_desc(uv, chat_id)}\n"
    msg += f"{clothing_advice(max_t, rain_p, chat_id)}"

    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, disable_notification=TEST_MODE)
        logging.info(f"✅ Mensaje enviado a {chat_id} ({info.get('nombre')})")
    except Exception as e:
        logging.error(f"Error Telegram: {e}")

# ================= COMANDO /test ==================
async def test_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, "🧪 Prueba manual /test\nSi ves esto → el bot funciona")

# ================= HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
         InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_nl"),
         InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")]
    ])

def kb_towns():
    rows = []
    for i in range(0, len(TOWNS), 3):
        row = [InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS[i:i+3]]
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def remove_jobs(app, chat_id):
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

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
            await query.edit_message_text("No se encontraron coordenadas 😕")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        chat_info[chat_id]["lat"] = lat
        chat_info[chat_id]["lon"] = lon
        save_users()
        remove_jobs(context.application, chat_id)

        tz = pytz.timezone('Europe/Madrid')

        if TEST_MODE:
            context.application.job_queue.run_repeating(send_weather, interval=300, first=5,
                                                        name=f"weather_test_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_once(send_weather, when=0.1,
                                                   name=f"immediate_{chat_id}", data={"chat_id": chat_id})
            await query.edit_message_text(f"🧪 PRUEBAS activadas para {town}\nMensaje en segundos + cada 5 min")
        else:
            context.application.job_queue.run_daily(send_weather, time(7, 57, tzinfo=tz),
                                                    name=f"weather_m_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_daily(send_weather, time(19, 57, tzinfo=tz),
                                                    name=f"weather_e_{chat_id}", data={"chat_id": chat_id})
            await query.edit_message_text(t(chat_id, "ok").format(town))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id, "city"))
        return
    town = " ".join(context.args)
    lat, lon = town_coords.get(town, (None, None))
    chat_id = update.effective_chat.id
    if lat is None:
        await update.message.reply_text(f"No se encontró '{town}'")
        return
    chat_info.setdefault(chat_id, {})["nombre"] = town
    chat_info[chat_id]["lat"] = lat
    chat_info[chat_id]["lon"] = lon
    save_users()
    await update.message.reply_text(f"✅ {town} guardado")

# ================= DB ==================
def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            chat_info = {int(k): v for k, v in json.load(f).items()}
    except:
        chat_info = {}

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)

# ================= MAIN ==================
def main():
    if not TOKEN:
        print("ERROR: No hay TOKEN")
        return

    print("⏳ Cargando coordenadas...")
    preload_town_coords()
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CommandHandler("test", test_send))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 Bot iniciado")
    app.run_polling()

if __name__ == "__main__":
    main()
