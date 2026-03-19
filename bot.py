import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import httpx

# Logging (muy visible en Railway)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# Configuración
# ────────────────────────────────────────────────
TOKEN = "TU_BOT_TOKEN_AQUI"           # ← CAMBIAR
ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"     # ← CAMBIAR (tu propio chat ID)

MODO_PRUEBA = True                    # Cambia a False para 8:02 y 20:02

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

# Estado simple (solo un usuario → ADMIN_CHAT_ID)
user_data = {"lang": "ES", "location": "Órgiva"}  # global para simplificar

TEXTOS = {
    "ES": {
        "selecciona_idioma": "Selecciona idioma / Select language",
        "bienvenido": "¡Bienvenido! 🌤️\nPoblación actual: {loc}\n\n/cambiar → cambiar localidad",
        "cambiar": "Elige tu localidad:",
        "cambia_con": "Para cambiar población escribe /cambiar",
        "error_clima": "❌ No se pudo obtener el tiempo ahora",
        "puesta": "🌇 Puesta de sol hoy",
        "salida": "🌅 Salida de sol mañana",
    },
    "EN": {
        "selecciona_idioma": "Select language / Selecciona idioma",
        "bienvenido": "Welcome! 🌤️\nCurrent location: {loc}\n\n/cambiar to change",
        "cambiar": "Choose your location:",
        "cambia_con": "To change location: /cambiar",
        "error_clima": "❌ Could not fetch weather",
        "puesta": "🌇 Sunset today",
        "salida": "🌅 Sunrise tomorrow",
    }
}

# ────────────────────────────────────────────────
# Obtener y formatear tiempo
# ────────────────────────────────────────────────
async def fetch_weather(loc_name: str):
    loc = LOCATION_MAP.get(loc_name, "Orgiva")
    url = f"https://wttr.in/{loc}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"Error fetching {loc}: {e}")
        return None


def format_message(data, loc_name: str, lang: str, real_mode: bool):
    if not data:
        return TEXTOS[lang]["error_clima"]

    lines = [f"🌤️ **{loc_name}**  {datetime.now().strftime('%d/%m/%Y %H:%M')}"]

    try:
        curr = data.get("current_condition", [{}])[0] or data["weather"][0]["hourly"][-1]

        temp = curr.get("temp_C", "—")
        feels = curr.get("FeelsLikeC", "—")
        rain = curr.get("chanceofrain", "—")
        uv = curr.get("uvIndex", "—")

        lines += [
            f"🌡️ {temp}°C  (sensación {feels}°C)",
            f"☔ {rain}%   UV {uv}",
        ]

        if data.get("weather"):
            hourly = data["weather"][0].get("hourly", [])
            if len(hourly) > 14:
                ma = hourly[8]
                ta = hourly[14]
                lines += [
                    f"🌅 Mañana ≈ {ma.get('tempC','—')}°C ({ma.get('chanceofrain','—')}% lluvia)",
                    f"🌇 Tarde  ≈ {ta.get('tempC','—')}°C  ({ta.get('chanceofrain','—')}% lluvia)",
                ]

            astro = data["weather"][0].get("astronomy", [{}])[0]
            key = "puesta" if real_mode else "salida"
            val = astro.get("sunset" if real_mode else "sunrise", "—")
            lines.append(f"{TEXTOS[lang][key]}: {val}")

    except Exception as e:
        logger.error(f"Parse error: {e}")
        lines.append("⚠️ Datos parciales")

    lines += ["", TEXTOS[lang]["cambia_con"]]

    return "\n".join(lines)


# ────────────────────────────────────────────────
# Job que envía el mensaje
# ────────────────────────────────────────────────
async def send_weather_job(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]

    data = await fetch_weather(loc)
    if not data:
        await context.bot.send_message(ADMIN_CHAT_ID, TEXTOS[lang]["error_clima"])
        return

    text = format_message(data, loc, lang, real_mode=not MODO_PRUEBA)
    await context.bot.send_message(ADMIN_CHAT_ID, text, parse_mode="Markdown")
    logger.info(f"Mensaje enviado a {ADMIN_CHAT_ID} para {loc}")


# ────────────────────────────────────────────────
# Handlers
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("Español 🇪🇸", callback_data="lang_ES")],
        [InlineKeyboardButton("English  🇬🇧", callback_data="lang_EN")],
    ]
    await update.message.reply_text(
        TEXTOS["ES"]["selecciona_idioma"],
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def callback_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]
    user_data["lang"] = lang
    loc = user_data["location"]

    await query.edit_message_text(TEXTOS[lang]["bienvenido"].format(loc=loc))


async def cmd_cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = []
    for label, value in LOCALIDADES_SELECTOR:
        kb.append([InlineKeyboardButton(label, callback_data=f"loc_{value}")])

    kb += [
        [InlineKeyboardButton("Motril", callback_data="loc_Motril")],
        [InlineKeyboardButton("Almuñécar", callback_data="loc_Almuñécar")],
        [InlineKeyboardButton("Salobreña", callback_data="loc_Salobreña")],
    ]

    await update.message.reply_text(
        TEXTOS[lang]["cambiar"],
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def callback_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, new_loc = query.data.split("_", 1)
    user_data["location"] = new_loc
    lang = user_data["lang"]

    await query.edit_message_text(
        f"✅ Localidad cambiada a **{new_loc}**\n\n{TEXTOS[lang]['cambia_con']}",
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────
# Inicio
# ────────────────────────────────────────────────
def main():
    logger.info("Iniciando bot...")

    application = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cambiar", cmd_cambiar))

    application.add_handler(CallbackQueryHandler(callback_lang, pattern=r"^lang_"))
    application.add_handler(CallbackQueryHandler(callback_loc, pattern=r"^loc_"))

    # ── JobQueue (la forma oficial y recomendada) ──
    job_queue = application.job_queue

    if MODO_PRUEBA:
        job_queue.run_repeating(
            callback=send_weather_job,
            interval=300,          # 5 minutos
            first=10               # empieza después de 10 segundos
        )
    else:
        job_queue.run_daily(
            callback=send_weather_job,
            time=datetime.time(hour=8, minute=2)
        )
        job_queue.run_daily(
            callback=send_weather_job,
            time=datetime.time(hour=20, minute=2)
        )

    logger.info(f"Bot iniciado | Modo prueba = {MODO_PRUEBA} | Jobs programados")

    # Ejecuta polling (bloqueante)
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=0.5,
        timeout=10,
    )


if __name__ == "__main__":
    main()
