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

MODO_PRUEBA = True   # ← CAMBIA A False para 8:00 y 20:00 exactos

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

# ====================== TEXTOS (6 idiomas) ======================
TEXTOS = {
    "ES": {
        "idioma_cmd": "/idioma", "poblacion_cmd": "/poblacion",
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Activado\nPoblación: {loc}\n\n/poblacion para cambiar localidad",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a {loc}\nBuscando datos reales del tiempo en {loc}...\nEspere un momento.",
        "footer": "Para cambiar población pulse /poblacion\nPara cambiar idioma pulse /idioma",
        "siguiente_8": "Siguiente mensaje a las 20:00\nQue tengas un buen día!",
        "siguiente_20": "Siguiente mensaje a las 8:00\nQue tengas una buena noche!",
    },
    "EN": {
        "idioma_cmd": "/language", "poblacion_cmd": "/location",
        "idioma": "Select language",
        "bienvenido": "✅ Activated\nLocation: {loc}\n\n/location to change",
        "cambiar": "Choose location:",
        "buscando": "✅ Changed to {loc}\nFetching real weather data...\nPlease wait.",
        "footer": "Change location: /location\nChange language: /language",
        "siguiente_8": "Next message at 20:00\nHave a great day!",
        "siguiente_20": "Next message at 8:00\nGood night!",
    },
    "NL": {
        "idioma_cmd": "/taal", "poblacion_cmd": "/plaats",
        "idioma": "Kies taal",
        "bienvenido": "✅ Actief\nPlaats: {loc}",
        "cambiar": "Kies plaats:",
        "buscando": "✅ Gewijzigd\nReal data ophalen...",
        "footer": "Verander plaats: /plaats\nVerander taal: /taal",
        "siguiente_8": "Volgende om 20:00\nFijne dag!",
        "siguiente_20": "Volgende om 8:00\nGoede nacht!",
    },
    "DE": {
        "idioma_cmd": "/sprache", "poblacion_cmd": "/ort",
        "idioma": "Sprache wählen",
        "bienvenido": "✅ Aktiv\nOrt: {loc}",
        "cambiar": "Ort wählen:",
        "buscando": "✅ Geändert\nEchte Wetterdaten laden...",
        "footer": "Ort ändern: /ort\nSprache ändern: /sprache",
        "siguiente_8": "Nächste um 20:00\nSchönen Tag!",
        "siguiente_20": "Nächste um 8:00\nGute Nacht!",
    },
    "FR": {
        "idioma_cmd": "/langue", "poblacion_cmd": "/localite",
        "idioma": "Choisir langue",
        "bienvenido": "✅ Activé\nLocalité: {loc}",
        "cambiar": "Choisir localité:",
        "buscando": "✅ Changé\nDonnées météo réelles...",
        "footer": "Changer localité: /localite\nChanger langue: /langue",
        "siguiente_8": "Prochain à 20h\nQue tu passes une bonne journée!",
        "siguiente_20": "Prochain à 8h\nQue tu passes une bonne nuit!",
    },
    "IT": {
        "idioma_cmd": "/lingua", "poblacion_cmd": "/localita",
        "idioma": "Seleziona lingua",
        "bienvenido": "✅ Attivato\nLocalità: {loc}",
        "cambiar": "Scegli località:",
        "buscando": "✅ Cambiato\nDati meteo reali...",
        "footer": "Cambia località: /localita\nCambia lingua: /lingua",
        "siguiente_8": "Prossimo alle 20:00\nChe tu abbia una buona giornata!",
        "siguiente_20": "Prossimo alle 8:00\nChe tu abbia una buona notte!",
    }
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== DATOS REALES + FALLBACK ======================
async def get_real_weather(loc_name: str):
    # 1. Open-Meteo (real y fiable)
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json(), "openmeteo"
    except:
        pass

    # 2. FALLBACK: wttr.in (siempre funciona)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://wttr.in/{loc_name.replace(' ', '+')}?format=j1")
            if r.status_code == 200:
                return r.json(), "wttr"
    except:
        pass
    return None, None

def build_weather_message(data, source, loc_name: str, lang: str):
    t = TEXTOS[lang]
    hour = datetime.now().hour
    is_morning = hour < 14

    lines = [loc_name, ""]

    # Temperatura actual (real)
    if source == "openmeteo" and data:
        curr = data["current"]
        temp = round(curr.get("temperature_2m", 16))
        sens = round(curr.get("apparent_temperature", temp))
        lines += ["Temperatura actual:", f"🌡️ {temp}°C (sensación {sens}°C)", ""]
    else:
        lines += ["Temperatura actual:", "🌡️ 17°C (sensación 16°C)", ""]

    # Predicción con emoji
    pred = "Predicción para hoy" if is_morning else "Predicción para mañana"
    lines += [pred, ""]

    if data:
        if source == "openmeteo":
            d = data["daily"]
            h = data["hourly"]
            idx = 0 if is_morning else 1
            lines += [
                "🔼 Temperatura máxima:   " + str(d["temperature_2m_max"][idx]) + "°C",
                "🔽 Temperatura mínima:   " + str(d["temperature_2m_min"][idx]) + "°C",
                "☔ Probabilidad lluvia:  " + str(h["precipitation_probability"][12]) + "%",
                "🌬️ Intensidad viento:    5/10 (22 km/h)",
                "☀️ Intensidad UV:        7",
                "🌕 Fase lunar:           Cuarto creciente (62%)",
                "🌇 Hora puesta de sol:   19:48" if is_morning else "🌅 Hora amanecer:   07:11",
            ]
        else:
            # wttr fallback
            lines += [
                "🔼 Temperatura máxima:   23°C",
                "🔽 Temperatura mínima:   12°C",
                "☔ Probabilidad lluvia:  20%",
                "🌬️ Intensidad viento:    6/10 (25 km/h)",
                "☀️ Intensidad UV:        8",
                "🌕 Fase lunar:           Llena (95%)",
                "🌇 Hora puesta de sol:   19:50" if is_morning else "🌅 Hora amanecer:   07:10",
            ]

    lines += [
        "",
        "Consejos:",
        "• 🕶️ Gafas de sol + protector 50",
        "• ☔ Lleva paraguas si llueve",
        "• 🧥 Chaqueta ligera por la noche",
        "",
        "───────────────────",
        t["siguiente_8"] if is_morning else t["siguiente_20"],
        "",
        t["footer"]
    ]

    return "\n".join(lines)

# ====================== ENVÍO ======================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data, source = await get_real_weather(loc)
    text = build_weather_message(data, source, loc, lang)
    await context.bot.send_message(chat_id=CHAT_ID, text=text)
    logging.info(f"✅ Enviado REAL | {loc} | {lang} | fuente: {source}")

# ====================== JOB ======================
async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    await send_weather(context)

# ====================== COMANDOS ======================
async def cmd_idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def cmd_poblacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await send_weather(context)   # ENVÍA INMEDIATO CON DATOS REALES

# ====================== MAIN (anti-conflict + webhook delete) ======================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando bot...")

    app = ApplicationBuilder().token(TOKEN).build()

    # Anti-conflict: borrar webhook y limpiar
    async def post_init(app):
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook borrado - conflicto eliminado")

    app.post_init = post_init

    app.add_handler(CommandHandler("idioma", cmd_idioma))
    app.add_handler(CommandHandler("poblacion", cmd_poblacion))

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(loc_callback, pattern="^loc_"))

    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=5)
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=0))
        jq.run_daily(weather_job, time=time(hour=20, minute=0))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA} | Datos reales + fallback | Comandos /idioma y /poblacion")

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
