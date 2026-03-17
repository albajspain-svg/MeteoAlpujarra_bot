import os
import json
from datetime import time, datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
DB_FILE = "users.json"
TEST_MODE = True  # ← CAMBIA A False PARA PRODUCCIÓN (solo este cambio)

chat_info = {}  # chat_id: {"nombre": str, "lat": float, "lon": float, "lang": str}
current_ad = {"name": "", "offer": "", "link": ""}

# ====================== BASE DE DATOS (users.json) ======================
def load_users():
    global chat_info
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            chat_info = {int(k): v for k, v in loaded.items()}
        print(f"✅ {len(chat_info)} usuarios cargados desde users.json")
    except:
        chat_info = {}
        print("📂 Nuevo archivo users.json creado")

def save_users():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in chat_info.items()}, f, ensure_ascii=False, indent=2)

# ====================== TRADUCCIONES COMPLETAS ======================
TEXTS = {
    "es": {
        "welcome_lang": "🌦️ ¡Bienvenido a MeteoAlpujarra!\n\nSelecciona tu idioma:",
        "select_location": "¿De dónde quieres saber el tiempo?",
        "activated": "✅ ¡Activado para {}!\nRecibirás alertas a las 8:00 y 20:00.",
        "no_town": "❗️ Elige primero un pueblo",
        "stats": "👥 Usuarios totales: {}",
        "ad_local": "🌟 Apoya al comercio local",
        "advice_prefix": "Consejos:",
        "models": "🌍 Modelos más precisos: ECMWF + ICON + GFS",
        "today": "Hoy",
        "tomorrow": "Mañana",
        "rain_line": "🌧️ Lluvia: ",
        "uv_line": "☀️ UV: ",
        "prob_line": "☔️ Probabilidad (próximas horas):",
        "prob_m": "- Mañana: ",
        "prob_md": "- Mediodía: ",
        "prob_t": "- Tarde: ",
        "wind_line": "💨 Viento: ",
        "other_towns": "Otros pueblos",
        "city_cmd": "Escribe /ciudad Nombre del pueblo",
        "change_lang": "🌍 Cambia tu idioma:",
        "help_text": "Comandos:\n/start - Iniciar\n/idioma - Cambiar idioma\n/clima - Tiempo ahora\n/ciudad Nombre - Cambiar pueblo\n/stop - Parar alertas\n/estadisticas (solo dueño)"
    },
    "en": {
        "welcome_lang": "🌦️ Welcome to MeteoAlpujarra!\n\nSelect your language:",
        "select_location": "Where do you want the weather from?",
        "activated": "✅ Activated for {}!\nYou will receive alerts at 8:00 and 20:00.",
        "no_town": "❗️ Choose a village first",
        "stats": "👥 Total users: {}",
        "ad_local": "🌟 Support local businesses",
        "advice_prefix": "Tips:",
        "models": "🌍 Most accurate models: ECMWF + ICON + GFS",
        "today": "Today",
        "tomorrow": "Tomorrow",
        "rain_line": "🌧️ Rain: ",
        "uv_line": "☀️ UV: ",
        "prob_line": "☔️ Probability (next hours):",
        "prob_m": "- Morning: ",
        "prob_md": "- Midday: ",
        "prob_t": "- Afternoon: ",
        "wind_line": "💨 Wind: ",
        "other_towns": "Other towns",
        "city_cmd": "Type /city Village name",
        "change_lang": "🌍 Change your language:",
        "help_text": "Commands:\n/start - Start\n/idioma - Change language\n/clima - Current weather\n/ciudad Name - Change village\n/stop - Stop alerts\n/estadisticas (owner only)"
    },
    "de": {
        "welcome_lang": "🌦️ Willkommen bei MeteoAlpujarra!\n\nWähle deine Sprache:",
        "select_location": "Von wo möchtest du das Wetter wissen?",
        "activated": "✅ Aktiviert für {}!\nDu erhältst Benachrichtigungen um 8:00 und 20:00.",
        "no_town": "❗️ Wähle zuerst ein Dorf",
        "stats": "👥 Gesamtbenutzer: {}",
        "ad_local": "🌟 Lokale Geschäfte unterstützen",
        "advice_prefix": "Tipps:",
        "models": "🌍 Genaueste Modelle: ECMWF + ICON + GFS",
        "today": "Heute",
        "tomorrow": "Morgen",
        "rain_line": "🌧️ Regen: ",
        "uv_line": "☀️ UV: ",
        "prob_line": "☔️ Regenwahrscheinlichkeit (nächste Stunden):",
        "prob_m": "- Vormittag: ",
        "prob_md": "- Mittag: ",
        "prob_t": "- Nachmittag: ",
        "wind_line": "💨 Wind: ",
        "other_towns": "Andere Dörfer",
        "city_cmd": "Schreibe /ciudad Name des Dorfes",
        "change_lang": "🌍 Sprache ändern:",
        "help_text": "Befehle:\n/start - Start\n/idioma - Sprache ändern\n/clima - Aktuelles Wetter\n/ciudad Name - Dorf wechseln\n/stop - Benachrichtigungen stoppen"
    },
    "nl": {
        "welcome_lang": "🌦️ Welkom bij MeteoAlpujarra!\n\nKies je taal:",
        "select_location": "Waar wil je het weer van weten?",
        "activated": "✅ Geactiveerd voor {}!\nJe krijgt meldingen om 8:00 en 20:00.",
        "no_town": "❗️ Kies eerst een dorp",
        "stats": "👥 Totaal gebruikers: {}",
        "ad_local": "🌟 Steun lokale bedrijven",
        "advice_prefix": "Tips:",
        "models": "🌍 Meest nauwkeurige modellen: ECMWF + ICON + GFS",
        "today": "Vandaag",
        "tomorrow": "Morgen",
        "rain_line": "🌧️ Regen: ",
        "uv_line": "☀️ UV: ",
        "prob_line": "☔️ Kans op regen (komende uren):",
        "prob_m": "- Ochtend: ",
        "prob_md": "- Middag: ",
        "prob_t": "- Avond: ",
        "wind_line": "💨 Wind: ",
        "other_towns": "Andere dorpen",
        "city_cmd": "Typ /ciudad Naam van het dorp",
        "change_lang": "🌍 Verander je taal:",
        "help_text": "Commando's:\n/start - Start\n/idioma - Taal wijzigen\n/clima - Huidig weer\n/ciudad Naam - Dorp wijzigen\n/stop - Stop meldingen"
    },
    "fr": {
        "welcome_lang": "🌦️ Bienvenue sur MeteoAlpujarra !\n\nSélectionnez votre langue :",
        "select_location": "D'où voulez-vous connaître le temps ?",
        "activated": "✅ Activé pour {} !\nVous recevrez des alertes à 8h00 et 20h00.",
        "no_town": "❗️ Choisissez d'abord un village",
        "stats": "👥 Utilisateurs totaux : {}",
        "ad_local": "🌟 Soutenez le commerce local",
        "advice_prefix": "Conseils :",
        "models": "🌍 Modèles les plus précis : ECMWF + ICON + GFS",
        "today": "Aujourd'hui",
        "tomorrow": "Demain",
        "rain_line": "🌧️ Pluie : ",
        "uv_line": "☀️ UV : ",
        "prob_line": "☔️ Probabilité (prochaines heures) :",
        "prob_m": "- Matin : ",
        "prob_md": "- Midi : ",
        "prob_t": "- Après-midi : ",
        "wind_line": "💨 Vent : ",
        "other_towns": "Autres villages",
        "city_cmd": "Tapez /ciudad Nom du village",
        "change_lang": "🌍 Changez votre langue :",
        "help_text": "Commandes :\n/start - Démarrer\n/idioma - Changer langue\n/clima - Météo actuelle\n/ciudad Nom - Changer village\n/stop - Arrêter alertes"
    }
}

