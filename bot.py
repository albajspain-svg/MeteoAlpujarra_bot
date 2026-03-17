import os
import json
import logging
from datetime import time
import requests
import pytz
from math import radians, cos, sin, asin, sqrt

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"
REAL_TIME = True  # True = cada 5 min | False = diaria 08:00 y 20:00

chat_info = {}
town_coords = {}
logging.basicConfig(level=logging.INFO)

# ====================== PUEBLOS ======================
TOWNS = [
    "Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez",
    "Soportújar", "Cáñar", "Carataunas", "Pórtugos",
    "Busquístar", "Atalbéitar", "Pitres", "Mecina", "Fondales",
    "Ferreirola", "Capilerilla", "Mecinilla",
    "Las Barreras", "Bayacas", "Los Tablones",
    "Bérchules", "Almegíjar", "Cádiar", "Polopos", "Turón",
    "Válor", "Yegen"
]

# ====================== TEXTOS ======================
TEXTS = {
    "es": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Elige tu pueblo:","ok":"✅ Activado para {}","city":"Escribe /ciudad Nombre","notfound":"❌ No encontrado","morning":"☀️ Mañana","afternoon":"🌇 Tarde","uv_low":"UV bajo 🌤️","uv_medium":"UV medio ☀️","uv_high":"UV alto 🧴","advice_hot":"Hace calor 😎, ropa ligera y bebe agua","advice_cold":"Hace frío 🧥, abrígate bien","advice_rain":"Llueve 🌧️, lleva paraguas/impermeable"},
    "en": {"welcome":"🌦️ MeteoAlpujarra\nSelect language / Selecciona idioma","select":"Choose your village:","ok":"✅ Activated for {}","city":"Type /city Name","notfound":"❌ Not found","morning":"☀️ Morning","afternoon":"🌇 Afternoon","uv_low":"Low UV 🌤️","uv_medium":"Medium UV ☀️","uv_high":"High UV 🧴","advice_hot":"Hot 😎, light clothes and drink water","advice_cold":"Cold 🧥, dress warmly","advice_rain":"Rain 🌧️, take umbrella/raincoat"},
    "de": {"select":"Wähle dein Dorf:","ok":"✅ Aktiviert für {}","city":"Schreibe /stadt Name","notfound":"❌ Nicht gefunden","morning":"☀️ Morgen","afternoon":"🌇 Nachmittag","uv_low":"UV niedrig 🌤️","uv_medium":"UV mittel ☀️","uv_high":"UV hoch 🧴","advice_hot":"Heiß 😎, leichte Kleidung","advice_cold":"Kalt 🧥, warm anziehen","advice_rain":"Regen 🌧️, Regenschirm mitnehmen"},
    "nl": {"select":"Kies je dorp:","ok":"✅ Geactiveerd voor {}","city":"Typ /stad Naam","notfound":"❌ Niet gevonden","morning":"☀️ Ochtend","afternoon":"🌇 Middag","uv_low":"UV laag 🌤️","uv_medium":"UV middel ☀️","uv_high":"UV hoog 🧴","advice_hot":"Warm 😎, lichte kleding","advice_cold":"Koud 🧥, warm aankleden","advice_rain":"Regen 🌧️, neem paraplu/regenkleding"},
    "fr": {"select":"Choisissez votre village:","ok":"✅ Activé pour {}","city":"Écris /ville Nom","notfound":"❌ Introuvable","morning":"☀️ Matin","afternoon":"🌇 Après-midi","uv_low":"UV faible 🌤️","uv_medium":"UV moyen ☀️","uv_high":"UV élevé 🧴","advice_hot":"Chaud 😎, vêtements légers","advice_cold":"Froid 🧥, habillez-vous chaudement","advice_rain":"Pluie 🌧️, prenez parapluie/imperméable"}
}

def t(chat_id,key):
    lang = chat_info.get(chat_id,{}).get("lang","es")
    return TEXTS.get(lang,TEXTS["es"]).get(key,"")

# ====================== PRELOAD COORDS ======================
def preload_town_coords():
    for town in TOWNS:
        try:
            res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1",timeout=10).json()
            if res.get("results"):
                r = res["results"][0]
                town_coords[town] = (r["latitude"], r["longitude"])
            else:
                town_coords[town] = (None,None)
        except:
            town_coords[town] = (None,None)

# ====================== METEO ======================
def meteo(lat, lon):
    if lat is None or lon is None:
        return {}
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m&timezone=Europe/Madrid"
    try:
        return requests.get(url,timeout=10).json()
    except:
        return {}

def nearest_town_with_data(lat, lon):
    dist_list = []
    for town, coords in town_coords.items():
        tlat, tlon = coords
        if tlat is not None:
            dist = haversine(lat, lon, tlat, tlon)
            dist_list.append((dist,town))
    dist_list.sort(key=lambda x:x[0])
    for _,tn in dist_list:
        daily = meteo(*town_coords[tn]).get("daily",{})
        if daily.get("temperature_2m_max"):
            return tn
    return None

