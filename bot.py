import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"
TEST_MODE = True

chat_info = {}

logging.basicConfig(level=logging.INFO)

TOWNS = ["Órgiva","Lanjarón","Pampaneira","Bubión","Capileira","Trevélez"]

TEXTS = {
    "es": {"welcome":"🌦️ MeteoAlpujarra\nSelecciona idioma","select":"Elige tu pueblo:","ok":"✅ Activado para {}","error":"⚠️ Error clima"},
    "en": {"welcome":"🌦️ MeteoAlpujarra\nSelect language","select":"Choose your village:","ok":"✅ Activated for {}","error":"⚠️ Weather error"},
    "fr": {"welcome":"🌦️ MeteoAlpujarra\nChoisissez la langue","select":"Choisissez votre village:","ok":"✅ Activé pour {}","error":"⚠️ Erreur météo"},
    "de": {"welcome":"🌦️ MeteoAlpujarra\nSprache wählen","select":"Wähle dein Dorf:","ok":"✅ Aktiviert für {}","error":"⚠️ Wetterfehler"},
    "nl": {"welcome":"🌦️ MeteoAlpujarra\nKies taal","select":"Kies je dorp:","ok":"✅ Geactiveerd voor {}","error":"⚠️ Weer fout"},
}

def t(cid, key):
    lang = chat_info.get(cid, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

def get_weather(town):
    try:
        r = requests.get(f"https://wttr.in/{town}?format=j1", timeout=10)
        return r.json()
    except:
        return None

def parse_weather(data, cid):
    try:
        if not data or "current_condition" not in data:
            return t(cid, "error")

        curr = data["current_condition"][0]
        today = data.get("weather", [{}])[0]

        temp = curr.get("temp_C", "--")
        uv = curr.get("uvIndex", "0")

        hourly = today.get("hourly", [])
        if len(hourly) < 6:
            return t(cid, "error")

        rain_m = hourly[2].get("chanceofrain", "0")
        rain_a = hourly[5].get("chanceofrain", "0")

        msg = f"🌡️ {temp}°C\n"
        msg += f"☀️ {rain_m}% 🌧️\n"
        msg += f"🌇 {rain_a}% 🌧️\n"
        msg += f"🧴 UV: {uv}"

        if TEST_MODE:
            msg = "🧪 " + msg

        return msg

    except:
        return t(cid, "error")

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    cid = context.job.data["chat_id"]
    if cid not in chat_info:
        return

    town = chat_info[cid]["nombre"]
    data = get_weather(town)
    text = parse_weather(data, cid)

    await context.bot.send_message(chat_id=cid, text=text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸", callback_data="lang_es"), InlineKeyboardButton("🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("🇫🇷", callback_data="lang_fr"), InlineKeyboardButton("🇩🇪", callback_data="lang_de"), InlineKeyboardButton("🇳🇱", callback_data="lang_nl")]
    ])

def kb_towns():
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS]])

def remove_jobs(app, cid):
    for job in app.job_queue.jobs():
        if str(cid) in job.name:
            job.schedule_removal()

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    cid = q.from_user.id

    if d.startswith("lang_"):
        chat_info.setdefault(cid, {})["lang"] = d[5:]
        save_users()
        await q.edit_message_text(t(cid,"select"), reply_markup=kb_towns())

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

        await q.edit_message_text(t(cid,"ok").format(town))

def load_users():
    global chat_info
    try:
        with open(DB_FILE,"r") as f:
            chat_info = {int(k): v for k,v in json.load(f).items()}
    except:
        chat_info = {}

def save_users():
    with open(DB_FILE,"w") as f:
        json.dump({str(k):v for k,v in chat_info.items()}, f)

async def on_startup(app):
    # 🔥 CIERRA TODO en Telegram (clave real)
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("🔥 Sesiones antiguas limpiadas")

def main():
    if not TOKEN:
        print("No TOKEN")
        return

    load_users()

    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot corriendo limpio")

    # 🔥 polling robusto (ignora conflictos iniciales)
    app.run_polling(drop_pending_updates=True, allowed_updates=[])

if __name__ == "__main__":
    main()
