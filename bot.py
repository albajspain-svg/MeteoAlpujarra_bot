import logging
import os
from datetime import datetime, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import httpx

# ====================== CONFIG ======================
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))          # ← Añade también esta variable en Railway → CHAT_ID con tu chat ID

if not TOKEN:
    raise ValueError("❌ FALTA BOT_TOKEN en Variables de Railway")
if not CHAT_ID:
    raise ValueError("❌ FALTA CHAT_ID en Variables de Railway")

MODO_PRUEBA = True        # ← Cambia SOLO esta línea a False para modo real (8:02 y 20:02)

# ====================== LOCALIDADES ======================
LOCATION_MAP = {
    "Órgiva": "Orgiva", "Lanjarón": "Lanjaron", "Pampaneira": "Orgiva",
    "Bubión": "Orgiva", "Capileira": "Orgiva", "Trevélez": "Orgiva",
    "Bayacas": "Orgiva", "El Morreón": "Orgiva",
    "Los Tablones": "Orgiva", "Las Barreras": "Orgiva",
    "Motril": "Motril", "Almuñécar": "Almunecar", "Salobreña": "Salobrena",
}

SELECTOR_LOCALIDADES = [
    ("🇪🇸 Órgiva", "Órgiva"),
    ("🏔️ Bayacas", "Bayacas"),
    ("🏔️ El Morreón", "El Morreón"),
    ("🏔️ Los Tablones", "Los Tablones"),
    ("🏔️ Las Barreras", "Las Barreras"),
    ("🇪🇸 Lanjarón", "Lanjarón"),
    ("🇪🇸 Pampaneira", "Pampaneira"),
    ("🇪🇸 Bubión", "Bubión"),
    ("🇪🇸 Capileira", "Capileira"),
    ("🇪🇸 Trevélez", "Trevélez"),
]

# ====================== TEXTOS EN 5 IDIOMAS ======================
TEXTOS = {
    "ES": {
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Bot activado\nPoblación actual: {loc}\n\nEnvía /cambiar para elegir otra",
        "cambiar": "Elige tu localidad:",
        "cambia_con": "Para cambiar población escribe /cambiar y pulsa intro",
        "error": "❌ No se pudo obtener el tiempo",
        "puesta": "🌇 Puesta de sol hoy",
        "salida": "🌅 Salida de sol mañana",
    },
    "EN": {
        "idioma": "Select language / Selecciona idioma",
        "bienvenido": "✅ Bot activated\nCurrent location: {loc}\n\nSend /cambiar to change",
        "cambiar": "Choose your location:",
        "cambia_con": "To change location type /cambiar and press enter",
        "error": "❌ Could not get weather",
        "puesta": "🌇 Sunset today",
        "salida": "🌅 Sunrise tomorrow",
    },
    "NL": {
        "idioma": "Kies taal / Select language",
        "bienvenido": "✅ Bot geactiveerd\nHuidige plaats: {loc}\n\nStuur /cambiar om te wijzigen",
        "cambiar": "Kies je locatie:",
        "cambia_con": "Om plaats te wijzigen typ /cambiar en druk enter",
        "error": "❌ Kon weer niet ophalen",
        "puesta": "🌇 Zonsondergang vandaag",
        "salida": "🌅 Zonsopgang morgen",
    },
    "DE": {
        "idioma": "Sprache wählen / Select language",
        "bienvenido": "✅ Bot aktiviert\nAktueller Ort: {loc}\n\n/cambiar zum Ändern",
        "cambiar": "Wähle deinen Ort:",
        "cambia_con": "Zum Ändern des Ortes /cambiar schreiben und Enter",
        "error": "❌ Wetter konnte nicht abgerufen werden",
        "puesta": "🌇 Sonnenuntergang heute",
        "salida": "🌅 Sonnenaufgang morgen",
    },
    "FR": {
        "idioma": "Choisir la langue / Select language",
        "bienvenido": "✅ Bot activé\nLocalité actuelle : {loc}\n\n/cambiar pour changer",
        "cambiar": "Choisissez votre localité :",
        "cambia_con": "Pour changer de localité tape /cambiar et appuie sur Entrée",
        "error": "❌ Impossible d'obtenir la météo",
        "puesta": "🌇 Coucher du soleil aujourd'hui",
        "salida": "🌅 Lever du soleil demain",
    }
}

