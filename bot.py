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

MODO_PRUEBA = True   # ← Cambia a False para modo 8:02 y 20:02 real

# ====================== COORDENADAS ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

# ====================== TEXTOS (6 idiomas) ======================
TEXTOS = {
    "ES": {"idioma": "Selecciona idioma / Select language", "bienvenido": "✅ Activado\nPoblación: {loc}\n\n/cambiar para cambiar", 
           "cambiar": "Elige tu localidad:", "cambia_con": "Para cambiar población pulsa /cambiar", 
           "buscando": "✅ Cambiado a {loc}\nBuscando datos del tiempo en {loc}...\nEspere un momento."},
    "EN": {"idioma": "Select language / Selecciona idioma", "bienvenido": "✅ Activated\nLocation: {loc}\n\n/cambiar to change", 
           "cambiar": "Choose location:", "cambia_con": "To change press /cambiar", 
           "buscando": "✅ Changed to {loc}\nFetching weather for {loc}...\nPlease wait."},
    "NL": {"idioma": "Kies taal", "bienvenido": "✅ Actief\nPlaats: {loc}", "cambiar": "Kies plaats:", 
           "cambia_con": "Verander met /cambiar", "buscando": "✅ Gewijzigd naar {loc}\nWeer ophalen..."},
    "DE": {"idioma": "Sprache wählen", "bienvenido": "✅ Aktiv\nOrt: {loc}", "cambiar": "Ort wählen:", 
           "cambia_con": "/cambiar zum Wechseln", "buscando": "✅ Geändert zu {loc}\nDaten werden geladen..."},
    "FR": {"idioma": "Choisir langue", "bienvenido": "✅ Activé\nLocalité: {loc}", "cambiar": "Choisir:", 
           "cambia_con": "/cambiar pour changer", "buscando": "✅ Changé en {loc}\nRecherche météo en cours..."},
    "IT": {"idioma": "Seleziona lingua", "bienvenido": "✅ Attivato\nLocalità: {loc}", "cambiar": "Scegli:", 
           "cambia_con": "/cambiar per cambiare", "buscando": "✅ Cambiato a {loc}\nCercando dati meteo..."},
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

# ====================== PUEBLOS (alfabético + 2 nuevos grandes) ======================
PUEBLOS_ALFA = [
    "BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS",
    "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"
]

# ====================== OPEN-METEO ======================
async def get_openmeteo(loc_name: str):
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,moon_phase&timezone=Europe/Madrid"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except:
        return None

def build_weather_message(data, loc_name: str, lang: str):
    t = TEXTOS[lang]
    now = datetime.now()
    is_morning = now.hour < 14

    lines = [f"{loc_name}\n"]

    # Temperatura actual siempre al principio
    if data:
        c = data["current"]
        lines += [
            "Temperatura actual:",
            f"{round(c.get('temperature_2m', 0))}°C (sensación {round(c.get('apparent_temperature', 0))}°C)\n\n"
        ]

    # Cabecera predicción
    if is_morning or MODO_PRUEBA:
        lines.append("Predicción para hoy")
    else:
        lines.append("Predicción para mañana")

    lines.append("")

    if data:
        d = data["daily"]
        h = data["hourly"]
        max_t = d["temperature_2m_max"][0] if is_morning else d["temperature_2m_max"][1]
        min_t = d["temperature_2m_min"][0] if is_morning else d["temperature_2m_min"][1]

        lines += [
            f"Temperatura máxima:   {max_t}°C",
            f"Temperatura mínima:   {min_t}°C",
            f"Probabilidad lluvia:  {h['precipitation_probability'][12]}%",
            f"Intensidad viento:    {min(10, max(1, round(h['wind_speed_10m'][12]/4)))}/10   ({h['wind_speed_10m'][12]} km/h)",
            f"Intensidad UV:        {data['current'].get('uv_index', 0)}",
            f"Fase lunar:           🌖 Cuarto creciente",
        ]

        astro = d["sunset"][0] if is_morning else d["sunrise"][1]
        hora_str = "Hora puesta de sol:" if is_morning else "Hora amanecer:"
        lines.append(f"{hora_str} {astro}")

        # Consejo simple
        lines.append("\nConsejos:")
        if data['current'].get('uv_index', 0) >= 6:
            lines.append("• Gafas de sol + protector 50")
        if h['precipitation_probability'][12] >= 40:
            lines.append("• Lleva paraguas")
        if h['wind_speed_10m'][12] >= 20 or max_t <= 15:
            lines.append("• Chaqueta + abrigo ligero")
        else:
            lines.append("• Ropa ligera + crema solar")

    lines += ["\n", t["cambia_con"]]

    return "\n".join(lines)

# ====================== ENVÍO ======================
async def send_weather(context: ContextTypes.DEFAULT_TYPE, immediate: bool = False):
    lang = user_data["lang"]
    loc = user_data["location"]
    data = await get_openmeteo(loc)
    text = build_weather_message(data, loc, lang)
    await context.bot.send_message(CHAT_ID, text, parse_mode="Markdown")

# ====================== JOB PROGRAMADO ======================
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
    lang = query.data.split("_")[1]
    user_data["lang"] = lang
    await query.edit_message_text(TEXTOS[lang]["bienvenido"].format(loc=user_data["location"]))

async def cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = []
    row = []
    for p in PUEBLOS_ALFA:
        row.append(InlineKeyboardButton(p, callback_data=f"loc_{p}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

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

    # Mensaje de confirmación + buscando
    await query.edit_message_text(
        TEXTOS[lang]["buscando"].format(loc=loc),
        parse_mode="Markdown"
    )

    # Enviar inmediatamente el tiempo actualizado
    await send_weather(context, immediate=True)

# ====================== MAIN ======================
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
        jq.run_repeating(weather_job, interval=300, first=5)
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=2))
        jq.run_daily(weather_job, time=time(hour=20, minute=2))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA}")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
