import logging
import os
from datetime import datetime, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import httpx

# ────────────────────────────────────────────────
# Logging (visible en Railway / Railway logs)
# ────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# Configuración básica
# ────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.critical("No se encontró BOT_TOKEN en las variables de entorno")
    raise ValueError("Falta la variable BOT_TOKEN en Railway → configúrala")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Opcional: pon tu chat_id aquí también como variable
if not ADMIN_CHAT_ID:
    ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"       # ← cámbialo si no usas variable
    logger.warning("Usando ADMIN_CHAT_ID hardcodeado → mejor ponlo como variable de entorno")

MODO_PRUEBA = True  # Cambia a False para modo real (8:02 y 20:02)

# ────────────────────────────────────────────────
# Localidades y mapeo para wttr.in
# ────────────────────────────────────────────────
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

# Estado (como es solo para ti → global simple)
user_data = {"lang": "ES", "location": "Órgiva"}

TEXTOS = {
    "ES": {
        "selecciona_idioma": "Selecciona idioma / Select language",
        "bienvenido": "¡Bienvenido! 🌤️\nPoblación actual: **{loc}**\n\nPara cambiar: /cambiar",
        "cambiar": "Elige localidad:",
        "cambia_con": "Para cambiar población escribe /cambiar",
        "error_clima": "❌ No se pudo obtener el tiempo ahora",
        "puesta": "🌇 Puesta de sol hoy",
        "salida": "🌅 Salida de sol mañana",
    },
    "EN": {
        "selecciona_idioma": "Select language / Selecciona idioma",
        "bienvenido": "Welcome! 🌤️\nCurrent location: **{loc}**\n\nTo change: /cambiar",
        "cambiar": "Choose location:",
        "cambia_con": "To change location: /cambiar",
        "error_clima": "❌ Could not get weather",
        "puesta": "🌇 Sunset today",
        "salida": "🌅 Sunrise tomorrow",
    }
}

# ────────────────────────────────────────────────
# Obtener datos del tiempo
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
        logger.error(f"Error al obtener tiempo para {loc}: {e}")
        return None


def format_weather_message(data, loc_name: str, lang: str, real_mode: bool):
    if not data:
        return TEXTOS[lang]["error_clima"]

    lines = [f"🌤️ **{loc_name}**   {datetime.now().strftime('%d/%m/%Y %H:%M')}"]

    try:
        # Condición actual (preferimos current si existe, sino última hora)
        curr = data.get("current_condition", [{}])[0]
        if not curr or "temp_C" not in curr:
            curr = data["weather"][0]["hourly"][-1]

        temp = curr.get("temp_C", "—")
        feels = curr.get("FeelsLikeC", "—")
        rain = curr.get("chanceofrain", "—")
        uv = curr.get("uvIndex", "—")

        lines += [
            f"🌡️ {temp}°C   (sensación {feels}°C)",
            f"☔ {rain}%   UV {uv}",
        ]

        # Mañana y tarde (aprox 8h y 14h)
        if data.get("weather"):
            hourly = data["weather"][0].get("hourly", [])
            if len(hourly) > 14:
                ma = hourly[8]
                ta = hourly[14]
                lines += [
                    f"🌅 Mañana ≈ {ma.get('tempC','—')}°C  ({ma.get('chanceofrain','—')}% lluvia)",
                    f"🌇 Tarde  ≈ {ta.get('tempC','—')}°C   ({ta.get('chanceofrain','—')}% lluvia)",
                ]

            # Sol
            astro = data["weather"][0].get("astronomy", [{}])[0]
            key = "puesta" if real_mode else "salida"
            val = astro.get("sunset" if real_mode else "sunrise", "—")
            lines.append(f"{TEXTOS[lang][key]}: {val}")

    except Exception as e:
        logger.error(f"Error formateando mensaje: {e}")
        lines.append("⚠️ Datos parciales o error de parseo")

    lines += ["", TEXTOS[lang]["cambia_con"]]

    return "\n".join(lines)


# ────────────────────────────────────────────────
# Job programado
# ────────────────────────────────────────────────
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]

    data = await fetch_weather(loc)
    text = format_weather_message(data, loc, lang, real_mode=not MODO_PRUEBA)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        logger.info(f"Mensaje enviado correctamente a {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")


# ────────────────────────────────────────────────
# Comandos y callbacks
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


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]
    user_data["lang"] = lang
    loc = user_data["location"]

    await query.edit_message_text(
        TEXTOS[lang]["bienvenido"].format(loc=loc),
        parse_mode="Markdown"
    )


async def cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = [[InlineKeyboardButton(label, callback_data=f"loc_{value}")] for label, value in LOCALIDADES_SELECTOR]

    kb += [
        [InlineKeyboardButton("Motril", callback_data="loc_Motril")],
        [InlineKeyboardButton("Almuñécar", callback_data="loc_Almuñécar")],
        [InlineKeyboardButton("Salobreña", callback_data="loc_Salobreña")],
    ]

    await update.message.reply_text(
        TEXTOS[lang]["cambiar"],
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def loc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, new_loc = query.data.split("_", 1)
    user_data["location"] = new_loc
    lang = user_data["lang"]

    await query.edit_message_text(
        f"✅ Cambiado a **{new_loc}**\n\n{TEXTOS[lang]['cambia_con']}",
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────
# Inicio del bot
# ────────────────────────────────────────────────
def main():
    logger.info("Iniciando bot...")

    application = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cambiar", cambiar))

    application.add_handler(CallbackQueryHandler(lang_callback, pattern=r"^lang_"))
    application.add_handler(CallbackQueryHandler(loc_callback, pattern=r"^loc_"))

    # JobQueue
    jq = application.job_queue

    if MODO_PRUEBA:
        jq.run_repeating(send_weather, interval=300, first=10)   # cada 5 min
    else:
        jq.run_daily(send_weather, time=time(hour=8, minute=2))
        jq.run_daily(send_weather, time=time(hour=20, minute=2))

    logger.info(f"Bot iniciado | Modo prueba = {MODO_PRUEBA} | Jobs configurados")

    # Iniciar polling
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=0.5,
        timeout=10,
    )


if __name__ == "__main__":
    main()
