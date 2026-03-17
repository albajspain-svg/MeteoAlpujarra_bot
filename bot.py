import os
import json
from datetime import time, datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"
TEST_MODE = True  # 🔥 TRUE = cada 5 min | FALSE = 8:00 y 20:00

chat_info = {}

# ====================== DB ======================
def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            chat_info = {int(k): v for k, v in data.items()}
        print(f"✅ {len(chat_info)} usuarios cargados")
    except:
        chat_info = {}
        print("📂 users.json creado")

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)

# ====================== TEXTOS ======================
TEXTS = {
    "es": {
        "welcome": "🌦️ MeteoAlpujarra\n\nSelecciona idioma:",
        "select": "Elige tu pueblo:",
        "ok": "✅ Activado para {}",
        "no": "❗️ Elige primero un pueblo",
        "otros": "Otros pueblos",
        "city": "Escribe /ciudad Nombre",
    },
    "en": {
        "welcome": "🌦️ MeteoAlpujarra\n\nSelect language:",
        "select": "Choose village:",
        "ok": "✅ Activated for {}",
        "no": "❗️ Choose a village first",
        "otros": "Other towns",
        "city": "Type /city Name",
    }
}

TOWNS = ["Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez"]

def t(lang, key):
    return TEXTS.get(lang, TEXTS["es"]).get(key, "")

# ====================== METEO ======================
def meteo(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m"
    return requests.get(url).json()

# ====================== TECLADOS ======================
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def kb_towns(lang):
    rows = []
    for town in TOWNS:
        rows.append([InlineKeyboardButton(town, callback_data=f"town_{town}")])
    rows.append([InlineKeyboardButton(t(lang, "otros"), callback_data="otros")])
    return InlineKeyboardMarkup(rows)

# ====================== JOBS ======================
def remove_jobs(app, chat_id):
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]

    if chat_id not in chat_info:
        return

    info = chat_info[chat_id]
    data = meteo(info["lat"], info["lon"])

    temp = data.get("current", {}).get("temperature_2m", "?")

    msg = f"📍 {info['nombre']}\n🌡️ {temp}°C\n🕒 {datetime.now().strftime('%H:%M')}"

    try:
        await context.bot.send_message(chat_id, msg)
    except:
        pass

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t("es", "welcome"), reply_markup=kb_lang())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.from_user.id  # 🔥 CLAVE

    print("CLICK:", data)

    # IDIOMA
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        chat_info.setdefault(chat_id, {})["lang"] = lang
        save_users()

        await query.edit_message_text(
            t(lang, "select"),
            reply_markup=kb_towns(lang)
        )

    # PUEBLO
    elif data.startswith("town_"):
        town = data.replace("town_", "")
        lang = chat_info.get(chat_id, {}).get("lang", "es")

        res = requests.get(
            f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1"
        ).json()

        if not res.get("results"):
            await query.edit_message_text("❌ Error")
            return

        r = res["results"][0]

        chat_info[chat_id] = {
            "nombre": r["name"],
            "lat": r["latitude"],
            "lon": r["longitude"],
            "lang": lang
        }
        save_users()

        remove_jobs(context.application, chat_id)

        if TEST_MODE:
            context.application.job_queue.run_repeating(
                send_weather,
                interval=300,
                first=5,
                name=f"weather_{chat_id}",
                data={"chat_id": chat_id}
            )
        else:
            context.application.job_queue.run_daily(
                send_weather,
                time(8, 0),
                name=f"weather_m_{chat_id}",
                data={"chat_id": chat_id}
            )
            context.application.job_queue.run_daily(
                send_weather,
                time(20, 0),
                name=f"weather_e_{chat_id}",
                data={"chat_id": chat_id}
            )

        await query.edit_message_text(t(lang, "ok").format(r["name"]))

    elif data == "otros":
        lang = chat_info.get(chat_id, {}).get("lang", "es")
        await query.edit_message_text(t(lang, "city"))

# ====================== COMANDOS ======================
async def clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in chat_info:
        await update.message.reply_text("Usa /start primero")
        return

    info = chat_info[chat_id]
    data = meteo(info["lat"], info["lon"])
    temp = data.get("current", {}).get("temperature_2m", "?")

    await update.message.reply_text(f"📍 {info['nombre']}\n🌡️ {temp}°C")

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usa /ciudad Nombre")
        return

    town = " ".join(context.args)
    res = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1"
    ).json()

    if not res.get("results"):
        await update.message.reply_text("❌ No encontrado")
        return

    r = res["results"][0]
    chat_id = update.effective_chat.id
    lang = chat_info.get(chat_id, {}).get("lang", "es")

    chat_info[chat_id] = {
        "nombre": r["name"],
        "lat": r["latitude"],
        "lon": r["longitude"],
        "lang": lang
    }
    save_users()

    await update.message.reply_text(f"✅ {r['name']} guardado")

# ====================== MAIN ======================
def main():
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clima", clima))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 MeteoAlpujarra PRO funcionando")
    app.run_polling()

if __name__ == "__main__":
    main()
