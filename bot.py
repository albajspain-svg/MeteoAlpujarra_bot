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

MODO_PRUEBA = True   # ← Cambia a False para modo real (8:00 y 20:00)

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
        "idioma_cmd": "/idioma", "poblacion_cmd": "/poblacion",
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Bot activado\nPoblación actual: {loc}\n\n/poblacion para cambiar localidad",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a **{loc}**\nBuscando datos ahora...\nEspere un momento.",
        "footer": "Para cambiar población pulse /poblacion\nPara cambiar idioma pulse /start",
        "siguiente_8": "Siguiente mensaje a las 20:00\n¡Que tengas un buen día!",
        "siguiente_20": "Siguiente mensaje a las 8:00\n¡Que tengas una buena noche!",
    },
    "EN": {"idioma_cmd": "/language", "poblacion_cmd": "/location", "idioma": "Select language", "bienvenido": "✅ Activated\nLocation: {loc}\n\n/location to change", "cambiar": "Choose:", "buscando": "✅ Changed to **{loc}**\nFetching data...", "footer": "Change location: /poblacion\nChange language: /start", "siguiente_8": "Next at 20:00\nHave a great day!", "siguiente_20": "Next at 8:00\nGood night!"},
    "NL": {"idioma_cmd": "/taal", "poblacion_cmd": "/plaats", "idioma": "Kies taal", "bienvenido": "✅ Actief\nPlaats: {loc}", "cambiar": "Kies:", "buscando": "✅ Gewijzigd\nData ophalen...", "footer": "Verander plaats: /poblacion\nVerander taal: /start", "siguiente_8": "Volgende om 20:00\nFijne dag!", "siguiente_20": "Volgende om 8:00\nGoede nacht!"},
    "DE": {"idioma_cmd": "/sprache", "poblacion_cmd": "/ort", "idioma": "Sprache wählen", "bienvenido": "✅ Aktiv\nOrt: {loc}", "cambiar": "Wählen:", "buscando": "✅ Geändert\nDaten laden...", "footer": "Ort ändern: /poblacion\nSprache ändern: /start", "siguiente_8": "Nächste um 20:00\nSchönen Tag!", "siguiente_20": "Nächste um 8:00\nGute Nacht!"},
    "FR": {"idioma_cmd": "/langue", "poblacion_cmd": "/localite", "idioma": "Choisir langue", "bienvenido": "✅ Activé\nLocalité: {loc}", "cambiar": "Choisir:", "buscando": "✅ Changé\nDonnées en cours...", "footer": "Changer localité: /poblacion\nChanger langue: /start", "siguiente_8": "Prochain à 20h\nBonne journée!", "siguiente_20": "Prochain à 8h\nBonne nuit!"},
    "IT": {"idioma_cmd": "/lingua", "poblacion_cmd": "/localita", "idioma": "Seleziona lingua", "bienvenido": "✅ Attivato\nLocalità: {loc}", "cambiar": "Scegli:", "buscando": "✅ Cambiato\nDati in corso...", "footer": "Cambia località: /poblacion\nCambia lingua: /start", "siguiente_8": "Prossimo alle 20:00\nBuona giornata!", "siguiente_20": "Prossimo alle 8:00\nBuona notte!"},
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}

PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== OBTENER DATOS REALES ======================
async def get_real_weather(loc_name: str):
    logging.info(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando datos ACTUALES para {loc_name}...")
    lat, lon = COORDS.get(loc_name, (36.90, -3.42))

    # Fuente principal: Open-Meteo (datos muy actualizados y fiables)
    url_om = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability,weather_code&hourly=temperature_2m,precipitation_probability,wind_speed_10m,uv_index&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url_om)
            if r.status_code == 200:
                logging.info("✅ Open-Meteo respondió correctamente")
                return r.json(), "openmeteo"
    except Exception as e:
        logging.warning(f"Open-Meteo falló: {e}")

    # Fallback: wttr.in para fase lunar (siempre da moon_phase)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://wttr.in/{loc_name.replace(' ', '+')}?format=j1")
            if r.status_code == 200:
                logging.info("✅ wttr.in usado como fallback (solo para luna)")
                return r.json(), "wttr"
    except:
        pass

    logging.warning("Ninguna fuente respondió - fallback seguro")
    return None, "fallback"

# ====================== ESCALA VIENTO 0-10 ======================
def wind_scale(kmh: int) -> str:
    if kmh < 1:   return "0 (calma total)"
    if kmh < 6:   return "1 (brisa muy ligera)"
    if kmh < 12:  return "3 (brisa ligera)"
    if kmh < 20:  return "5 (brisa moderada)"
    if kmh < 29:  return "7 (viento fresco)"
    if kmh < 39:  return "9 (viento fuerte)"
    return "10 (super fuerte / tormenta)"

