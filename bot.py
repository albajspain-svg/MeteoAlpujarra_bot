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

MODO_PRUEBA = True   # ← Cambia a False para modo real (8:02 y 20:02)

# ====================== COORDENADAS (para Open-Meteo) ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

# ====================== TEXTOS EN 6 IDIOMAS ======================
TEXTOS = {
    "ES": {
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Bot activado\n🌡️ Población: {loc}\n\n/cambiar → cambiar localidad",
        "cambiar": "Elige tu localidad:",
        "cambia_con": "Para cambiar población: escribe /cambiar y pulsa intro",
        "error": "❌ Error al obtener el tiempo",
        "mañana": "🌅 Mañana", "tarde": "🌇 Tarde",
        "max": "🔼 Máx", "min": "🔽 Mín", "uv": "☀️ UV", "lluvia": "☔ Lluvia", "viento": "🌬️ Viento",
        "intensidad": "💨 Intensidad", "consejo": "🧥 Consejo:",
        "ropa": "Abrigo + chaqueta", "gafas": "Gafas de sol + protector 50", "paraguas": "Lleva paraguas",
        "ligero": "Camiseta + crema solar",
    },
    "EN": {
        "idioma": "Select language / Selecciona idioma",
        "bienvenido": "✅ Bot activated\n🌡️ Location: {loc}\n\n/cambiar to change",
        "cambiar": "Choose your location:",
        "cambia_con": "To change location: /cambiar + Enter",
        "error": "❌ Error fetching weather",
        "mañana": "🌅 Morning", "tarde": "🌇 Afternoon",
        "max": "🔼 Max", "min": "🔽 Min", "uv": "☀️ UV", "lluvia": "☔ Rain", "viento": "🌬️ Wind",
        "intensidad": "💨 Intensity", "consejo": "🧥 Advice:",
        "ropa": "Jacket + sweater", "gafas": "Sunglasses + SPF50", "paraguas": "Take umbrella",
        "ligero": "T-shirt + sunscreen",
    },
    "NL": {
        "idioma": "Kies taal / Select language",
        "bienvenido": "✅ Bot actief\n🌡️ Plaats: {loc}\n\n/cambiar om te wijzigen",
        "cambiar": "Kies locatie:",
        "cambia_con": "Verander plaats: /cambiar + enter",
        "error": "❌ Weer ophalen mislukt",
        "mañana": "🌅 Ochtend", "tarde": "🌇 Middag",
        "max": "🔼 Max", "min": "🔽 Min", "uv": "☀️ UV", "lluvia": "☔ Regen", "viento": "🌬️ Wind",
        "intensidad": "💨 Kracht", "consejo": "🧥 Tip:",
        "ropa": "Jas + trui", "gafas": "Zonnebril + factor 50", "paraguas": "Neem paraplu",
        "ligero": "T-shirt + zonnecrème",
    },
    "DE": {
        "idioma": "Sprache wählen",
        "bienvenido": "✅ Bot aktiv\n🌡️ Ort: {loc}\n\n/cambiar zum Ändern",
        "cambiar": "Ort wählen:",
        "cambia_con": "/cambiar zum Wechseln",
        "error": "❌ Wetterabruf fehlgeschlagen",
        "mañana": "🌅 Vormittag", "tarde": "🌇 Nachmittag",
        "max": "🔼 Max", "min": "🔽 Min", "uv": "☀️ UV", "lluvia": "☔ Regen", "viento": "🌬️ Wind",
        "intensidad": "💨 Stärke", "consejo": "🧥 Tipp:",
        "ropa": "Jacke + Pullover", "gafas": "Sonnenbrille + LSF50", "paraguas": "Regenschirm mitnehmen",
        "ligero": "T-Shirt + Sonnencreme",
    },
    "FR": {
        "idioma": "Choisir langue",
        "bienvenido": "✅ Bot activé\n🌡️ Localité: {loc}\n\n/cambiar pour changer",
        "cambiar": "Choisir localité:",
        "cambia_con": "/cambiar pour changer",
        "error": "❌ Impossible d'obtenir la météo",
        "mañana": "🌅 Matin", "tarde": "🌇 Après-midi",
        "max": "🔼 Max", "min": "🔽 Min", "uv": "☀️ UV", "lluvia": "☔ Pluie", "viento": "🌬️ Vent",
        "intensidad": "💨 Intensité", "consejo": "🧥 Conseil:",
        "ropa": "Veste + pull", "gafas": "Lunettes + crème 50", "paraguas": "Prendre parapluie",
        "ligero": "T-shirt + crème solaire",
    },
    "IT": {
        "idioma": "Seleziona lingua / Select language",
        "bienvenido": "✅ Bot attivato\n🌡️ Località: {loc}\n\n/cambiar per cambiare",
        "cambiar": "Scegli località:",
        "cambia_con": "/cambiar per cambiare località",
        "error": "❌ Errore nel recupero meteo",
        "mañana": "🌅 Mattina", "tarde": "🌇 Pomeriggio",
        "max": "🔼 Max", "min": "🔽 Min", "uv": "☀️ UV", "lluvia": "☔ Pioggia", "viento": "🌬️ Vento",
        "intensidad": "💨 Intensità", "consejo": "🧥 Consiglio:",
        "ropa": "Giacca + maglione", "gafas": "Occhiali + protezione 50", "paraguas": "Porta ombrello",
        "ligero": "Maglietta + crema solare",
    }
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

# ====================== LISTA PUEBLOS (alfabético) ======================
PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ"]

# ====================== OBTENER DATOS FIABLES (Open-Meteo) ======================
async def get_openmeteo(loc_name: str):
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_gusts_10m,uv_index,precipitation_probability"
        f"&hourly=temperature_2m,precipitation_probability,wind_speed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset"
        f"&timezone=Europe/Madrid"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logging.error(f"Open-Meteo error: {e}")
        return None

def generar_mensaje(data, loc_name: str, lang: str, real_mode: bool):
    if not data:
        return TEXTOS[lang]["error"]

    t = TEXTOS[lang]
    lines = [f"🌤️ **{loc_name}**  {datetime.now().strftime('%d/%m %H:%M')}"]

    # Datos actuales
    c = data["current"]
    temp = round(c.get("temperature_2m", 0))
    sens = round(c.get("apparent_temperature", temp))
    uv = round(c.get("uv_index", 0))
    rain = c.get("precipitation_probability", 0)
    wind = round(c.get("wind_speed_10m", 0))
    intensidad = min(10, max(1, wind // 4 + 1))

    lines += [
        f"{t['mañana']}: {data['hourly']['temperature_2m'][8]}°C • {data['hourly']['precipitation_probability'][8]}% ☔",
        f"{t['tarde']}: {data['hourly']['temperature_2m'][14]}°C • {data['hourly']['precipitation_probability'][14]}% ☔",
        f"{t['max']}: {data['daily']['temperature_2m_max'][0]}°C  |  {t['min']}: {data['daily']['temperature_2m_min'][0]}°C",
        f"{t['uv']}: {uv}  |  {t['lluvia']}: {rain}%  |  {t['viento']}: {wind} km/h  |  {t['intensidad']}: {intensidad}/10",
    ]

    # Consejos inteligentes
    consejo = t["ligero"]
    if uv >= 6: consejo = t["gafas"]
    if rain >= 40: consejo = t["paraguas"]
    if temp <= 14 or wind >= 25: consejo = t["ropa"]
    if uv >= 8 and rain < 20: consejo += " + 🕶️"

    lines += [f"{t['consejo']} {consejo}"]

    lines += ["", t["cambia_con"]]
    return "\n".join(lines)

# ====================== JOB ======================
async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data = await get_openmeteo(loc)
    text = generar_mensaje(data, loc, lang, real_mode=not MODO_PRUEBA)
    await context.bot.send_message(CHAT_ID, text, parse_mode="Markdown")
    logging.info(f"✅ Enviado | {loc} | {lang}")

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
    # 3 columnas pueblos alfa UPPERCASE sin emoji
    kb = []
    row = []
    for p in PUEBLOS_ALFA:
        row.append(InlineKeyboardButton(p, callback_data=f"loc_{p}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row: kb.append(row)

    # Playa abajo con emoji
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
    await query.edit_message_text(f"✅ **{loc}** activado\n\n{TEXTOS[lang]['cambia_con']}", parse_mode="Markdown")

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

    # JobQueue (está en python-telegram-bot 20.x - sin requirements extra)
    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=10)
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=2))
        jq.run_daily(weather_job, time=time(hour=20, minute=2))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA} | Open-Meteo activo")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
