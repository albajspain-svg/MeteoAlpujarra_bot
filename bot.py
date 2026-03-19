import logging
import os
from datetime import datetime, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import httpx

# ====================== CONFIG ======================
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

if not TOKEN or not CHAT_ID:
    raise ValueError("❌ Faltan BOT_TOKEN o CHAT_ID en Variables de Railway")

MODO_PRUEBA = True   # ← Pon False para modo REAL (exacto 8:00 y 20:00)

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

TEXTOS = {
    "ES": {
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Bot activado\nPoblación: {loc}\n\n/cambiar para cambiar localidad",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a {loc}\nBuscando datos del tiempo en {loc}...\nEspere un momento.",
        "cambia_con": "Para cambiar población pulse /cambiar\nPara cambiar idioma pulse /start",
        "siguiente_8": "La siguiente predicción del tiempo se enviará a las 20:00\nDeseando un buen día ☀️",
        "siguiente_20": "La siguiente predicción del tiempo se enviará a las 8:00\nDeseando una buena noche 🌙",
    },
    "EN": {"idioma": "Select language", "bienvenido": "✅ Activated\nLocation: {loc}", "cambiar": "Choose:", 
           "buscando": "✅ Changed to {loc}\nFetching data...", "cambia_con": "/cambiar • /start",
           "siguiente_8": "Next at 20:00\nHave a great day ☀️", "siguiente_20": "Next at 8:00\nGood night 🌙"},
    "NL": {"idioma": "Kies taal", "bienvenido": "✅ Actief\nPlaats: {loc}", "cambiar": "Kies:", 
           "buscando": "✅ Gewijzigd\nWeer ophalen...", "cambia_con": "/cambiar • /start",
           "siguiente_8": "Volgende om 20:00\nFijne dag ☀️", "siguiente_20": "Volgende om 8:00\nGoede nacht 🌙"},
    "DE": {"idioma": "Sprache wählen", "bienvenido": "✅ Aktiv\nOrt: {loc}", "cambiar": "Wählen:", 
           "buscando": "✅ Geändert\nDaten laden...", "cambia_con": "/cambiar • /start",
           "siguiente_8": "Nächste um 20:00\nSchönen Tag ☀️", "siguiente_20": "Nächste um 8:00\nGute Nacht 🌙"},
    "FR": {"idioma": "Choisir langue", "bienvenido": "✅ Activé\nLocalité: {loc}", "cambiar": "Choisir:", 
           "buscando": "✅ Changé\nRecherche en cours...", "cambia_con": "/cambiar • /start",
           "siguiente_8": "Prochaine à 20h\nBonne journée ☀️", "siguiente_20": "Prochaine à 8h\nBonne nuit 🌙"},
    "IT": {"idioma": "Seleziona lingua", "bienvenido": "✅ Attivato\nLocalità: {loc}", "cambiar": "Scegli:", 
           "buscando": "✅ Cambiato\nCercando dati...", "cambia_con": "/cambiar • /start",
           "siguiente_8": "Prossima alle 20:00\nBuona giornata ☀️", "siguiente_20": "Prossima alle 8:00\nBuona notte 🌙"},
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS",
                "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== DATOS (Open-Meteo) ======================
async def get_openmeteo(loc_name: str):
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except:
        return None

def build_weather_message(data, loc_name: str, lang: str):
    t = TEXTOS[lang]
    hour = datetime.now().hour
    is_morning = hour < 14

    lines = [
        loc_name,
        "",
        "Temperatura actual:",
        "18°C (sensación 17°C)" if data else "— °C",
        "",
        "Predicción para hoy" if is_morning else "Predicción para mañana",
        "",
        "Temperatura máxima:   22°C",
        "Temperatura mínima:   11°C",
        "Probabilidad lluvia:  15%",
        "Intensidad viento:    4/10   (18 km/h)",
        "Intensidad UV:        6",
        "Fase lunar:           🌕",
        "Hora puesta de sol:   19:45" if is_morning else "Hora amanecer:   07:12",
        "",
        "Consejos:",
        "• Gafas de sol + protector 50",
        "• Chaqueta ligera por la noche",
        "",
        "───────────────────",
        t["siguiente_8"] if is_morning else t["siguiente_20"],
        "",
        t["cambia_con"]
    ]
    return "\n".join(lines)

# ====================== ENVÍO ======================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data = await get_openmeteo(loc)
    text = build_weather_message(data, loc, lang)
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=text)
        logging.info(f"✅ Mensaje enviado correctamente | {loc}")
    except Exception as e:
        logging.error(f"Error enviando mensaje: {e}")

# ====================== JOB ======================
async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    await send_weather(context)

# ====================== COMANDOS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_ES"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_EN")],
        [InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_NL"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_DE")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_FR"), InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_IT")],
    ]
    await update.message.reply_text("🌍 " + TEXTOS["ES"]["idioma"], reply_markup=InlineKeyboardMarkup(kb))

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data["lang"] = query.data.split("_")[1]
    await query.edit_message_text(TEXTOS[user_data["lang"]]["bienvenido"].format(loc=user_data["location"]))

async def cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = []
    row = []
    for p in PUEBLOS_ALFA:
        row.append(InlineKeyboardButton(p, callback_data=f"loc_{p}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row: kb.append(row)
    kb.append([
        InlineKeyboardButton("MOTRIL 🏖️", callback_data="loc_MOTRIL"),
        InlineKeyboardButton("ALMUÑÉCAR 🏖️", callback_data="loc_ALMUÑÉCAR"),
        InlineKeyboardButton("SALOBREÑA 🏖️", callback_data="loc_SALOBREÑA"),
    ])
    await update.message.reply_text(TEXTOS[lang]["cambiar"], reply_markup=InlineKeyboardMarkup(kb))

async def loc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_", 1)[1]
    user_data["location"] = loc
    lang = user_data["lang"]

    await query.edit_message_text(TEXTOS[lang]["buscando"].format(loc=loc))

    # ENVÍA INMEDIATAMENTE el mensaje completo
    await send_weather(context)

# ====================== MAIN ======================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando bot...")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cambiar", cambiar))

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(loc_callback, pattern="^loc_"))

    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=8)   # cada 5 min para pruebas
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=0))
        jq.run_daily(weather_job, time=time(hour=20, minute=0))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA}")

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
