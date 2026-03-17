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

TEST_MODE = True  # Cambia a False cuando quieras horarios fijos

chat_info = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Pueblos (nombres que entiende wttr.in bien)
TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos", "Busquístar", "Atalbéitar",
    "Pitres", "Mecina", "Fondales", "Ferreirola", "Capilerilla", "Mecinilla",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Válor", "Yegen"
]

TEXTS = {
    "es": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Elige tu pueblo:","ok":"✅ Activado para {}","city":"Escribe /ciudad Nombre","morning":"☀️ Mañana","afternoon":"🌇 Tarde","uv_low":"UV bajo 🌤️","uv_medium":"UV medio ☀️","uv_high":"UV alto 🧴","advice_hot":"Hace calor 😎, ropa ligera y bebe agua","advice_cold":"Hace frío 🧥, abrígate bien","advice_rain":"Llueve 🌧️, lleva paraguas/impermeable"},
    "en": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Choose your village:","ok":"✅ Activated for {}","city":"Type /city Name","morning":"☀️ Morning","afternoon":"🌇 Afternoon","uv_low":"Low UV 🌤️","uv_medium":"Medium UV ☀️","uv_high":"High UV 🧴","advice_hot":"Hot 😎, light clothes and drink water","advice_cold":"Cold 🧥, dress warmly","advice_rain":"Rain 🌧️, take umbrella/raincoat"},
    "de": {"select":"Wähle dein Dorf:","ok":"✅ Aktiviert für {}","city":"Schreibe /stadt Name","morning":"☀️ Morgen","afternoon":"🌇 Nachmittag","uv_low":"UV niedrig 🌤️","uv_medium":"UV mittel ☀️","uv_high":"UV hoch 🧴","advice_hot":"Heiß 😎, leichte Kleidung","advice_cold":"Kalt 🧥, warm anziehen","advice_rain":"Regen 🌧️, Regenschirm mitnehmen"},
    "nl": {"select":"Kies je dorp:","ok":"✅ Geactiveerd voor {}","city":"Typ /stad Naam","morning":"☀️ Ochtend","afternoon":"🌇 Middag","uv_low":"UV laag 🌤️","uv_medium":"UV middel ☀️","uv_high":"UV hoog 🧴","advice_hot":"Warm 😎, lichte kleding","advice_cold":"Koud 🧥, warm aankleden","advice_rain":"Regen 🌧️, neem paraplu/regenkleding"},
    "fr": {"select":"Choisissez votre village:","ok":"✅ Activé pour {}","city":"Écris /ville Nom","morning":"☀️ Matin","afternoon":"🌇 Après-midi","uv_low":"UV faible 🌤️","uv_medium":"UV moyen ☀️","uv_high":"UV élevé 🧴","advice_hot":"Chaud 😎, vêtements légers","advice_cold":"Froid 🧥, habillez-vous chaudement","advice_rain":"Pluie 🌧️, prenez parapluie/imperméable"}
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

def get_weather(town):
    try:
        url = f"https://wttr.in/{town.replace(' ', '+')}?format=j1"
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()
        logging.info(f"wttr.in OK para {town}")
        return data
    except Exception as e:
        logging.error(f"wttr.in falló para {town}: {str(e)}")
        return None

def parse_weather(data, chat_id):
    if not data or "current_condition" not in data or "weather" not in data:
        return "⚠️ Datos incompletos. Reintenta en unos minutos."

    try:
        current = data["current_condition"][0]
        today = data["weather"][0]

        temp = int(current["temp_C"])
        max_t = int(today["maxtempC"])
        min_t = int(today["mintempC"])
        wind = int(current["windspeedKmph"])
        uv = int(current["uvIndex"])
        rain_prob = int(today["hourly"][8]["chanceofrain"])  # mediodía aprox

        msg = f"📍 {data['nearest_area'][0]['areaName'][0]['value']}\n\n"
        msg += f"🕗 Mañana\n"
        msg += f"🌡️ {temp}°C   Mín {min_t}°C   Máx {max_t}°C\n"
        msg += f"🌬️ {wind} km/h   UV {uv}\n"

        if rain_prob > 30:
            msg += "🌧️ Prob. lluvia alta"
        elif temp >= 28:
            msg += "😎 Hace calor"
        elif temp <= 15:
            msg += "🧥 Hace frío"

        if TEST_MODE:
            msg = "🧪 PRUEBA " + msg

        return msg
    except Exception as e:
        logging.error(f"Error parseando datos: {e}")
        return "⚠️ Datos incompletos. Reintenta."

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return

    town = chat_info[chat_id]["nombre"]
    data = get_weather(town)
    msg = parse_weather(data, chat_id)

    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, disable_notification=TEST_MODE)
        logging.info(f"Enviado a {chat_id} ({town})")
    except Exception as e:
        logging.error(f"Error enviando: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"), InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_nl"), InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")]
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
        if town not in TOWNS:
            await query.edit_message_text("Pueblo no disponible")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        save_users()
        remove_jobs(context.application, chat_id)

        tz = pytz.timezone('Europe/Madrid')

        if TEST_MODE:
            context.application.job_queue.run_repeating(send_weather, interval=300, first=5,
                                                        name=f"weather_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_once(send_weather, when=0.1,
                                                   name=f"imm_{chat_id}", data={"chat_id": chat_id})
            await query.edit_message_text(f"🧪 Pruebas para {town}\nMensaje en segundos + cada 5 min")
        else:
            context.application.job_queue.run_daily(send_weather, time(7,57,tzinfo=tz),
                                                    name=f"m_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_daily(send_weather, time(19,57,tzinfo=tz),
                                                    name=f"e_{chat_id}", data={"chat_id": chat_id})
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

def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            chat_info = {int(k): v for k, v in json.load(f).items()}
        logging.info(f"{len(chat_info)} usuarios cargados")
    except Exception as e:
        chat_info = {}
        logging.info("No hay usuarios previos")

def save_users():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error guardando: {e}")

def main():
    if not TOKEN:
        print("ERROR: TOKEN no encontrado")
        return

    print("Iniciando bot con wttr.in...")
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot corriendo – prueba /start")
    app.run_polling()

if __name__ == "__main__":
    main()
