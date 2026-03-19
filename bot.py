import logging
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ────────────────────────────────────────────────
#  Logging (muy importante para ver qué pasa en Railway)
# ────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
#  Configuración
# ────────────────────────────────────────────────
TOKEN = "TU_BOT_TOKEN_AQUI"           # CAMBIAR
ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"     # CAMBIAR (tu chat id)

MODO_PRUEBA = True                    # False → 8:02 y 20:02 todos los días

# Localidades
PRINCIPALES = ["Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez"]
EXTRAS = ["Motril", "Almuñécar", "Salobreña"]

LOCATION_MAP = {
    "Órgiva": "Orgiva",
    "Lanjarón": "Lanjaron",
    "Pampaneira": "Orgiva",
    "Bubión": "Orgiva",
    "Capileira": "Orgiva",
    "Trevélez": "Orgiva",
    "Bayacas": "Orgiva",
    "El Morreón": "Orgiva",
    "Los Tablones": "Orgiva",
    "Las Barreras": "Orgiva",
    "Motril": "Motril",
    "Almuñécar": "Almunecar",
    "Salobreña": "Salobrena",
}

LOCALIDADES_SELECTOR = [
    ("🇪🇸 Órgiva",       "Órgiva"),
    ("🏔️ Bayacas",      "Bayacas"),
    ("🏔️ El Morreón",   "El Morreón"),
    ("🏔️ Los Tablones", "Los Tablones"),
    ("🏔️ Las Barreras", "Las Barreras"),
    ("🇪🇸 Lanjarón",     "Lanjarón"),
    ("🇪🇸 Pampaneira",   "Pampaneira"),
    ("🇪🇸 Bubión",       "Bubión"),
    ("🇪🇸 Capileira",    "Capileira"),
    ("🇪🇸 Trevélez",     "Trevélez"),
]

# ────────────────────────────────────────────────
#  Estado por chat
# ────────────────────────────────────────────────
user_data = {}  # chat_id → {"lang": "ES", "location": "Órgiva"}

TEXTOS = {
    "ES": {
        "selecciona_idioma": "Selecciona idioma / Select language",
        "bienvenido": "¡Bienvenido! 🌤️\nPoblación: {loc}\n\n/cambiar para elegir otra",
        "cambiar": "Elige localidad:",
        "cambia_con": "Para cambiar población: /cambiar",
        "error_clima": "❌ No se pudo obtener el tiempo",
        "hora_puesta": "🌇 Puesta sol hoy",
        "hora_salida": "🌅 Salida sol mañana",
    },
    "EN": {
        "selecciona_idioma": "Select language / Selecciona idioma",
        "bienvenido": "Welcome! 🌤️\nLocation: {loc}\n\n/cambiar to change",
        "cambiar": "Choose location:",
        "cambia_con": "To change location: /cambiar",
        "error_clima": "❌ Could not get weather",
        "hora_puesta": "🌇 Sunset today",
        "hora_salida": "🌅 Sunrise tomorrow",
    }
}

# ────────────────────────────────────────────────
#  Obtener datos wttr.in
# ────────────────────────────────────────────────
async def fetch_weather_data(location: str):
    loc = LOCATION_MAP.get(location, "Orgiva")
    url = f"https://wttr.in/{loc}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"Error fetching weather for {loc}: {e}")
        return None


