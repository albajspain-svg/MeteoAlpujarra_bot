import os
import json
import logging
from datetime import datetime, time
import requests
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"
REAL_TIME = True  # True = cada 5 min, False = 08:00 y 20:00

chat_info = {}
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
    "El Morreón"
]

# ====================== TEXTOS ======================
TEXTS = {
    "es": {
        "welcome": "🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma",
        "select": "Elige tu pueblo:",
        "ok": "✅ Activado para {}",
        "city": "Escribe /ciudad Nombre",
        "notfound": "❌ No encontrado",
        "use_start": "Usa /start primero",
        "uv_low": "UV bajo 🌤️",
        "uv_medium": "UV medio ☀️",
        "uv_high": "UV alto 🧴",
        "advice_hot": "Hace calor 😎, ropa ligera y bebe agua",
        "advice_cold": "Hace frío 🧥, abrígate bien",
        "advice_rain": "Llueve 🌧️, lleva paraguas/impermeable",
        "morning": "☀️ Mañana",
        "afternoon": "🌇 Tarde"
    },
    "en": {
        "welcome": "🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma",
        "select": "Choose your village:",
        "ok": "✅ Activated for {}",
        "city": "Type /city Name",
        "notfound": "❌ Not found",
        "use_start": "Use /start first",
        "uv_low": "Low UV 🌤️",
        "uv_medium": "Medium UV ☀️",
        "uv_high": "High UV 🧴",
        "advice_hot": "Hot 😎, light clothes and drink water",
        "advice_cold": "Cold 🧥, dress warmly",
        "advice_rain": "Rain 🌧️, take umbrella/raincoat",
        "morning": "☀️ Morning",
        "afternoon": "🌇 Afternoon"
    },
    "de": {
        "select": "Wähle dein Dorf:",
        "ok": "✅ Aktiviert für {}",
        "city": "Schreibe /stadt Name",
        "notfound": "❌ Nicht gefunden",
        "use_start": "Benutze zuerst /start",
        "uv_low": "UV niedrig 🌤️",
        "uv_medium": "UV mittel ☀️",
        "uv_high": "UV hoch 🧴",
        "advice_hot": "Heiß 😎, leichte Kleidung",
        "advice_cold": "Kalt 🧥, warm anziehen",
        "advice_rain": "Regen 🌧️, Regenschirm mitnehmen",
        "morning": "☀️ Morgen",
        "afternoon": "🌇 Nachmittag"
    },
    "nl": {
        "select": "Kies je dorp:",
        "ok": "✅ Geactiveerd voor {}",
        "city": "Typ /stad Naam",
        "notfound": "❌ Niet gevonden",
        "use_start": "Gebruik eerst /start",
        "uv_low": "UV laag 🌤️",
        "uv_medium": "UV middel ☀️",
        "uv_high": "UV hoog 🧴",
        "advice_hot": "Warm 😎, lichte kleding",
        "advice_cold": "Koud 🧥, warm aankleden",
        "advice_rain": "Regen 🌧️, neem paraplu/regenkleding",
        "morning": "☀️ Ochtend",
        "afternoon": "🌇 Middag"
    },
    "fr": {
        "select": "Choisissez votre village:",
        "ok": "✅ Activé pour {}",
        "city": "Écris /ville Nom",
        "notfound": "❌ Introuvable",
        "use_start": "Utilisez d'abord /start",
        "uv_low": "UV faible 🌤️",
        "uv_medium": "UV moyen ☀️",
        "uv_high": "UV élevé 🧴",
        "advice_hot": "Chaud 😎, vêtements légers",
        "advice_cold": "Froid 🧥, habillez-vous chaudement",
        "advice_rain": "Pluie 🌧️, prenez parapluie/imperméable",
        "morning": "☀️ Matin",
        "afternoon": "🌇 Après-midi"
    }
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, "")

# ====================== METEO ======================
def meteo(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,weathercode,wind_speed_10m"
        f"&timezone=Europe/Madrid"
    )
    try:
        return requests.get(url, timeout=10).json()
    except:
        return {}

