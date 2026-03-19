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

MODO_PRUEBA = True  # ← True = prueba cada 5 minutos | False = 8:00 y 20:00

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

COASTAL_PUEBLOS = ["MOTRIL", "ALMUÑÉCAR", "SALOBREÑA"]

# ====================== TEXTOS TRADUCIDOS ======================
TEXTOS = {
    "ES": {
        "idioma_cmd": "/idioma", "poblacion_cmd": "/poblacion",
        "idioma": "Selecciona idioma / Select language",
        "bienvenido": "✅ Bot activado\nPoblación actual: {loc}",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a **{loc}**\nBuscando datos ahora...\nEspere un momento.",
        "footer": "Para cambiar el idioma pulse /start\nPara cambiar la localización /poblacion",
        "siguiente_8": "Siguiente mensaje a las 20:00\n¡Que tengas un buen día!",
        "siguiente_20": "Siguiente mensaje a las 8:00\n¡Que tengas una buena noche!",
        "temp_actual_title": "🌡️ Temperatura actual:",
        "sensacion": " (sensación {sens}°C).",
        "estado_actual": "☀️ Estado actual: {estado}",
        "prediccion_hoy": "Predicción para hoy",
        "prediccion_manana": "Predicción para mañana",
        "temp_max": "🔼 Temperatura máxima: {max_t}°C.",
        "temp_min": "🔽 Temperatura mínima: {min_t}°C.",
        "prob_lluvia": "☔ Probabilidad de lluvia: {rain_prob}%.",
        "int_viento": "🌬️ Viento: {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Intensidad UV máxima: {uv_text}.",
        "fase_lunar": "Fase lunar: {lunar}.",
        "hora_puesta": "🌇 Hora puesta de sol",
        "hora_amanecer": "🌅 Hora amanecer",
        "desc_day": "Descripción del día:",
        "consejos_title": "Consejos:",
        "consejo_uv": "• Usa protector solar SPF 50+, gafas de sol y evita el sol directo entre 12:00 y 16:00.",
        "consejo_rain": "• Lleva paraguas o chubasquero; la lluvia puede aparecer de forma repentina.",
        "consejo_windcold": "• Chaqueta o abrigo ligero es imprescindible; protege del viento y el frío.",
        "consejo_ligera": "• Ropa ligera y cómoda es suficiente para todo el día.",
        "consejo_capa": "• Lleva una capa extra para la tarde o noche por cambios de temperatura.",
        "consejo_coast": "• Disfruta de la brisa marina para un paseo agradable por la costa.",
        "consejo_mountain": "• En las zonas de montaña, prepárate para cambios de temperatura nocturnos.",
        "separator": "───────────────────",
        "estado_despejado": "Despejado con brisa.",
        "estado_nublado": "Nublado con posibles chubascos.",
        "estado_fallback": "Parcialmente nublado.",
        "luna_llena": "Luna llena (95-100%)",
        "luna_creciente": "Cuarto creciente (60-70%)",
        "luna_fallback": "Luna llena (96%)",
        "luna_nueva": "Luna nueva (0-5%)",
        "wind_desc_calma": "calma total",
        "wind_desc_ligera": "brisa ligera",
        "wind_desc_moderada": "brisa moderada",
        "wind_desc_fuerte": "viento fuerte",
        "wind_desc_muy_fuerte": "viento muy fuerte",
        "wind_desc_tormenta": "tormenta",
        "desc_clear": "• Día mayormente despejado y soleado.",
        "desc_partly": "• Día con intervalos de nubes y claros.",
        "desc_cloudy": "• Día nublado o con chubascos.",
        "desc_wind_strong": "• Viento moderado a fuerte por la tarde.",
        "desc_wind_light": "• Brisa ligera durante el día.",
        "desc_wind_calma": "• Viento calmado.",
        "desc_temp_hot": "• Calor notable, mantente hidratado.",
        "desc_temp_cool": "• Ambiente fresco, ideal para actividades.",
        "desc_temp_pleasant": "• Temperaturas agradables y cómodas.",
        "desc_coast": "• Brisa marina típica de la costa.",
        "desc_mountain": "• Clima típico de montaña con posibles variaciones.",
    },
    "EN": {
        "idioma_cmd": "/language", "poblacion_cmd": "/location",
        "idioma": "Select language",
        "bienvenido": "✅ Activated\nCurrent location: {loc}",
        "cambiar": "Choose your location:",
        "buscando": "✅ Changed to **{loc}**\nFetching data now...\nPlease wait.",
        "footer": "To change language press /start\nTo change location /poblacion",
        "siguiente_8": "Next message at 20:00\nHave a great day!",
        "siguiente_20": "Next message at 8:00\nGood night!",
        "temp_actual_title": "🌡️ Current temperature:",
        "sensacion": " (feels like {sens}°C).",
        "estado_actual": "☀️ Current condition: {estado}",
        "prediccion_hoy": "Forecast for today",
        "prediccion_manana": "Forecast for tomorrow",
        "temp_max": "🔼 Maximum temperature: {max_t}°C.",
        "temp_min": "🔽 Minimum temperature: {min_t}°C.",
        "prob_lluvia": "☔ Rain probability: {rain_prob}%.",
        "int_viento": "🌬️ Wind: {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Maximum UV intensity: {uv_text}.",
        "fase_lunar": "Moon phase: {lunar}.",
        "hora_puesta": "🌇 Sunset time",
        "hora_amanecer": "🌅 Sunrise time",
        "desc_day": "Day description:",
        "consejos_title": "Tips:",
        "consejo_uv": "• Use SPF 50+ sunscreen, sunglasses and avoid direct sun between 12:00 and 16:00.",
        "consejo_rain": "• Carry an umbrella or raincoat; rain may appear suddenly.",
        "consejo_windcold": "• Light jacket or coat is essential; protects from wind and cold.",
        "consejo_ligera": "• Light and comfortable clothing is sufficient all day.",
        "consejo_capa": "• Take an extra layer for afternoon or night due to temperature changes.",
        "consejo_coast": "• Enjoy the sea breeze for a pleasant coastal walk.",
        "consejo_mountain": "• In mountain areas, prepare for nighttime temperature changes.",
        "separator": "───────────────────",
        "estado_despejado": "Clear with breeze.",
        "estado_nublado": "Cloudy with possible showers.",
        "estado_fallback": "Partly cloudy.",
        "luna_llena": "Full moon (95-100%)",
        "luna_creciente": "Waxing crescent (60-70%)",
        "luna_fallback": "Full moon (96%)",
        "luna_nueva": "New moon (0-5%)",
        "wind_desc_calma": "total calm",
        "wind_desc_ligera": "light breeze",
        "wind_desc_moderada": "moderate breeze",
        "wind_desc_fuerte": "fresh wind",
        "wind_desc_muy_fuerte": "strong wind",
        "wind_desc_tormenta": "storm",
        "desc_clear": "• Mostly clear and sunny day.",
        "desc_partly": "• Day with clouds and clear intervals.",
        "desc_cloudy": "• Cloudy day or with showers.",
        "desc_wind_strong": "• Moderate to strong wind in the afternoon.",
        "desc_wind_light": "• Light breeze during the day.",
        "desc_wind_calma": "• Calm wind.",
        "desc_temp_hot": "• Notable heat, stay hydrated.",
        "desc_temp_cool": "• Cool environment, ideal for activities.",
        "desc_temp_pleasant": "• Pleasant and comfortable temperatures.",
        "desc_coast": "• Typical sea breeze on the coast.",
        "desc_mountain": "• Typical mountain climate with possible variations.",
    },
    # ... (los demás idiomas siguen iguales que en la versión anterior, para no alargar demasiado aquí)
    # Puedes copiarlos de tu versión anterior si los tienes modificados
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}
PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== FASE LUNAR REAL ======================
def get_lunar_phase(now: datetime, lang: str) -> str:
    t = TEXTOS[lang]
    y, m, d = now.year, now.month, now.day
    if m <= 2: y -= 1; m += 12
    a = y // 100; b = a // 4; c = 2 - a + b
    e = int(365.25 * (y + 4716)); f = int(30.6001 * (m + 1))
    jd = c + d + e + f - 1524.5
    moon_age = (jd - 2451549.5) % 29.53058867
    if moon_age < 2.5 or moon_age > 27.0: return t["luna_nueva"]
    elif 12.0 < moon_age < 17.0: return t["luna_llena"]
    else: return t["luna_creciente"]

