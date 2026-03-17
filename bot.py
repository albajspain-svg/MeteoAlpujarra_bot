import os
import json
import logging
from datetime import time
import requests
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ────────────────────────────────────────────────
# CONFIGURACIÓN GLOBAL
# ────────────────────────────────────────────────

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

TEST_MODE = True  # True → cada 5 min + inmediato | False → 07:57 y 19:57

chat_info = {}    # {chat_id: {"nombre": "Órgiva", "lang": "es"}}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos", "Busquístar", "Atalbéitar",
    "Pitres", "Mecina", "Fondales", "Ferreirola", "Capilerilla", "Mecinilla",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Válor", "Yegen"
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
    },
    "en": {
        "welcome": "🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma",
        "select": "Choose your village:",
        "ok": "✅ Activated for {}",
        "city": "Type /city Name",
        "morning": "☀️ Morning",
        "afternoon": "🌇 Afternoon",
        "uv_low": "Low UV 🌤️",
        "uv_medium": "Medium UV ☀️",
        "uv_high": "High UV 🧴",
        "advice_hot": "Hot 😎, light clothes and drink water",
        "advice_cold": "Cold 🧥, dress warmly",
        "advice_rain": "Rain 🌧️, take umbrella/raincoat"
    },
    # Puedes añadir de, nl, fr si los necesitas
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

# ────────────────────────────────────────────────
# OBTENER TIEMPO (wttr.in – muy estable)
# ────────────────────────────────────────────────

def get_weather(town):
    try:
        url = f"https://wttr.in/{town.replace(' ', '+')}?format=j1"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"wttr.in falló para '{town}': {str(e)}")
        return None

def parse_weather(data, chat_id):
    if not data or "current_condition" not in data or "weather" not in data:
        return f"⚠️ No se pudo obtener datos para este pueblo.\nReintenta en unos minutos."

    try:
        curr = data["current_condition"][0]
        today = data["weather"][0]
        area = data["nearest_area"][0]["areaName"][0]["value"]

        temp = curr.get("temp_C", "--")
        wind_kmh = curr.get("windspeedKmph", 0)
        uv = curr.get("uvIndex", 0)
        max_t = today["maxtempC"]
        min_t = today["mintempC"]
        rain_prob = int(today["hourly"][8]["chanceofrain"])  # aprox mediodía

        msg = f"📍 {area}\n\n"
        msg += f"🕗 {t(chat_id, 'morning')}\n"
        msg += f"🌡️ {temp}°C   Mín {min_t}°C   Máx {max_t}°C\n"
        msg += f"🌬️ {wind_kmh} km/h   UV {uv}\n"

        if rain_prob > 30:
            msg += t(chat_id, "advice_rain")
        elif int(max_t) >= 28:
            msg += t(chat_id, "advice_hot")
        elif int(min_t) <= 12:
            msg += t(chat_id, "advice_cold")

        if TEST_MODE:
            msg = "🧪 PRUEBA ─ " + msg

        return msg
    except Exception as e:
        logging.error(f"Error parseando wttr.in: {e}")
        return "⚠️ Formato de datos inesperado. Reintenta."

# ────────────────────────────────────────────────
# ENVIAR MENSAJE
# ────────────────────────────────────────────────

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return

    town = chat_info[chat_id]["nombre"]
    data = get_weather(town)
    text = parse_weather(data, chat_id)

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_notification=TEST_MODE
        )
        logging.info(f"Mensaje enviado a {chat_id} ({town})")
    except Exception as e:
        logging.error(f"Error al enviar mensaje a {chat_id}: {e}")

# ────────────────────────────────────────────────
# HANDLERS
# ────────────────────────────────────────────────

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

def remove_jobs(application, chat_id):
    if not application.job_queue:
        return
    for job in application.job_queue.jobs():
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
        if town not in TOWNS:
            await query.edit_message_text("Pueblo no disponible")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        save_users()
        remove_jobs(context.application, chat_id)

        tz = pytz.timezone('Europe/Madrid')

        if TEST_MODE:
            context.application.job_queue.run_repeating(
                send_weather, interval=300, first=3,
                name=f"weather_{chat_id}", data={"chat_id": chat_id}
            )
            context.application.job_queue.run_once(
                send_weather, when=0.5,
                name=f"test_{chat_id}", data={"chat_id": chat_id}
            )
            await query.edit_message_text(
                f"🧪 Modo pruebas activado para {town}\n"
                "→ Mensaje de prueba en ~1 segundo\n"
                "→ Luego cada 5 minutos"
            )
        else:
            context.application.job_queue.run_daily(
                send_weather, time(7, 57, tzinfo=tz),
                name=f"morning_{chat_id}", data={"chat_id": chat_id}
            )
            context.application.job_queue.run_daily(
                send_weather, time(19, 57, tzinfo=tz),
                name=f"evening_{chat_id}", data={"chat_id": chat_id}
            )
            await query.edit_message_text(t(chat_id, "ok").format(town))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id, "city"))
        return
    town = " ".join(context.args)
    if town not in TOWNS:
        await update.message.reply_text("Pueblo no disponible")
        return
    chat_id = update.effective_chat.id
    chat_info.setdefault(chat_id, {})["nombre"] = town
    save_users()
    await update.message.reply_text(f"✅ {town} guardado")

# ────────────────────────────────────────────────
# BASE DE DATOS SIMPLE
# ────────────────────────────────────────────────

def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            chat_info = {int(k): v for k, v in raw.items()}
        logging.info(f"Cargados {len(chat_info)} usuarios")
    except Exception:
        chat_info = {}
        logging.info("No hay archivo de usuarios → empezamos vacío")

def save_users():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)
        logging.info("Usuarios guardados")
    except Exception as e:
        logging.error(f"Error al guardar usuarios: {e}")

# ────────────────────────────────────────────────
# INICIO
# ────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("ERROR: TOKEN no encontrado en las variables de entorno")
        return

    print("Iniciando MeteoAlpujarra ...")
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot iniciado – prueba /start en Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
