import os
import json
import logging
from datetime import time
import requests
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

TEST_MODE = True

chat_info = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos", "Busquístar", "Atalbéitar",
    "Pitres", "Mecina", "Fondales", "Ferreirola", "Capilerilla", "Mecinilla",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Válor", "Yegen"
]

TEXTS = {
    "es": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Elige tu pueblo:","ok":"✅ Activado para {}","city":"Escribe /ciudad Nombre","morning":"☀️ Mañana","afternoon":"🌇 Tarde","uv_low":"UV bajo 🌤️","uv_medium":"UV medio ☀️","uv_high":"UV alto 🧴","advice_hot":"Hace calor 😎, ropa ligera y bebe agua","advice_cold":"Hace frío 🧥, abrígate bien","advice_rain":"Llueve 🌧️, lleva paraguas/impermeable"},
    "en": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Choose your village:","ok":"✅ Activated for {}","city":"Type /city Name","morning":"☀️ Morning","afternoon":"🌇 Afternoon","uv_low":"Low UV 🌤️","uv_medium":"Medium UV ☀️","uv_high":"High UV 🧴","advice_hot":"Hot 😎, light clothes and drink water","advice_cold":"Cold 🧥, dress warmly","advice_rain":"Rain 🌧️, take umbrella/raincoat"},
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

def get_weather(town):
    try:
        r = requests.get(f"https://wttr.in/{town.replace(' ', '+')}?format=j1", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.error(f"wttr.in error para {town}: {e}")
        return None

def parse_weather(data, chat_id):
    if not data or "current_condition" not in data:
        return "⚠️ No se pudo obtener el tiempo ahora."

    curr = data["current_condition"][0]
    today = data["weather"][0]

    temp = curr.get("temp_C", "--")
    max_t = today["maxtempC"]
    min_t = today["mintempC"]
    wind = curr.get("windspeedKmph", 0)
    uv = curr.get("uvIndex", 0)

    msg = f"📍 {data['nearest_area'][0]['areaName'][0]['value']}\n\n"
    msg += f"🌡️ {temp}°C (Mín {min_t}°C / Máx {max_t}°C)\n"
    msg += f"🌬️ {wind} km/h   UV {uv}\n"

    if int(max_t or 0) >= 28:
        msg += t(chat_id, "advice_hot")
    elif int(min_t or 0) <= 12:
        msg += t(chat_id, "advice_cold")

    if TEST_MODE:
        msg = "🧪 " + msg

    return msg

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info: return

    town = chat_info[chat_id]["nombre"]
    data = get_weather(town)
    text = parse_weather(data, chat_id)

    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logging.error(f"No se pudo enviar: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ])

def kb_towns():
    rows = []
    for i in range(0, len(TOWNS), 3):
        rows.append([InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS[i:i+3]])
    return InlineKeyboardMarkup(rows)

def remove_jobs(app, chat_id):
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    cid = q.from_user.id

    if d.startswith("lang_"):
        chat_info.setdefault(cid, {})["lang"] = d[5:]
        save_users()
        await q.edit_message_text(t(cid, "select"), reply_markup=kb_towns())

    elif d.startswith("town_"):
        town = d[5:]
        if town not in TOWNS: return
        chat_info.setdefault(cid, {})["nombre"] = town
        save_users()
        remove_jobs(context.application, cid)

        if TEST_MODE:
            context.application.job_queue.run_repeating(send_weather, 300, first=3, name=f"w_{cid}", data={"chat_id": cid})
            context.application.job_queue.run_once(send_weather, 0.5, name=f"i_{cid}", data={"chat_id": cid})
            await q.edit_message_text(f"Pruebas ON para {town}")
        else:
            tz = pytz.timezone('Europe/Madrid')
            context.application.job_queue.run_daily(send_weather, time(7,57,tzinfo=tz), name=f"m_{cid}", data={"chat_id": cid})
            context.application.job_queue.run_daily(send_weather, time(19,57,tzinfo=tz), name=f"e_{cid}", data={"chat_id": cid})
            await q.edit_message_text(t(cid, "ok").format(town))

def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            chat_info = {int(k): v for k,v in json.load(f).items()}
    except:
        chat_info = {}

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k):v for k,v in chat_info.items()}, f, ensure_ascii=False)

def main():
    if not TOKEN:
        print("No hay TOKEN")
        return

    print("Iniciando...")
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot corriendo")
    app.run_polling()

if __name__ == "__main__":
    main()
