import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- Logging ----------------
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Configuración ----------------
TOKEN = "TU_BOT_TOKEN_AQUI"           # ← cambiar
ADMIN_CHAT_ID = "TU_CHAT_ID_AQUI"     # ← cambiar (chat donde recibes los mensajes)

# Modo prueba = True → cada ~5 min   /   Modo real = False → 8:00 y 20:00
MODO_PRUEBA = True                    # ← CAMBIAR A False para modo producción

# Localidades principales (las 6 + 3 que se muestran aparte)
PRINCIPALES = [
    "Órgiva",           # 0 - referencia para Bayacas, El Morreón, Los Tablones, Las Barreras
    "Lanjarón",
    "Pampaneira",
    "Bubión",
    "Capileira",
    "Trevélez",
]

EXTRAS = ["Motril", "Almuñécar", "Salobreña"]

# Mapeo para wttr.in (usamos Órgiva para los pueblos alpujarreños pequeños)
LOCATION_MAP = {
    "Órgiva": "Orgiva",
    "Lanjarón": "Lanjaron",
    "Pampaneira": "Orgiva",          # aproximamos a Órgiva
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

# Bandera + nombre para selector
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

# ---------------- Estado (por chat) ----------------
user_data = {}  # chat_id → {"lang": "ES", "location": "Órgiva"}

# ---------------- Idiomas ----------------
TEXTOS = {
    "ES": {
        "selecciona_idioma": "Selecciona idioma / Select language",
        "bienvenido": "¡Bienvenido! 🌤️\nTu localidad actual: {loc}\n\nPara cambiar población escribe:\n/cambiar\n\nPronto recibirás el tiempo automático.",
        "cambiar": "Selecciona tu localidad:",
        "extra": "\n\n──────────────\nOtras localidades populares:",
        "modo": "Modo actual: {modo}",
        "enviado": "✅ Mensaje de prueba enviado",
        "error_clima": "❌ No se pudo obtener el tiempo ahora",
        "cambia_con": "Para cambiar población escribe /cambiar y pulsa intro",
        "hora_puesta": "🌇 Puesta de sol hoy",
        "hora_salida": "🌅 Salida de sol mañana",
    },
    "EN": {
        "selecciona_idioma": "Select language / Selecciona idioma",
        "bienvenido": "Welcome! 🌤️\nCurrent location: {loc}\n\nTo change location type:\n/cambiar\n\nWeather updates coming soon.",
        "cambiar": "Choose your location:",
        "extra": "\n\n──────────────\nOther popular locations:",
        "modo": "Current mode: {modo}",
        "enviado": "✅ Test message sent",
        "error_clima": "❌ Could not fetch weather right now",
        "cambia_con": "To change location type /cambiar and press enter",
        "hora_puesta": "🌇 Sunset today",
        "hora_salida": "🌅 Sunrise tomorrow",
    },
    # Puedes añadir NL, DE, FR siguiendo el mismo patrón...
}

# Por simplicidad solo ES y EN completos. Puedes extenderlo.

# ---------------- Funciones clima ----------------
async def obtener_datos_tiempo(location: str):
    """Devuelve datos crudos de wttr.in"""
    loc = LOCATION_MAP.get(location, "Orgiva")
    url = f"https://wttr.in/{loc}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"Error obteniendo tiempo {loc} → {e}")
        return None


def extraer_info_tiempo(data, modo_real: bool = False):
    if not data:
        return "❌ No se pudo obtener información del tiempo"

    lines = []

    try:
        # Condición actual (más reciente posible)
        if "current_condition" in data and data["current_condition"]:
            curr = data["current_condition"][0]
        else:
            # Última hora disponible
            if data.get("weather") and data["weather"][0].get("hourly"):
                curr = data["weather"][0]["hourly"][-1]
            else:
                return "❌ Datos incompletos"

        temp = curr.get("temp_C", "—")
        feels = curr.get("FeelsLikeC", "—")
        uv   = curr.get("uvIndex", "—")
        rain = curr.get("chanceofrain", "—")

        lines.append(f"🌡️ {temp}°C  (sensación {feels}°C)")
        lines.append(f"☔ {rain}%  |  UV {uv}")

        # Mañana / Tarde (solo modo real o aproximado)
        if data.get("weather"):
            today = data["weather"][0]
            hourly = today.get("hourly", [])

            if len(hourly) >= 8:  # ~8-9h mañana, ~14-15h tarde
                manana = hourly[min(8, len(hourly)-1)]
                tarde  = hourly[min(14, len(hourly)-1)]

                lines.append(f"🌅 Mañana ≈ {manana.get('tempC','—')}°C  ({manana.get('chanceofrain','—')}% lluvia)")
                lines.append(f"🌇 Tarde  ≈ {tarde.get('tempC','—')}°C   ({tarde.get('chanceofrain','—')}% lluvia)")

        # Astronomia
        if data.get("weather"):
            astro = data["weather"][0].get("astronomy", [{}])[0]
            if modo_real:
                lines.append(f"{TEXTOS['ES']['hora_puesta']}: {astro.get('sunset','—')}")
            else:
                lines.append(f"{TEXTOS['ES']['hora_salida']}: {astro.get('sunrise','—')} (mañana)")

    except Exception as e:
        logger.error(f"Error parseando datos: {e}")
        return "❌ Error al procesar el tiempo"

    lines.append("")
    lines.append(TEXTOS["ES"]["cambia_con"])

    return "\n".join(lines)


# ---------------- Mensaje formateado ----------------
def crear_mensaje_clima(location: str, datos, lang: str = "ES", modo_real: bool = False):
    txt = extraer_info_tiempo(datos, modo_real)
    header = f"🌤️ **{location}**  {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    return header + txt


# ---------------- Envío programado ----------------
async def enviar_clima_programado(context: ContextTypes.DEFAULT_TYPE):
    chat_id = ADMIN_CHAT_ID
    if chat_id not in user_data:
        user_data[chat_id] = {"lang": "ES", "location": "Órgiva"}

    loc = user_data[chat_id]["location"]
    lang = user_data[chat_id]["lang"]

    # Obtenemos datos ~1 min antes de enviar → ya lo estamos haciendo aquí
    datos = await obtener_datos_tiempo(loc)
    if not datos:
        await context.bot.send_message(chat_id, TEXTOS[lang]["error_clima"])
        return

    texto = crear_mensaje_clima(loc, datos, lang, modo_real=not MODO_PRUEBA)
    await context.bot.send_message(chat_id, texto, parse_mode="Markdown")


# ---------------- Comandos y flujo ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("Español 🇪🇸", callback_data="lang_ES")],
        [InlineKeyboardButton("English 🇬🇧",  callback_data="lang_EN")],
        # Puedes añadir más: NL, DE, FR ...
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        TEXTOS["ES"]["selecciona_idioma"],
        reply_markup=reply_markup
    )


