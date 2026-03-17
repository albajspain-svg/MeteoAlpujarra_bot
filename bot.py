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

TEST_MODE = True          # Cambia a False para modo real (07:57 y 19:57)

chat_info = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ================= PUEBLOS OFICIALES ALPÚJARRA (solo los que funcionan) =================
TOWN_COORDS = {
    "Órgiva": (36.9026, -3.4238),
    "Lanjarón": (36.9185, -3.4818),
    "Pampaneira": (36.9402, -3.3610),
    "Bubión": (36.9500, -3.3550),
    "Capileira": (36.9615, -3.3586),
    "Trevélez": (37.0004, -3.2655),
    "Soportújar": (36.9286, -3.4054),
    "Cáñar": (36.9268, -3.4281),
    "Carataunas": (36.9220, -3.4083),
    "Pórtugos": (36.9419, -3.3107),
    "Busquístar": (36.9380, -3.2944),
    "Atalbéitar": (36.9345, -3.3090),
    "Pitres": (36.9300, -3.3200),
    "Mecina": (36.9250, -3.3150),
    "Fondales": (36.9251, -3.3214),
    "Ferreirola": (36.9298, -3.3139),
    "Capilerilla": (36.9200, -3.3100),
    "Mecinilla": (36.9269, -3.3236),
    "Bérchules": (36.9768, -3.1907),
    "Almegíjar": (36.9026, -3.3012),
    "Cádiar": (36.9459, -3.1802),
    "Polopos": (36.7947, -3.2982),
    "Válor": (36.9962, -3.0829),
    "Yegen": (36.9810, -3.1190),
}

TOWNS = list(TOWN_COORDS.keys())

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

# ================= METEO =================
def get_weather(lat, lon):
    if not lat or not lon:
        return {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m&timezone=Europe/Madrid&forecast_days=2"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        logging.info(f"API OK para {lat},{lon} → daily existe: {'daily' in data}")
        return data
    except Exception as e:
        logging.error(f"API Open-Meteo falló: {type(e).__name__} - {e}")
        return {}

def wind_scale(kmh):
    if kmh is None: return "?"
    return f"{kmh} km/h | {min(10, round(kmh/6))}/10"

def thermal_feel(temp, wind):
    if temp is None or wind is None: return ""
    return f"🌡️ Sens. térmica: {round(temp - sqrt(wind)/3)}°C"

def uv_desc(uv, chat_id):
    if uv < 3: return t(chat_id, "uv_low")
    if uv < 6: return t(chat_id, "uv_medium")
    return t(chat_id, "uv_high")

def clothing_advice(temp, rain, chat_id):
    if rain > 30: return t(chat_id, "advice_rain")
    if temp >= 28: return t(chat_id, "advice_hot")
    if temp <= 15: return t(chat_id, "advice_cold")
    return ""

# ================= ENVÍO =================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info: return

    info = chat_info[chat_id]
    nombre = info["nombre"]
    lat, lon = TOWN_COORDS.get(nombre, (None, None))

    data = get_weather(lat, lon)

    if not data or "daily" not in data or not data["daily"].get("temperature_2m_max"):
        msg = f"⚠️ {nombre}\nNo se pudo obtener el tiempo ahora.\nAPI Open-Meteo sin respuesta.\nReintenta en 1 minuto."
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg)
        except: pass
        return

    d = data["daily"]
    c = data.get("current_weather", {})

    msg = f"📍 {nombre}\n\n"
    msg += f"🕗 {'Tarde' if (not TEST_MODE and 'weather_e' in context.job.name) else 'Mañana'}\n"
    msg += f"{thermal_feel(c.get('temperature'), d['wind_speed_10m'][0])}\n"
    msg += f"🌡️ {c.get('temperature', '--')}°C   Mín {d['temperature_2m_min'][0]}°C   Máx {d['temperature_2m_max'][0]}°C\n"
    msg += f"🌬️ {wind_scale(d['wind_speed_10m'][0])}   {uv_desc(d['uv_index_max'][0], chat_id)}\n"
    msg += f"{clothing_advice(d['temperature_2m_max'][0], d['precipitation_probability_max'][0], chat_id)}"

    if TEST_MODE:
        msg = "🧪 PRUEBA " + msg

    await context.bot.send_message(chat_id=chat_id, text=msg, disable_notification=TEST_MODE)
    logging.info(f"Mensaje enviado correctamente a {chat_id} ({nombre})")

# ================= HANDLERS =================
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
        if town not in TOWN_COORDS:
            await query.edit_message_text("Pueblo no disponible")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        save_users()
        remove_jobs(context.application, chat_id)

        if TEST_MODE:
            context.application.job_queue.run_repeating(send_weather, interval=300, first=5, name=f"weather_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_once(send_weather, when=0.1, name=f"imm_{chat_id}", data={"chat_id": chat_id})
            await query.edit_message_text(f"🧪 Pruebas activadas para {town}\nMensaje en segundos + cada 5 min")
        else:
            tz = pytz.timezone('Europe/Madrid')
            context.application.job_queue.run_daily(send_weather, time(7,57,tzinfo=tz), name=f"m_{chat_id}", data={"chat_id": chat_id})
            context.application.job_queue.run_daily(send_weather, time(19,57,tzinfo=tz), name=f"e_{chat_id}", data={"chat_id": chat_id})
            await query.edit_message_text(t(chat_id, "ok").format(town))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id, "city"))
        return
    town = " ".join(context.args)
    if town not in TOWN_COORDS:
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
    except:
        chat_info = {}
        logging.info("Base de usuarios vacía")

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)

def main():
    if not TOKEN:
        print("ERROR: No hay TOKEN en variables de entorno")
        return

    print("🤖 MeteoAlpujarra iniciado (solo pueblos válidos)")
    load_users()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling()

if __name__ == "__main__":
    main()