def wind_scale(kmh):
    if kmh is None:
        return "?"
    scale = min(10, round(kmh / 6))
    return f"{scale}/10"

def uv_index_desc(uv, chat_id):
    if uv < 3:
        return t(chat_id,"uv_low")
    elif uv < 6:
        return t(chat_id,"uv_medium")
    else:
        return t(chat_id,"uv_high")

def clothing_advice(temp, rain, chat_id):
    if rain > 0:
        return t(chat_id,"advice_rain")
    if temp >= 28:
        return t(chat_id,"advice_hot")
    if temp <= 15:
        return t(chat_id,"advice_cold")
    return ""

# ====================== UI ======================
def kb_lang():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
            InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_nl"),
            InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")
        ]
    ])

def kb_towns():
    rows = []
    for i in range(0,len(TOWNS),3):
        row = [InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS[i:i+3]]
        rows.append(row)
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
    daily = data.get("daily",{})

    if not daily:
        await context.bot.send_message(chat_id,"❌ Error obteniendo datos")
        return

    msg = f"📍 {info['nombre']}\n\n"
    max_temp = daily["temperature_2m_max"][0]
    min_temp = daily["temperature_2m_min"][0]
    rain = daily["precipitation_probability_max"][0]
    uv = daily.get("uv_index_max",[0])[0]
    wind = daily.get("wind_speed_10m",[0])[0]
    weather_code = daily.get("weathercode",[0])[0]

    # mañana
    msg += f"{t(chat_id,'morning')}:\n"
    msg += f"🌡️ {min_temp}–{max_temp}°C | 🌬️ {wind_scale(wind)} | {uv_index_desc(uv,chat_id)} | {clothing_advice(max_temp,rain,chat_id)}\n\n"

    # tarde (usamos misma info simple)
    msg += f"{t(chat_id,'afternoon')}:\n"
    msg += f"🌡️ {min_temp}–{max_temp}°C | 🌬️ {wind_scale(wind)} | {uv_index_desc(uv,chat_id)} | {clothing_advice(max_temp,rain,chat_id)}\n"

    await context.bot.send_message(chat_id,msg)

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.from_user.id

    if data.startswith("lang_"):
        lang = data.replace("lang_","")
        chat_info.setdefault(chat_id, {})["lang"]=lang
        save_users()
        await query.edit_message_text(t(chat_id,"select"), reply_markup=kb_towns())
    elif data.startswith("town_"):
        town = data.replace("town_","")
        res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",timeout=10).json()
        if not res.get("results"):
            await query.edit_message_text(t(chat_id,"notfound"))
            return
        r=res["results"][0]
        chat_info[chat_id].update({"nombre":r["name"],"lat":r["latitude"],"lon":r["longitude"]})
        save_users()
        remove_jobs(context.application,chat_id)
        if REAL_TIME:
            context.application.job_queue.run_repeating(send_weather,interval=300,first=5,name=f"weather_{chat_id}",data={"chat_id":chat_id})
        else:
            tz=pytz.timezone('Europe/Madrid')
            context.application.job_queue.run_daily(send_weather,time(8,0,tzinfo=tz),name=f"weather_m_{chat_id}",data={"chat_id":chat_id})
            context.application.job_queue.run_daily(send_weather,time(20,0,tzinfo=tz),name=f"weather_e_{chat_id}",data={"chat_id":chat_id})
        await query.edit_message_text(t(chat_id,"ok").format(r["name"]))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id,"city"))
        return
    town=" ".join(context.args)
    res=requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",timeout=10).json()
    if not res.get("results"):
        await update.message.reply_text(t(update.effective_chat.id,"notfound"))
        return
    r=res["results"][0]
    chat_id=update.effective_chat.id
    chat_info[chat_id].update({"nombre":r["name"],"lat":r["latitude"],"lon":r["longitude"]})
    save_users()
    await update.message.reply_text(f"✅ {r['name']} guardado")

# ====================== MAIN ======================
def main():
    load_users()
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("ciudad",ciudad))
    app.add_handler(CallbackQueryHandler(buttons))
    print("🤖 MeteoAlpujarra PRO funcionando")
    app.run_polling()

if __name__=="__main__":
    main()
