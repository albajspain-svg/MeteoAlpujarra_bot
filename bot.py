import os
import json
import logging
from datetime import time
import requests
import pytz
from math import sqrt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
DB_FILE = "users.json"

# Cambia a False cuando quieras el horario real
TEST_MODE = True

chat_info = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# Solo pueblos confirmados que devuelven datos en Open-Meteo
TOWN_COORDS = {
    "Órgiva": (36.9026, -3.4238),
    "Lanjarón": (36.9185, -3.4818),
    "Pampaneira": (36.9402, -3.3610),
    "Bubión": (36.9500, -3.3550),
    "Capileira": (36.9615, -3.3586),
    "Trevélez": (37.0004, -3.2655),
    "Soportújar": (36.9286, -3.4054),
    "Cáñar": (36.9268, -3.4281),
    "Carataunas": (36.9220, -3.4083),
    "Pórtugos": (36.9419, -3.3107),
    "Busquístar": (36.9380, -3.2944),
    "Pitres": (36.9300, -3.3200),
    "Bérchules": (36.9768, -3.1907),
    "Almegíjar": (36.9026, -3.3012),
    "Cádiar": (36.9459, -3.1802),
    "Válor": (36.9962, -3.0829),
    "Yegen": (36.9810, -3.1190),
}

TOWNS = list(TOWN_COORDS.keys())

TEXTS = {
    "es": {
        "welcome": "🌦️ MeteoAlpujarra\nElige idioma / Select language",
        "select": "Elige tu pueblo:",
        "ok": "✅ Activado para {}",
        "city": "Escribe /ciudad Nombre del pueblo",
        "morning": "☀️ Mañana",
        "afternoon": "🌇 Tarde",
        "uv_low": "UV bajo 🌤️",
        "uv_medium": "UV medio ☀️",
        "uv_high": "UV alto 🧴",
        "advice_hot": "Hace calor 😎, ropa ligera y bebe agua",
        "advice_cold": "Hace frío 🧥, abrígate bien",
        "advice_rain": "Llueve 🌧️, lleva paraguas/impermeable"
    }
}

def t(chat_id, key):
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    return TEXTS.get(lang, TEXTS["es"]).get(key, key)

# ================= OBTENER DATOS METEO =================
def get_meteo_data(nombre):
    lat, lon = TOWN_COORDS.get(nombre, (None, None))
    if lat is None:
        return None, "Pueblo no encontrado en la lista"

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m"
        f"&timezone=Europe/Madrid"
    )

    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()

        if "daily" not in data or "temperature_2m_max" not in data["daily"]:
            logging.warning(f"Respuesta sin daily para {nombre}: {data}")
            return None, "Datos diarios no disponibles en Open-Meteo"

        logging.info(f"Datos OK para {nombre}: max {data['daily']['temperature_2m_max'][0]}°C")
        return data, None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error conexión API para {nombre}: {str(e)}")
        return None, f"Error de conexión: {str(e)}"
    except Exception as e:
        logging.error(f"Error parseando respuesta para {nombre}: {str(e)}")
        return None, "Error inesperado al procesar datos"

# ================= AUXILIARES =================
def wind_scale(kmh):
    if kmh is None: return "?"
    scale = min(10, round(kmh / 6))
    return f"{int(kmh)} km/h | {scale}/10"

def thermal_feel(temp, wind):
    if temp is None or wind is None: return ""
    feel = temp - sqrt(wind) / 3
    return f"🌡️ Sens. térmica ≈ {round(feel)}°C"

def uv_desc(uv, chat_id):
    uv = uv or 0
    if uv < 3: return t(chat_id, "uv_low")
    if uv < 6: return t(chat_id, "uv_medium")
    return t(chat_id, "uv_high")

def clothing_advice(max_temp, rain_prob, chat_id):
    if rain_prob > 30: return t(chat_id, "advice_rain")
    if max_temp >= 28: return t(chat_id, "advice_hot")
    if max_temp <= 15: return t(chat_id, "advice_cold")
    return ""

