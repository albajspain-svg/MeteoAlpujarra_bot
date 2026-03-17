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

TOWNS = ["Órgiva","Lanjarón","Pampaneira","Bubión","Capileira","Trevélez"]

TEXTS = {
    "es": {
        "welcome":"🌦️ MeteoAlpujarra\nSelecciona idioma",
        "select":"Elige tu pueblo:",
        "ok":"✅ Activado para {}",
        "morning":"☀️ Mañana",
        "afternoon":"🌇 Tarde",
        "rain":"🌧️ Lluvia",
        "uv":"🧴 UV",
        "advice_hot":"😎 Hace calor, bebe agua",
        "advice_cold":"🧥 Hace frío, abrígate",
        "advice_rain":"☔ Puede llover"
    },
    "en": {
        "welcome":"🌦️ MeteoAlpujarra\nSelect language",
        "select":"Choose your village:",
        "ok":"✅ Activated for {}",
        "morning":"☀️ Morning",
        "afternoon":"🌇 Afternoon",
        "rain":"🌧️ Rain",
        "uv":"🧴 UV",
        "advice_hot":"😎 Hot, drink water",
        "advice_cold":"🧥 Cold, dress warm",
        "advice_rain":"☔ Rain expected"
    },
    "fr": {
        "welcome":"🌦️ MeteoAlpujarra\nChoisissez la langue",
        "select":"Choisissez votre village:",
        "ok":"✅ Activé pour {}",
        "morning":"☀️ Matin",
        "afternoon":"🌇 Après-midi",
        "rain":"🌧️ Pluie",
        "uv":"🧴 UV",
        "advice_hot":"😎 Chaleur, hydratez-vous",
        "advice_cold":"🧥 Froid, couvrez-vous",
        "advice_rain":"☔ Pluie possible"
    },
    "de": {
        "welcome":"🌦️ MeteoAlpujarra\nSprache wählen",
        "select":"Wähle dein Dorf:",
        "ok":"✅ Aktiviert für {}",
        "morning":"☀️ Morgen",
        "afternoon":"🌇 Nachmittag",
        "rain":"🌧️ Regen",
        "uv":"🧴 UV",
        "advice_hot":"😎 Heiß, trink Wasser",
        "advice_cold":"🧥 Kalt, warm anziehen",
        "advice_rain":"☔ Regen möglich"
    },
    "nl": {
        "welcome":"🌦️ MeteoAlpujarra\nKies taal",
        "select":"Kies je dorp:",
        "ok":"✅ Geactiveerd voor {}",
        "morning":"☀️ Ochtend",
        "afternoon":"🌇 Middag",
        "rain":"🌧️ Regen",
        "uv":"🧴 UV",
        "advice_hot":"😎 Warm, drink water",
        "advice_cold":"🧥 Koud, kleed je warm",
        "advice_rain":"☔ Kans op regen"
    },
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

def get_weather(town):
    try:
        r = requests.get(f"https://wttr.in/{town}?format=j1", timeout=10)
        r.raise_for_status()
        return r.json()
    except:
        return None

def parse_weather(data, chat_id):
    if not data:
        return "Error clima"

    curr = data["current_condition"][0]
    today = data["weather"][0]

    temp = curr.get("temp_C", "--")
    uv = curr.get("uvIndex", "0")

    morning = today["hourly"][2]
    afternoon = today["hourly"][5]

    rain_m = morning.get("chanceofrain", "0")
    rain_a = afternoon.get("chanceofrain", "0")

    msg = f"🌡️ {temp}°C\n\n"
    msg += f"{t(chat_id,'morning')}: {t(chat_id,'rain')} {rain_m}%\n"
    msg += f"{t(chat_id,'afternoon')}: {t(chat_id,'rain')} {rain_a}%\n"
    msg += f"{t(chat_id,'uv')}: {uv}\n\n"

    if int(temp) >= 28:
        msg += t(chat_id,"advice_hot")
    elif int(temp) <= 12:
        msg += t(chat_id,"advice_cold")

    if int(rain_m) > 50 or int(rain_a) > 50:
        msg += "\n" + t(chat_id,"advice_rain")

    if TEST_MODE:
        msg = "🧪 " + msg

    return msg

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info: return

    town = chat_info[chat_id]["nombre"]
    data = get_weather(town)
    text = parse_weather(data, chat_id)

    await context.bot.send_message(chat_id=chat_id, text=text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇪🇸 ES", callback_data="lang_es"),
            InlineKeyboardButton("🇬🇧 EN", callback_data="lang_en"),
        ],
        [
            InlineKeyboardButton("🇫🇷 FR", callback_data="lang_fr"),
            InlineKeyboardButton("🇩🇪 DE", callback_data="lang_de"),
            InlineKeyboardButton("🇳🇱 NL", callback_data="lang_nl"),
        ]
    ])

def kb_towns():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS]
    ])

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
        chat_info.setdefault(cid, {})["nombre"] = town
        save_users()

        remove_jobs(context.application, cid)

        context.application.job_queue.run_repeating(
            send_weather, 300, first=3,
            name=f"w_{cid}",
            data={"chat_id": cid}
        )

        await q.edit_message_text(t(cid, "ok").format(town))

def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r") as f:
            chat_info = {int(k): v for k,v in json.load(f).items()}
    except:
        chat_info = {}

def save_users():
    with open(DB_FILE, "w") as f:
        json.dump({str(k):v for k,v in chat_info.items()}, f)

def main():
    if not TOKEN:
        print("No TOKEN")
        return

    print("Iniciando...")
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot corriendo")

    # 🔥 FIX ERROR 409
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