async def callback_idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        user_data[chat_id] = user_data.get(chat_id, {})
        user_data[chat_id]["lang"] = lang

        loc = user_data[chat_id].get("location", "Órgiva")

        await query.message.edit_text(
            TEXTOS[lang]["bienvenido"].format(loc=loc)
        )


async def cmd_cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"lang": "ES", "location": "Órgiva"}

    lang = user_data[chat_id]["lang"]

    keyboard = []
    for emoji_nombre, valor in LOCALIDADES_SELECTOR:
        keyboard.append([InlineKeyboardButton(emoji_nombre, callback_data=f"loc_{valor}")])

    keyboard.append([InlineKeyboardButton("Motril",      callback_data="loc_Motril")])
    keyboard.append([InlineKeyboardButton("Almuñécar",   callback_data="loc_Almuñécar")])
    keyboard.append([InlineKeyboardButton("Salobreña",   callback_data="loc_Salobreña")])

    await update.message.reply_text(
        TEXTOS[lang]["cambiar"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def callback_localidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data

    if data.startswith("loc_"):
        nueva_loc = data[4:]
        user_data[chat_id] = user_data.get(chat_id, {})
        user_data[chat_id]["location"] = nueva_loc

        lang = user_data[chat_id].get("lang", "ES")

        await query.message.edit_text(
            f"✅ Localidad cambiada a **{nueva_loc}**\n\n"
            f"{TEXTOS[lang]['cambia_con']}",
            parse_mode="Markdown"
        )


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía mensaje ahora mismo (útil para pruebas)"""
    await enviar_clima_programado(context)
    await update.message.reply_text(TEXTOS["ES"]["enviado"])


# ---------------- Main ----------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("cambiar", cmd_cambiar))
    app.add_handler(CommandHandler("test",    cmd_test))      # solo para pruebas

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_idioma,   pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(callback_localidad, pattern="^loc_"))

    # Scheduler
    scheduler = AsyncIOScheduler()

    if MODO_PRUEBA:
        scheduler.add_job(
            lambda: asyncio.create_task(enviar_clima_programado(app.context_types_context)),
            'interval',
            minutes=5
        )
    else:
        # 8:00 y 20:00 todos los días
        scheduler.add_job(
            lambda: asyncio.create_task(enviar_clima_programado(app.context_types_context)),
            'cron', hour=8, minute=2
        )
        scheduler.add_job(
            lambda: asyncio.create_task(enviar_clima_programado(app.context_types_context)),
            'cron', hour=20, minute=2
        )

    scheduler.start()

    logger.info("Bot iniciado. Modo prueba = %s", MODO_PRUEBA)

    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    asyncio.run(main())