TOWNS = ["Órgiva", "Lanjarón", "Pampaneira", "Bubión", "Capileira", "Trevélez", "Soportújar", "Pitres", "Pórtugos", "Busquístar", "Cáñar", "La Taha", "Los Tablones", "Cigarrones", "Bayacas", "El Morreon", "Las Barreras"]

def get_text(lang: str, key: str):
    return TEXTS.get(lang, TEXTS["es"]).get(key, TEXTS["es"][key])

# ====================== METEO ======================
def obtener_datos(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m&hourly=precipitation_probability,windspeed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max&timezone=auto&models=best_match"
    return requests.get(url).json()

def procesar_datos(data, day_offset=0):
    current = data.get("current", {})
    daily = data.get("daily", {})
    hourly = data.get("hourly", {})

    t_actual = round(current.get("temperature_2m", 0))
    tmax = round(daily.get("temperature_2m_max", [0])[day_offset])
    tmin = round(daily.get("temperature_2m_min", [0])[day_offset])
    lluvia = round(daily.get("precipitation_sum", [0])[day_offset], 1)
    uv = round(daily.get("uv_index_max", [0])[day_offset])

    precip = hourly.get("precipitation_probability", [0] * 24)
    mañana_p = int(sum(precip[0:8]) / 8) if len(precip) > 8 else 0
    mediodia_p = int(sum(precip[8:16]) / 8) if len(precip) > 16 else 0
    tarde_p = int(sum(precip[16:24]) / 8) if len(precip) > 24 else 0

    viento = round(hourly.get("windspeed_10m", [0])[0])

    return {
        "t_actual": t_actual, "tmin": tmin, "tmax": tmax, "lluvia": lluvia,
        "uv": uv, "mañana": mañana_p, "mediodia": mediodia_p, "tarde": tarde_p, "viento": viento
    }

def consejos(lang, datos):
    if lang == "en": return "🧥 Jacket if cold | ☀️ Sunscreen | ☔️ Umbrella if rain"
    if lang == "de": return "🧥 Jacke bei Kälte | ☀️ Sonnencreme | ☔️ Schirm bei Regen"
    if lang == "nl": return "🧥 Jas bij kou | ☀️ Zonnebrand | ☔️ Paraplu bij regen"
    if lang == "fr": return "🧥 Veste s'il fait froid | ☀️ Crème solaire | ☔️ Parapluie s'il pleut"
    return "🧥 Abrígate si hace frío | 🕶️ Crema solar | ☔️ Paraguas si llueve"

def crear_mensaje(lang, nombre, datos, is_morning):
    banner = ""
    if current_ad.get("name"):
        banner = f'<b>{get_text(lang, "ad_local")}</b>\n{current_ad["name"]}\n<i>{current_ad["offer"]}</i>\n<a href="{current_ad["link"]}">Ver oferta</a>\n\n'

    day_label = get_text(lang, "today") if is_morning else get_text(lang, "tomorrow")

    return f"""
📍 {nombre} — MeteoAlpujarra

{banner}🌡️ Actual: {datos['t_actual']}°C | {day_label}: {datos['tmin']}°C / {datos['tmax']}°C
{get_text(lang, 'rain_line')}{datos['lluvia']} mm
{get_text(lang, 'uv_line')}{datos['uv']}

{get_text(lang, 'prob_line')}
{get_text(lang, 'prob_m')}{datos['mañana']}%
{get_text(lang, 'prob_md')}{datos['mediodia']}%
{get_text(lang, 'prob_t')}{datos['tarde']}%

{get_text(lang, 'wind_line')}{datos['viento']} km/h

{get_text(lang, "advice_prefix")} {consejos(lang, datos)}

{get_text(lang, "models")}
"""

# ====================== JOBS ======================
def remove_jobs(app, chat_id):
    for job in app.job_queue.jobs():
        if str(chat_id) in job.name:
            job.schedule_removal()

async def enviar_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in chat_info:
        return
    info = chat_info[chat_id]
    lang = info["lang"]
    nombre = info["nombre"]
    lat, lon = info["lat"], info["lon"]

    data_raw = obtener_datos(lat, lon)

    # Decidir Hoy o Mañana
    if "is_morning" in context.job.data:
        is_morning = context.job.data["is_morning"]
    else:
        # Modo prueba: usa hora actual
        hour = datetime.now().hour
        is_morning = hour < 13

    datos = procesar_datos(data_raw, day_offset=0 if is_morning else 1)
    mensaje = crear_mensaje(lang, nombre, datos, is_morning)

    try:
        await context.bot.send_message(chat_id, mensaje, parse_mode='HTML')
    except:
        pass

# ====================== COMANDOS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
        [InlineKeyboardButton("🇳🇱 Nederlands", callback_data="lang_nl")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")]
    ]
    await update.message.reply_text(get_text("es", "welcome_lang"), reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("lang_"):
        lang = data[5:]
        chat_info.setdefault(chat_id, {})["lang"] = lang
        save_users()

        # Teclado de pueblos (multilenguaje)
        keyboard = []
        row = []
        for town in TOWNS:
            row.append(InlineKeyboardButton(town, callback_data=f"town_{town}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(get_text(lang, "other_towns"), callback_data="otros")])

        await query.edit_message_text(get_text(lang, "select_location"), reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("town_"):
        town = data[5:]
        lang = chat_info[chat_id].get("lang", "es")

        if town == "otros":
            await query.edit_message_text(get_text(lang, "city_cmd"))
            return

        res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1&language=es&format=json").json()
        if not res.get("results"):
            await query.edit_message_text("❌ Pueblo no encontrado. Usa /ciudad")
            return

        r = res["results"][0]
        chat_info[chat_id] = {
            "nombre": r.get("name", town),
            "lat": r["latitude"],
            "lon": r["longitude"],
            "lang": lang
        }
        save_users()

        remove_jobs(context.application, chat_id)

        if TEST_MODE:
            context.application.job_queue.run_repeating(
                enviar_job, interval=300, first=5, name=f"weather_test_{chat_id}",
                data={"chat_id": chat_id}
            )
            await query.edit_message_text(get_text(lang, "activated").format(chat_info[chat_id]["nombre"]) + "\n\n🧪 MODO PRUEBA: cada 5 minutos")
        else:
            context.application.job_queue.run_daily(enviar_job, time(8, 0), name=f"weather_morning_{chat_id}", data={"chat_id": chat_id, "is_morning": True})
            context.application.job_queue.run_daily(enviar_job, time(20, 0), name=f"weather_evening_{chat_id}", data={"chat_id": chat_id, "is_morning": False})
            await query.edit_message_text(get_text(lang, "activated").format(chat_info[chat_id]["nombre"]))

async def idioma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    keyboard = [[InlineKeyboardButton(f"{flag} {name}", callback_data=f"lang_{code}")] for flag, name, code in [
        ("🇪🇸", "Español", "es"), ("🇬🇧", "English", "en"), ("🇩🇪", "Deutsch", "de"),
        ("🇳🇱", "Nederlands", "nl"), ("🇫🇷", "Français", "fr")
    ]]
    await update.message.reply_text(get_text(lang, "change_lang"), reply_markup=InlineKeyboardMarkup(keyboard))

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(get_text("es", "stats").format(len(chat_info)))

async def setad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        current_ad["name"] = ""
        await update.message.reply_text("✅ Publicidad desactivada")
        return
    name = context.args[0]
    link = context.args[-1]
    offer = " ".join(context.args[1:-1])
    current_ad.update({"name": name, "offer": offer, "link": link})
    await update.message.reply_text(f"✅ Publicidad activada:\n{name}\n{offer}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_info:
        del chat_info[chat_id]
        save_users()
        remove_jobs(context.application, chat_id)
        await update.message.reply_text("✅ Alertas detenidas. Usa /start para volver.")
    else:
        await update.message.reply_text("No tenías alertas activas.")

async def clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in chat_info:
        await update.message.reply_text(get_text(chat_info.get(chat_id, {}).get("lang", "es"), "no_town"))
        return
    info = chat_info[chat_id]
    data_raw = obtener_datos(info["lat"], info["lon"])
    datos = procesar_datos(data_raw, 0)
    msg = crear_mensaje(info["lang"], info["nombre"], datos, True)
    await update.message.reply_text(msg, parse_mode='HTML')

async def ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        lang = chat_info.get(update.effective_chat.id, {}).get("lang", "es")
        await update.message.reply_text(get_text(lang, "city_cmd"))
        return
    town = " ".join(context.args)
    res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={town}&count=1&language=es&format=json").json()
    if not res.get("results"):
        await update.message.reply_text("❌ No encontrado. Prueba otro nombre.")
        return
    r = res["results"][0]
    chat_id = update.effective_chat.id
    lang = chat_info.get(chat_id, {}).get("lang", "es")
    chat_info[chat_id] = {"nombre": r.get("name", town), "lat": r["latitude"], "lon": r["longitude"], "lang": lang}
    save_users()
    remove_jobs(context.application, chat_id)
    if TEST_MODE:
        context.application.job_queue.run_repeating(enviar_job, interval=300, first=5, name=f"weather_test_{chat_id}", data={"chat_id": chat_id})
    else:
        context.application.job_queue.run_daily(enviar_job, time(8, 0), name=f"weather_morning_{chat_id}", data={"chat_id": chat_id, "is_morning": True})
        context.application.job_queue.run_daily(enviar_job, time(20, 0), name=f"weather_evening_{chat_id}", data={"chat_id": chat_id, "is_morning": False})
    await update.message.reply_text(get_text(lang, "activated").format(chat_info[chat_id]["nombre"]))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = chat_info.get(update.effective_chat.id, {}).get("lang", "es")
    await update.message.reply_text(get_text(lang, "help_text"))

# ====================== MAIN ======================
def main():
    load_users()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("idioma", idioma))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(CommandHandler("setad", setad))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("clima", clima))
    app.add_handler(CommandHandler("ciudad", ciudad))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 MeteoAlpujarra V6 iniciado – ¡Base de datos + TEST_MODE listo!")
    app.run_polling()

if __name__ == "__main__":
    main()