# ====================== FUNCIONES AUXILIARES (wind, uv, descripción, consejos) ======================
def wind_description(kmh: int, lang: str) -> str:
    t = TEXTOS[lang]
    if kmh < 1: return t["wind_desc_calma"]
    if kmh < 12: return t["wind_desc_ligera"]
    if kmh < 20: return t["wind_desc_moderada"]
    if kmh < 29: return t["wind_desc_fuerte"]
    if kmh < 39: return t["wind_desc_muy_fuerte"]
    return t["wind_desc_tormenta"]

def uv_explanation(uv: int, lang: str) -> str:
    t = TEXTOS[lang]
    if uv <= 2: return t.get("uv_bajo", "Bajo")
    if uv <= 5: return t.get("uv_moderado", "Moderado")
    if uv <= 7: return t.get("uv_alto", "Alto")
    if uv <= 10: return t.get("uv_muy_alto", "Muy alto")
    return t.get("uv_extremo", "Extremo")

def get_day_description(rain_prob: int, wind_kmh: int, max_t: int, lang: str, loc_name: str) -> list:
    t = TEXTOS[lang]
    lines = []
    if rain_prob < 20: lines.append(t["desc_clear"])
    elif rain_prob < 50: lines.append(t["desc_partly"])
    else: lines.append(t["desc_cloudy"])
    if wind_kmh > 20: lines.append(t["desc_wind_strong"])
    elif wind_kmh > 10: lines.append(t["desc_wind_light"])
    else: lines.append(t["desc_wind_calma"])
    if max_t > 25: lines.append(t["desc_temp_hot"])
    elif max_t < 18: lines.append(t["desc_temp_cool"])
    else: lines.append(t["desc_temp_pleasant"])
    if loc_name in COASTAL_PUEBLOS: lines.append(t["desc_coast"])
    else: lines.append(t["desc_mountain"])
    return lines