user_data = {"lang": "ES", "location": "Órgiva"}

# ====================== FUNCIONES CLIMA ======================
async def get_weather_data(loc_name: str):
    code = LOCATION_MAP.get(loc_name, "Orgiva")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://wttr.in/{code}?format=j1")
        r.raise_for_status()
        return r.json()

def build_message(data, loc_name: str, lang: str, real_mode: bool):
    if not data:
        return TEXTOS[lang]["error"]

    txt = [f"🌤️ **{loc_name}** — {datetime.now().strftime('%d/%m %H:%M')}"]

    try:
        curr = data["current_condition"][0] if data.get("current_condition") else data["weather"][0]["hourly"][-1]
        txt += [
            f"🌡️ {curr.get('temp_C', '—')}°C  (sens. {curr.get('FeelsLikeC', '—')}°C)",
            f"☔ {curr.get('chanceofrain', '—')}%   UV {curr.get('uvIndex', '—')}",
        ]

        if data.get("weather"):
            h = data["weather"][0]["hourly"]
            if len(h) > 14:
                txt += [
                    f"🌅 Mañana ≈ {h[8].get('tempC','—')}°C ({h[8].get('chanceofrain','—')}% lluvia)",
                    f"🌇 Tarde  ≈ {h[14].get('tempC','—')}°C ({h[14].get('chanceofrain','—')}% lluvia)",
                ]
            astro = data["weather"][0]["astronomy"][0]
            key = "puesta" if real_mode else "salida"
            txt.append(f"{TEXTOS[lang][key]}: {astro.get('sunset' if real_mode else 'sunrise', '—')}")

    except:
        txt.append("⚠️ Datos parciales")

    txt += ["", TEXTOS[lang]["cambia_con"]]
    return "\n".join(txt)

# ====================== JOB ======================
async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data = await get_weather_data(loc)
    text = build_message(data, loc, lang, real_mode=not MODO_PRUEBA)
    await context.bot.send_message(CHAT_ID, text, parse_mode="Markdown")
    logging.info(f"✅ Mensaje enviado | {loc} | {lang}")

# ====================== COMANDOS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_ES")],
        [InlineKeyboardButton("🇬🇧 English",  callback_data="lang_EN")],
        [InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_NL")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_DE")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_FR")],
    ]
    await update.message.reply_text(
        "🌍 " + TEXTOS["ES"]["idioma"],
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    user_data["lang"] = lang
    await query.edit_message_text(TEXTOS[lang]["bienvenido"].format(loc=user_data["location"]))

async def cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = [[InlineKeyboardButton(txt, callback_data=f"loc_{val}")] for txt, val in SELECTOR_LOCALIDADES]
    kb += [
        [InlineKeyboardButton("Motril",      callback_data="loc_Motril")],
        [InlineKeyboardButton("Almuñécar",   callback_data="loc_Almuñécar")],
        [InlineKeyboardButton("Salobreña",   callback_data="loc_Salobreña")],
    ]
    await update.message.reply_text(TEXTOS[lang]["cambiar"], reply_markup=InlineKeyboardMarkup(kb))

async def loc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_", 1)[1]
    user_data["location"] = loc
    lang = user_data["lang"]
    await query.edit_message_text(
        f"✅ **{loc}** activado\n\n{TEXTOS[lang]['cambia_con']}",
        parse_mode="Markdown"
    )

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

    # JOB QUEUE (la forma correcta y estable)
    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=10)   # cada 5 min
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=2))
        jq.run_daily(weather_job, time=time(hour=20, minute=2))

    logger.info(f"✅ Bot listo | Modo prueba = {MODO_PRUEBA} | CHAT_ID = {CHAT_ID}")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