def format_weather_message(data, location: str, lang: str = "ES", real_mode: bool = False):
    if not data:
        return TEXTOS[lang]["error_clima"]

    lines = [f"🌤️ **{location}**   {datetime.now().strftime('%d/%m/%Y %H:%M')}"]

    try:
        curr = data["current_condition"][0] if data.get("current_condition") else data["weather"][0]["hourly"][-1]

        temp = curr.get("temp_C", "—")
        feels = curr.get("FeelsLikeC", "—")
        rain = curr.get("chanceofrain", "—")
        uv = curr.get("uvIndex", "—")

        lines.extend([
            f"🌡️ {temp}°C (sens. {feels}°C)",
            f"☔ {rain}%   UV {uv}",
        ])

        if data.get("weather"):
            hourly = data["weather"][0].get("hourly", [])
            if len(hourly) > 14:
                man = hourly[8]
                tar = hourly[14]
                lines.extend([
                    f"🌅 Mañ ≈ {man.get('tempC','—')}°C  ({man.get('chanceofrain','—')}% lluvia)",
                    f"🌇 Tard ≈ {tar.get('tempC','—')}°C  ({tar.get('chanceofrain','—')}% lluvia)",
                ])

            astro = data["weather"][0].get("astronomy", [{}])[0]
            key = "hora_puesta" if real_mode else "hora_salida"
            value = astro.get("sunset" if real_mode else "sunrise", "—")
            lines.append(f"{TEXTOS[lang][key]}: {value}")

    except Exception as e:
        logger.error(f"Parse error: {e}")
        lines.append("⚠️ Datos parciales o error")

    lines.append("")
    lines.append(TEXTOS[lang]["cambia_con"])

    return "\n".join(lines)


# ────────────────────────────────────────────────
#  Job programado
# ────────────────────────────────────────────────
async def job_send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ADMIN_CHAT_ID
    if chat_id not in user_data:
        user_data[chat_id] = {"lang": "ES", "location": "Órgiva"}

    loc = user_data[chat_id]["location"]
    lang = user_data[chat_id]["lang"]

    data = await fetch_weather_data(loc)
    if not data:
        await context.bot.send_message(chat_id, TEXTOS[lang]["error_clima"])
        return

    text = format_weather_message(data, loc, lang, real_mode=not MODO_PRUEBA)
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")


# ────────────────────────────────────────────────
#  Comandos
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Español 🇪🇸", callback_data="lang_ES")],
        [InlineKeyboardButton("English  🇬🇧", callback_data="lang_EN")],
    ]
    await update.message.reply_text(
        TEXTOS["ES"]["selecciona_idioma"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def callback_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]

    chat_id = query.message.chat_id
    user_data.setdefault(chat_id, {})["lang"] = lang
    loc = user_data[chat_id].get("location", "Órgiva")

    await query.message.edit_text(TEXTOS[lang]["bienvenido"].format(loc=loc))


async def cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data.setdefault(chat_id, {})["lang"] = "ES"  # default si no existe

    lang = user_data[chat_id]["lang"]

    kb = [[InlineKeyboardButton(txt, callback_data=f"loc_{val}")] for txt, val in LOCALIDADES_SELECTOR]
    kb.append([InlineKeyboardButton("Motril", callback_data="loc_Motril")])
    kb.append([InlineKeyboardButton("Almuñécar", callback_data="loc_Almuñécar")])
    kb.append([InlineKeyboardButton("Salobreña", callback_data="loc_Salobreña")])

    await update.message.reply_text(
        TEXTOS[lang]["cambiar"],
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def callback_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    loc = query.data.split("_", 1)[1]
    chat_id = query.message.chat_id
    user_data.setdefault(chat_id, {})["location"] = loc
    lang = user_data[chat_id].get("lang", "ES")

    await query.message.edit_text(
        f"✅ Cambiado a **{loc}**\n\n{TEXTOS[lang]['cambia_con']}",
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────
#  Inicio
# ────────────────────────────────────────────────
def main():
    logger.info("Iniciando bot...")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cambiar", cambiar))

    app.add_handler(CallbackQueryHandler(callback_lang, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(callback_loc, pattern="^loc_"))

    # Scheduler
    scheduler = AsyncIOScheduler()
    if MODO_PRUEBA:
        scheduler.add_job(job_send_weather, "interval", minutes=5, args=(app.context_types_context,))
    else:
        scheduler.add_job(job_send_weather, "cron", hour=8, minute=2, args=(app.context_types_context,))
        scheduler.add_job(job_send_weather, "cron", hour=20, minute=2, args=(app.context_types_context,))

    scheduler.start()

    logger.info(f"Bot listo | Modo prueba = {MODO_PRUEBA}")

    # ¡Aquí está el cambio clave para Railway!
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=0.5,
        timeout=10,
    )


if __name__ == "__main__":
    main()