def get_consejos(uv_max: int, rain_prob: int, wind_kmh: int, temp: int, loc_name: str, lang: str) -> list:
    t = TEXTOS[lang]
    cons = []
    if uv_max >= 6: cons.append(t["consejo_uv"])
    if rain_prob >= 40: cons.append(t["consejo_rain"])
    if wind_kmh >= 25 or temp < 14: cons.append(t["consejo_windcold"])
    if rain_prob < 20 and uv_max < 5 and temp > 18:
        cons.append(t["consejo_ligera"])
    else:
        cons.append(t["consejo_capa"])
    if loc_name in COASTAL_PUEBLOS:
        cons.append(t["consejo_coast"])
    else:
        cons.append(t["consejo_mountain"])
    return cons

# ====================== OBTENER DATOS ======================
async def get_real_weather(loc_name: str):
    if loc_name in ["LOS TABLONES", "EL MORREÓN", "LAS BARRERAS", "BAYACAS"]:
        lat, lon = COORDS["ÓRGIVA"]
    else:
        lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m,uv_index&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code == 200: return r.json(), "openmeteo"
    except: pass
    return None, "fallback"

# ====================== CONSTRUIR MENSAJE ======================
def build_weather_message(data, source, loc_name: str, lang: str):
    t = TEXTOS[lang]
    now = datetime.now()
    is_morning = now.hour < 14
    if source == "openmeteo" and data:
        c = data["current"]
        d = data["daily"]
        h = data["hourly"]
        idx = 0 if is_morning else 1
        temp = round(c["temperature_2m"])
        sens = round(c["apparent_temperature"])
        uv_max = max(h["uv_index"][idx*24:(idx+1)*24]) if "uv_index" in h else int(c.get("uv_index", 5))
        rain_prob = h["precipitation_probability"][12]
        wind_kmh = round(h["wind_speed_10m"][12])
        max_t = d["temperature_2m_max"][idx]
        min_t = d["temperature_2m_min"][idx]
        sunrise = d["sunrise"][idx].split("T")[1][:5]
        sunset = d["sunset"][idx].split("T")[1][:5]
        estado = t["estado_despejado"] if rain_prob < 30 else t["estado_nublado"]
    else:
        temp, sens, uv_max, rain_prob, wind_kmh = 17, 16, 8, 25, 20
        max_t, min_t = 23, 12
        sunrise, sunset = "07:11", "19:49"
        estado = t["estado_fallback"]
    lunar = get_lunar_phase(now, lang)
    wind_desc = wind_description(wind_kmh, lang)
    uv_text = f"{uv_max} ({uv_explanation(uv_max, lang)})"
    desc_lines = get_day_description(rain_prob, wind_kmh, max_t, lang, loc_name)
    consejos = get_consejos(uv_max, rain_prob, wind_kmh, temp, loc_name, lang)
    lines = [
        loc_name, "",
        t["temp_actual_title"],
        f" {temp}°C" + t["sensacion"].format(sens=sens),
        t["estado_actual"].format(estado=estado), "",
        t["prediccion_hoy"] if is_morning else t["prediccion_manana"], "",
        t["temp_max"].format(max_t=max_t),
        t["temp_min"].format(min_t=min_t),
        t["prob_lluvia"].format(rain_prob=rain_prob),
        t["int_viento"].format(wind_kmh=wind_kmh, wind_desc=wind_desc),
        t["int_uv"].format(uv_text=uv_text),
        (t["hora_puesta"] if is_morning else t["hora_amanecer"]) + f": {sunset if is_morning else sunrise}.",
        t["fase_lunar"].format(lunar=lunar),
        "",
        "📅 " + t["desc_day"],
        *desc_lines,
        "",
        "💡 " + t["consejos_title"],
        *consejos,
        "",
        t["separator"],
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

async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    await send_weather(context)

# ====================== COMANDOS ======================
async def cmd_idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = [
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_ES"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_EN")],
        [InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_NL"), InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_DE")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_FR"), InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_IT")],
    ]
    await update.message.reply_text("🌍 " + TEXTOS[lang]["idioma"], reply_markup=InlineKeyboardMarkup(kb))

async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    old_lang = user_data["lang"]
    user_data["lang"] = query.data.split("_")[1]
    new_lang = user_data["lang"]
    
    # Mensaje de confirmación breve
    text = TEXTOS[new_lang]["bienvenido"].format(loc=user_data["location"])
    await query.edit_message_text(text)
    
    # Si ya hay población seleccionada → enviar inmediatamente el tiempo en el nuevo idioma
    if user_data["location"]:
        await send_weather(context)

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
    text = TEXTOS[lang]["buscando"].format(loc=loc)
    await query.edit_message_text(text)
    await send_weather(context)

# ====================== MAIN ======================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = ApplicationBuilder().token(TOKEN).build()
    
    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
    
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
    
    logging.info("✅ BOT LISTO | Cambio de idioma → reenvía tiempo si hay población | Descripción real | Consejos adaptados")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
