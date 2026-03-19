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

MODO_PRUEBA = True   # ← Cambia a False para modo REAL (exactamente 8:00 y 20:00)

# ====================== COORDENADAS ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

# ====================== TEXTOS COMPLETOS ======================
TEXTOS = {
    "ES": {
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Activado\nPoblación: {loc}\n\n/cambiar para cambiar",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a **{loc}**\nBuscando datos del tiempo en {loc}...\nEspere un momento.",
        "cambia_con": "Para cambiar población pulse /cambiar\nPara cambiar idioma pulse /start",
        "siguiente_8": "La siguiente predicción se enviará a las 8:00\nDeseando un buen día ☀️",
        "siguiente_20": "La siguiente predicción se enviará a las 20:00\nDeseando una buena noche 🌙",
    },
    "EN": {"idioma": "Select language", "bienvenido": "✅ Activated\nLocation: {loc}", "cambiar": "Choose location:", 
           "buscando": "✅ Changed to **{loc}**\nFetching weather...\nPlease wait.", "cambia_con": "Change location: /cambiar\nChange language: /start",
           "siguiente_8": "Next forecast at 8:00 AM\nHave a great day ☀️", "siguiente_20": "Next forecast at 8:00 PM\nGood night 🌙"},
    "NL": {"idioma": "Kies taal", "bienvenido": "✅ Actief\nPlaats: {loc}", "cambiar": "Kies plaats:", 
           "buscando": "✅ Gewijzigd\nWeer ophalen...", "cambia_con": "/cambiar • /start", 
           "siguiente_8": "Volgende om 8:00\nFijne dag ☀️", "siguiente_20": "Volgende om 20:00\nGoede nacht 🌙"},
    "DE": {"idioma": "Sprache wählen", "bienvenido": "✅ Aktiv\nOrt: {loc}", "cambiar": "Ort wählen:", 
           "buscando": "✅ Geändert\nDaten werden geladen...", "cambia_con": "/cambiar • /start", 
           "siguiente_8": "Nächste um 8:00\nSchönen Tag ☀️", "siguiente_20": "Nächste um 20:00\nGute Nacht 🌙"},
    "FR": {"idioma": "Choisir langue", "bienvenido": "✅ Activé\nLocalité: {loc}", "cambiar": "Choisir:", 
           "buscando": "✅ Changé\nMétéo en cours...", "cambia_con": "/cambiar • /start", 
           "siguiente_8": "Prochaine à 8h\nBonne journée ☀️", "siguiente_20": "Prochaine à 20h\nBonne nuit 🌙"},
    "IT": {"idioma": "Seleziona lingua", "bienvenido": "✅ Attivato\nLocalità: {loc}", "cambiar": "Scegli:", 
           "buscando": "✅ Cambiato\nCercando meteo...", "cambia_con": "/cambiar • /start", 
           "siguiente_8": "Prossima alle 8:00\nBuona giornata ☀️", "siguiente_20": "Prossima alle 20:00\nBuona notte 🌙"},
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== OPEN-METEO (CORREGIDO - sin errores 400) ======================
async def get_openmeteo(loc_name: str):
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logging.error(f"API error: {e}")
        return None

def build_weather_message(data, loc_name: str, lang: str):
    t = TEXTOS[lang]
    hour = datetime.now().hour
    is_morning = hour < 14

    lines = [f"{loc_name}\n", "Temperatura actual:"]

    if data:
        c = data["current"]
        lines.append(f"{round(c.get('temperature_2m', 0))}°C (sensación {round(c.get('apparent_temperature', 0))}°C)\n")
    else:
        lines.append("— °C\n")

    lines.append("Predicción para hoy" if is_morning else "Predicción para mañana")
    lines.append("")

    if data:
        d = data["daily"]
        h = data["hourly"]
        day_idx = 0 if is_morning else 1

        lines += [
            f"Temperatura máxima:   {d['temperature_2m_max'][day_idx]}°C",
            f"Temperatura mínima:   {d['temperature_2m_min'][day_idx]}°C",
            f"Probabilidad lluvia:  {h['precipitation_probability'][12]}%",
            f"Intensidad viento:    {min(10, round(h['wind_speed_10m'][12]/3.5))}/10   ({h['wind_speed_10m'][12]} km/h)",
            f"Intensidad UV:        {data['current'].get('uv_index', 5)}",
            f"Fase lunar:           🌕 Llena",
            f"Hora {'puesta de sol' if is_morning else 'amanecer'}: {d['sunset' if is_morning else 'sunrise'][day_idx]}",
        ]

    lines.append("\nConsejos:\n• Gafas de sol + protector 50\n• Ropa ligera si no llueve\n• Lleva chaqueta si hace viento")

    lines.append("\n___________________")

    # Footer en idioma seleccionado
    footer = t["siguiente_8"] if is_morning else t["siguiente_20"]
    lines.append(footer)
    lines.append(t["cambia_con"])

    return "\n".join(lines)

# ====================== ENVÍO ======================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data = await get_openmeteo(loc)
    text = build_weather_message(data, loc, lang)
    await context.bot.send_message(CHAT_ID, text, parse_mode="Markdown")
    logging.info(f"✅ Enviado | {loc} | {lang}")

# ====================== JOB (exacto 8:00 y 20:00) ======================
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

    await query.edit_message_text(TEXTOS[lang]["buscando"].format(loc=loc), parse_mode="Markdown")

    # Enviar inmediatamente
    await send_weather(context)

# ====================== MAIN (limpio - sin conflictos) ======================
def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando bot...")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cambiar", cambiar))

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(loc_callback, pattern="^loc_"))

    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=10)   # pruebas cada 5 min
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=0))
        jq.run_daily(weather_job, time=time(hour=20, minute=0))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA} | Horas exactas programadas")

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