# ================= ENVIAR MENSAJE =================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return

    nombre = chat_info[chat_id].get("nombre", "—")
    data, error = get_meteo_data(nombre)

    if error:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {nombre}\n{error}\nPrueba más tarde o con otro pueblo."
        )
        return

    daily = data["daily"]
    current = data.get("current_weather", {})

    max_t = daily["temperature_2m_max"][0]
    min_t = daily["temperature_2m_min"][0]
    rain_p = daily["precipitation_probability_max"][0]
    uv = daily.get("uv_index_max", [0])[0]
    wind = daily["wind_speed_10m"][0]
    curr_t = current.get("temperature", round((min_t + max_t) / 2))

    prefix = "🧪 PRUEBA " if TEST_MODE else ""
    is_tarde = (not TEST_MODE) and "weather_e" in context.job.name

    msg = f"{prefix}📍 {nombre}\n\n"
    msg += f"🕗 {'Tarde' if is_tarde else 'Mañana'}:\n"
    msg += f"{thermal_feel(curr_t, wind)}\n"
    msg += f"🌡️ {curr_t}°C   Mín {min_t}°C   Máx {max_t}°C\n"
    msg += f"🌬️ {wind_scale(wind)}   {uv_desc(uv, chat_id)}\n"
    msg += clothing_advice(max_t, rain_p, chat_id)

    await context.bot.send_message(chat_id=chat_id, text=msg, disable_notification=TEST_MODE)

# ================= COMANDO DE PRUEBA API =================
async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in chat_info or "nombre" not in chat_info[chat_id]:
        await update.message.reply_text("Primero elige un pueblo con /start")
        return

    nombre = chat_info[chat_id]["nombre"]
    _, error = get_meteo_data(nombre)

    if error:
        await update.message.reply_text(f"❌ Problema con {nombre}:\n{error}")
    else:
        await update.message.reply_text(f"✅ Datos OK para {nombre}\nPuedes esperar el próximo envío automático")

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["es"]["welcome"], reply_markup=kb_lang())

def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        # Puedes añadir más idiomas si los implementas
    ])

def kb_towns():
    rows = []
    for i in range(0, len(TOWNS), 3):
        row = [InlineKeyboardButton(t, callback_data=f"town_{t}") for t in TOWNS[i:i+3]]
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def remove_jobs(app, chat_id):
    if not app.job_queue:
        return
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.from_user.id

    if data.startswith("lang_"):
        lang = data.replace("lang_", "")
        chat_info.setdefault(chat_id, {})["lang"] = lang
        save_users()
        await query.edit_message_text(t(chat_id, "select"), reply_markup=kb_towns())

    elif data.startswith("town_"):
        town = data.replace("town_", "")
        if town not in TOWN_COORDS:
            await query.edit_message_text("Pueblo no disponible")
            return

        chat_info.setdefault(chat_id, {})["nombre"] = town
        save_users()
        remove_jobs(context.application, chat_id)

        tz = pytz.timezone('Europe/Madrid')

        if TEST_MODE:
            context.application.job_queue.run_repeating(
                send_weather, interval=300, first=10,
                name=f"weather_test_{chat_id}", data={"chat_id": chat_id}
            )
            context.application.job_queue.run_once(
                send_weather, when=0.1,
                name=f"immediate_{chat_id}", data={"chat_id": chat_id}
            )
            await query.edit_message_text(f"🧪 Modo pruebas para {town}\n→ Mensaje en segundos\n→ Luego cada 5 min")
        else:
            context.application.job_queue.run_daily(
                send_weather, time(7, 57, tzinfo=tz),
                name=f"weather_m_{chat_id}", data={"chat_id": chat_id}
            )
            context.application.job_queue.run_daily(
                send_weather, time(19, 57, tzinfo=tz),
                name=f"weather_e_{chat_id}", data={"chat_id": chat_id}
            )
            await query.edit_message_text(t(chat_id, "ok").format(town))

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(t(update.effective_chat.id, "city"))
        return
    town = " ".join(context.args).title()
    if town not in TOWN_COORDS:
        await update.message.reply_text(f"{town} no está en la lista de pueblos disponibles")
        return
    chat_id = update.effective_chat.id
    chat_info.setdefault(chat_id, {})["nombre"] = town
    save_users()
    await update.message.reply_text(f"✅ {town} configurado")

def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            chat_info = {int(k): v for k, v in data.items()}
    except:
        chat_info = {}

def save_users():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error guardando usuarios: {e}")

def main():
    if not TOKEN:
        print("ERROR: TOKEN no encontrado en variables de entorno")
        return

    load_users()
    print("Bot iniciado - pueblos válidos cargados:", len(TOWNS))

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CommandHandler("testapi", test_api))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