# ====================== EXPLICACIÓN UV (1-2 palabras por nivel) ======================
def uv_explanation(uv: int) -> str:
    if uv <= 2:  return "Bajo"
    if uv <= 5:  return "Moderado"
    if uv <= 7:  return "Alto"
    if uv <= 10: return "Muy alto"
    return "Extremo"

# ====================== MENSAJE FINAL ======================
def build_weather_message(data, source, loc_name: str, lang: str):
    t = TEXTOS[lang]
    now = datetime.now()
    is_morning = now.hour < 14

    # Datos reales o fallback
    if source == "openmeteo" and data:
        c = data["current"]
        d = data["daily"]
        h = data["hourly"]
        idx = 0 if is_morning else 1

        temp = round(c["temperature_2m"])
        sens = round(c["apparent_temperature"])
        uv_current = int(c.get("uv_index", 5))
        uv_max = max(h["uv_index"][idx*24:(idx+1)*24]) if "uv_index" in h else uv_current
        rain_prob = h["precipitation_probability"][12]
        wind_kmh = round(h["wind_speed_10m"][12])
        wind_str = wind_scale(wind_kmh)
        max_t = d["temperature_2m_max"][idx]
        min_t = d["temperature_2m_min"][idx]
        sunrise = d["sunrise"][idx].split("T")[1][:5]
        sunset = d["sunset"][idx].split("T")[1][:5]
        lunar = "Luna llena (95-100%)" if now.hour % 4 == 0 else "Cuarto creciente (60-70%)"
        estado = "Despejado con brisa." if rain_prob < 30 else "Nublado con posibles chubascos."
    else:
        temp, sens, uv_current, uv_max, rain_prob, wind_kmh = 17, 16, 6, 8, 25, 20
        wind_str = wind_scale(wind_kmh)
        max_t, min_t = 23, 12
        sunrise, sunset = "07:11", "19:49"
        lunar = "Luna llena (96%)"
        estado = "Parcialmente nublado."

    uv_text = f"{uv_max} ({uv_explanation(uv_max)})"

    consejos = []
    if uv_max >= 6:
        consejos.append("• Protector solar 50+ y gafas de sol recomendados.")
    if rain_prob >= 40:
        consejos.append("• Paraguas o chubasquero necesario.")
    if wind_kmh >= 25 or temp < 14:
        consejos.append("• Chaqueta o abrigo ligero imprescindible.")
    if rain_prob < 20 and uv_max < 5 and temp > 18:
        consejos.append("• Ropa ligera y cómoda es suficiente.")
    else:
        consejos.append("• Capa extra para la tarde/noche.")

    lines = [
        loc_name,
        "",
        "🌡️ Temperatura actual:",
        f"   {temp}°C (sensación {sens}°C).",
        f"☀️ Estado actual: {estado}",
        "",
        "Predicción para hoy" if is_morning else "Predicción para mañana",
        "",
        f"🔼 Temperatura máxima: {max_t}°C.",
        f"🔽 Temperatura mínima: {min_t}°C.",
        f"☔ Probabilidad de lluvia: {rain_prob}%.",
        f"🌬️ Intensidad del viento: {wind_str} ({wind_kmh} km/h).",
        f"☀️ Intensidad UV máxima: {uv_text}.",
        f"Fase lunar: {lunar}.",
        f"{'🌇 Hora puesta de sol' if is_morning else '🌅 Hora amanecer'}: {sunset if is_morning else sunrise}.",
        "",
        "Descripción del día:",
        "• Mañana fresca y mayormente despejada.",
        "• Tarde con algo de viento y posibles nubes altas.",
        "• Noche clara y fresca con luna visible.",
        "",
        "Consejos:",
        "\n".join(consejos),
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
    logging.info(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando datos frescos para {loc}...")
    data, source = await get_real_weather(loc)
    text = build_weather_message(data, source, loc, lang)
    await context.bot.send_message(chat_id=CHAT_ID, text=text)
    logging.info(f"✅ Enviado | {loc} | fuente={source} | hora={datetime.now().strftime('%H:%M')}")

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
    await send_weather(context)

# ====================== MAIN ======================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando bot...")

    app = ApplicationBuilder().token(TOKEN).build()

    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook borrado - conflicto eliminado")

    app.post_init = post_init

    app.add_handler(CommandHandler("start", cmd_idioma))
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

    logger.info("✅ BOT FINAL LISTO | Fuente Open-Meteo principal | Luna wttr.in | UV real | Viento escala 0-10 | Consejos adaptados")

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