def haversine(lat1, lon1, lat2, lon2):
    lat1,lon1,lat2,lon2 = map(radians,[lat1,lon1,lat2,lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2*asin(sqrt(a))
    return 6371*c

def wind_scale(kmh):
    if kmh is None: return "?"
    return f"{min(10,round(kmh/6))}/10"

def uv_desc(uv,chat_id):
    if uv < 3: return t(chat_id,"uv_low")
    elif uv < 6: return t(chat_id,"uv_medium")
    else: return t(chat_id,"uv_high")

def clothing_advice(temp,rain,chat_id):
    if rain > 0: return t(chat_id,"advice_rain")
    if temp >= 28: return t(chat_id,"advice_hot")
    if temp <= 15: return t(chat_id,"advice_cold")
    return ""

# ====================== UI ======================
def kb_lang():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇪🇸 Español",callback_data="lang_es"),
            InlineKeyboardButton("🇬🇧 English",callback_data="lang_en")
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch",callback_data="lang_de"),
            InlineKeyboardButton("🇳🇱 Nederlands",callback_data="lang_nl"),
            InlineKeyboardButton("🇫🇷 Français",callback_data="lang_fr")
        ]
    ])

def kb_towns():
    rows=[]
    for i in range(0,len(TOWNS),3):
        row=[InlineKeyboardButton(t,callback_data=f"town_{t}") for t in TOWNS[i:i+3]]
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def remove_jobs(app,chat_id):
    if not app.job_queue: return
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name: job.schedule_removal()

async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id=context.job.data["chat_id"]
    if chat_id not in chat_info: return
    info=chat_info[chat_id]
    data=meteo(info["lat"],info["lon"])
    daily=data.get("daily",{})
    if not daily.get("temperature_2m_max"):
        town=nearest_town_with_data(info["lat"], info["lon"])
        if town:
            chat_info[chat_id].update({"nombre":town,"lat":town_coords[town][0],"lon":town_coords[town][1]})
            data=meteo(chat_info[chat_id]["lat"],chat_info[chat_id]["lon"])
            daily=data.get("daily",{})
    max_temp = daily.get("temperature_2m_max",[0])[0]
    min_temp = daily.get("temperature_2m_min",[0])[0]
    rain = daily.get("precipitation_probability_max",[0])[0]
    uv = daily.get("uv_index_max",[0])[0]
    wind = daily.get("wind_speed_10m",[0])[0]

    msg=f"📍 {chat_info[chat_id]['nombre']}\n\n"
    msg+=f"{t(chat_id,'morning')}:\n🌡️ {min_temp}–{max_temp}°C | 🌬️ {wind_scale(wind)} | {uv_desc(uv,chat_id)} | {clothing_advice(max_temp,rain,chat_id)}\n\n"
    msg+=f"{t(chat_id,'afternoon')}:\n🌡️ {min_temp}–{max_temp}°C | 🌬️ {wind_scale(wind)} | {uv_desc(uv,chat_id)} | {clothing_advice(max_temp,rain,chat_id)}"
    await context.bot.send_message(chat_id,msg)

# ====================== HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"],reply_markup=kb_lang())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()
    data=query.data
    chat_id=query.from_user.id
    if data.startswith("lang_"):
        lang=data.replace("lang_","")
        chat_info.setdefault(chat_id,{})["lang"]=lang
        save_users()
        await query.edit_message_text(t(chat_id,"select"),reply_markup=kb_towns())
    elif data.startswith("town_"):
        town=data.replace("town_","")
        lat, lon = town_coords.get(town,(None,None))
        chat_info.setdefault(chat_id,{})["nombre"]=town
        chat_info[chat_id]["lat"]=lat
        chat_info[chat_id]["lon"]=lon
        save_users()
        remove_jobs(context.application,chat_id)
        if REAL_TIME:
            context.application.job_queue.run_repeating(send_weather,interval=300,first=5,name=f"weather_{chat_id}",data={"chat_id":chat_id})
        else:
            tz=pytz.timezone('Europe/Madrid')
            context.application.job_queue.run_daily(send_weather,time(8,0,tzinfo=tz),name=f"weather_m_{chat_id}",data={"chat_id":chat_id})
            context.application.job_queue.run_daily(send_weather,time(20,0,tzinfo=tz),name=f"weather_e_{chat_id}",data={"chat_id":chat_id})
        await query.edit_message_text(t(chat_id,"ok").format(town))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id,"city"))
        return
    town=" ".join(context.args)
    lat, lon = town_coords.get(town,(None,None))
    chat_id=update.effective_chat.id
    chat_info.setdefault(chat_id,{})["nombre"]=town
    chat_info[chat_id]["lat"]=lat
    chat_info[chat_id]["lon"]=lon
    save_users()
    await update.message.reply_text(f"✅ {town} guardado")

def load_users():
    global chat_info
    try:
        with open(DB_FILE,"r",encoding="utf-8") as f:
            data=json.load(f)
            chat_info={int(k):v for k,v in data.items()}
    except:
        chat_info={}

def save_users():
    with open(DB_FILE,"w",encoding="utf-8") as f:
        json.dump({str(k):v for k,v in chat_info.items()},f,indent=2)

# ====================== MAIN ======================
def main():
    print("⏳ Cargando coordenadas de pueblos...")
    preload_town_coords()
    load_users()
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("ciudad",ciudad))
    app.add_handler(CallbackQueryHandler(buttons))
    print("🤖 MeteoAlpujarra PRO funcionando")
    app.run_polling()

if __name__=="__main__":
    main()
