import logging
import os
import sqlite3
import time as time_module
from datetime import datetime, time as dt_time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import httpx

# ====================== CONFIG ======================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Falta BOT_TOKEN en Variables de Railway")
MODO_PRUEBA = False

DB_PATH = "users.db"

# ====================== CACHÉ ANTI-429 ======================
weather_cache = {}

# ====================== BBDD ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'ES',
            location TEXT DEFAULT 'ÓRGIVA',
            chat_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT lang, location, chat_id FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return {"lang": row[0], "location": row[1], "chat_id": row[2]}
    cur.execute("INSERT INTO users (user_id, lang, location) VALUES (?, 'ES', 'ÓRGIVA')", (user_id,))
    conn.commit()
    conn.close()
    return {"lang": "ES", "location": "ÓRGIVA", "chat_id": None}

def update_user_data(user_id: int, lang=None, location=None, chat_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sets = []
    params = []
    if lang is not None: sets.append("lang=?"); params.append(lang)
    if location is not None: sets.append("location=?"); params.append(location)
    if chat_id is not None: sets.append("chat_id=?"); params.append(chat_id)
    if sets:
        query = f"UPDATE users SET {', '.join(sets)} WHERE user_id=?"
        params.append(user_id)
        cur.execute(query, params)
        if cur.rowcount == 0:
            cur.execute("INSERT INTO users (user_id, lang, location, chat_id) VALUES (?, ?, ?, ?)",
                        (user_id, lang or "ES", location or "ÓRGIVA", chat_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, lang, location, chat_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [{"user_id": r[0], "lang": r[1], "location": r[2], "chat_id": r[3]} for r in rows]

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}
COASTAL_PUEBLOS = ["MOTRIL", "ALMUÑÉCAR", "SALOBREÑA"]
PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== TEXTOS COMPLETOS (TODOS LOS IDIOMAS) ======================
TEXTOS = {
    "ES": {
        "idioma_cmd": "/idioma", "poblacion_cmd": "/poblacion",
        "idioma": "Selecciona idioma",
        "bienvenido": "✅ Bot activado\nPoblación actual: {loc}",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a **{loc}**\nBuscando datos actualizados...\nEspere un momento.\n📍 Para cambiar de nuevo usa /poblacion",
        "footer": "🌍 Cambiar idioma: /start\n📍 Cambiar localización: /poblacion",
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
        "uv_bajo": "Bajo (FPS 15-30 recomendado)",
        "uv_moderado": "Moderado (FPS 30-50 recomendado)",
        "uv_alto": "Alto (FPS 50+ recomendado)",
        "uv_muy_alto": "Muy alto (FPS 50+ y evitar sol recomendado)",
        "uv_extremo": "Extremo (FPS 50+ y evitar exposición recomendado)",
        "sea_temp": "🌊 Temperatura del agua del mar: {sea}°C.",
        "humedad": "💧 Humedad relativa: {hum}%.",
        "info_envios": "Los pronósticos se envían automáticamente a las 8am para el día corriente y a las 20h para el día siguiente.",
        "rain_hours": "☔ Lluvia posible a las: {hours}.",
        "brief_title": "Pronóstico breve próximos 3 días:",
        "brief_days": ["Mañana", "Pasado mañana", "En 3 días"],
        "brief_format": "• {day_label}: Máx {max_t}°C Mín {min_t}°C Lluvia {rain_prob}% Viento {wind_kmh} km/h",
    },
    "EN": {
        "idioma_cmd": "/language", "poblacion_cmd": "/location",
        "idioma": "Select language",
        "bienvenido": "✅ Activated\nCurrent location: {loc}",
        "cambiar": "Choose your location:",
        "buscando": "✅ Changed to **{loc}**\nFetching updated data...\nPlease wait.\n📍 To change again use /poblacion",
        "footer": "🌍 Change language: /start\n📍 Change location: /poblacion",
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
        "uv_bajo": "Low (SPF 15-30 recommended)",
        "uv_moderado": "Moderate (SPF 30-50 recommended)",
        "uv_alto": "High (SPF 50+ recommended)",
        "uv_muy_alto": "Very high (SPF 50+ and avoid sun recommended)",
        "uv_extremo": "Extreme (SPF 50+ and avoid exposure recommended)",
        "sea_temp": "🌊 Sea water temperature: {sea}°C.",
        "humedad": "💧 Relative humidity: {hum}%.",
        "info_envios": "Forecasts are sent automatically at 8am for the current day and at 20h for the next day.",
        "rain_hours": "☔ Possible rain around: {hours}.",
        "brief_title": "Brief forecast for the next 3 days:",
        "brief_days": ["Tomorrow", "Day after tomorrow", "In 3 days"],
        "brief_format": "• {day_label}: Max {max_t}°C Min {min_t}°C Rain {rain_prob}% Wind {wind_kmh} km/h",
    },
    "NL": {
        "idioma_cmd": "/taal", "poblacion_cmd": "/locatie",
        "idioma": "Selecteer taal",
        "bienvenido": "✅ Bot geactiveerd\nHuidige locatie: {loc}",
        "cambiar": "Kies je locatie:",
        "buscando": "✅ Gewijzigd naar **{loc}**\nGegevens ophalen...\nEen moment geduld.\n📍 Om opnieuw te wijzigen gebruik /poblacion",
        "footer": "🌍 Taal wijzigen: /start\n📍 Locatie wijzigen: /poblacion",
        "siguiente_8": "Volgende bericht om 20:00\nFijne dag!",
        "siguiente_20": "Volgende bericht om 8:00\nGoede nacht!",
        "temp_actual_title": "🌡️ Huidige temperatuur:",
        "sensacion": " (voelt als {sens}°C).",
        "estado_actual": "☀️ Huidige toestand: {estado}",
        "prediccion_hoy": "Voorspelling voor vandaag",
        "prediccion_manana": "Voorspelling voor morgen",
        "temp_max": "🔼 Maximum temperatuur: {max_t}°C.",
        "temp_min": "🔽 Minimum temperatuur: {min_t}°C.",
        "prob_lluvia": "☔ Kans op regen: {rain_prob}%.",
        "int_viento": "🌬️ Wind: {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Maximale UV-intensiteit: {uv_text}.",
        "fase_lunar": "Maanfase: {lunar}.",
        "hora_puesta": "🌇 Zonsondergang",
        "hora_amanecer": "🌅 Zonsopgang",
        "desc_day": "Dagbeschrijving:",
        "consejos_title": "Tips:",
        "consejo_uv": "• Gebruik zonnebrandcrème SPF 50+, zonnebril en vermijd direct zonlicht tussen 12:00 en 16:00.",
        "consejo_rain": "• Neem een paraplu of regenjas mee; regen kan plotseling komen.",
        "consejo_windcold": "• Een lichte jas is essentieel; beschermt tegen wind en kou.",
        "consejo_ligera": "• Lichte en comfortabele kleding is voldoende voor de hele dag.",
        "consejo_capa": "• Neem een extra laag mee voor de middag of avond vanwege temperatuurwisselingen.",
        "consejo_coast": "• Geniet van de zeewind voor een aangename wandeling langs de kust.",
        "consejo_mountain": "• In berggebieden, bereid je voor op nachtelijke temperatuurwisselingen.",
        "separator": "───────────────────",
        "estado_despejado": "Helder met bries.",
        "estado_nublado": "Bewolkt met mogelijke buien.",
        "estado_fallback": "Gedeeltelijk bewolkt.",
        "luna_llena": "Volle maan (95-100%)",
        "luna_creciente": "Wassende maan (60-70%)",
        "luna_fallback": "Volle maan (96%)",
        "luna_nueva": "Nieuwe maan (0-5%)",
        "wind_desc_calma": "totale kalmte",
        "wind_desc_ligera": "lichte bries",
        "wind_desc_moderada": "matige bries",
        "wind_desc_fuerte": "frisse wind",
        "wind_desc_muy_fuerte": "sterke wind",
        "wind_desc_tormenta": "storm",
        "desc_clear": "• Meestal helder en zonnige dag.",
        "desc_partly": "• Dag met wolken en heldere intervallen.",
        "desc_cloudy": "• Bewolkte dag of met buien.",
        "desc_wind_strong": "• Matige tot sterke wind in de middag.",
        "desc_wind_light": "• Lichte bries gedurende de dag.",
        "desc_wind_calma": "• Rustige wind.",
        "desc_temp_hot": "• Aanzienlijke hitte, blijf gehydrateerd.",
        "desc_temp_cool": "• Koel klimaat, ideaal voor activiteiten.",
        "desc_temp_pleasant": "• Aangename en comfortabele temperaturen.",
        "desc_coast": "• Typische zeewind aan de kust.",
        "desc_mountain": "• Typisch bergklimaat met mogelijke variaties.",
        "uv_bajo": "Laag (SPF 15-30 aanbevolen)",
        "uv_moderado": "Matig (SPF 30-50 aanbevolen)",
        "uv_alto": "Hoog (SPF 50+ aanbevolen)",
        "uv_muy_alto": "Zeer hoog (SPF 50+ en zon vermijden aanbevolen)",
        "uv_extremo": "Extreem (SPF 50+ en blootstelling vermijden aanbevolen)",
        "sea_temp": "🌊 Temperatuur van het zeewater: {sea}°C.",
        "humedad": "💧 Relatieve vochtigheid: {hum}%.",
        "info_envios": "De voorspellingen worden automatisch verzonden om 8:00 voor de huidige dag en om 20:00 voor de volgende dag.",
        "rain_hours": "☔ Mogelijke regen rond: {hours}.",
        "brief_title": "Korte voorspelling voor de komende 3 dagen:",
        "brief_days": ["Morgen", "Overmorgen", "Over 3 dagen"],
        "brief_format": "• {day_label}: Max {max_t}°C Min {min_t}°C Regen {rain_prob}% Wind {wind_kmh} km/h",
    },
    "DE": {
        "idioma_cmd": "/sprache", "poblacion_cmd": "/standort",
        "idioma": "Sprache auswählen",
        "bienvenido": "✅ Bot aktiviert\nAktueller Standort: {loc}",
        "cambiar": "Wählen Sie Ihren Standort:",
        "buscando": "✅ Geändert zu **{loc}**\nDaten abrufen...\nBitte warten.\n📍 Zum erneuten Ändern verwenden Sie /poblacion",
        "footer": "🌍 Sprache ändern: /start\n📍 Standort ändern: /poblacion",
        "siguiente_8": "Nächste Nachricht um 20:00\nSchönen Tag!",
        "siguiente_20": "Nächste Nachricht um 8:00\nGute Nacht!",
        "temp_actual_title": "🌡️ Aktuelle Temperatur:",
        "sensacion": " (fühlt sich an wie {sens}°C).",
        "estado_actual": "☀️ Aktueller Zustand: {estado}",
        "prediccion_hoy": "Vorhersage für heute",
        "prediccion_manana": "Vorhersage für morgen",
        "temp_max": "🔼 Höchsttemperatur: {max_t}°C.",
        "temp_min": "🔽 Tiefsttemperatur: {min_t}°C.",
        "prob_lluvia": "☔ Regenwahrscheinlichkeit: {rain_prob}%.",
        "int_viento": "🌬️ Wind: {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Maximale UV-Intensität: {uv_text}.",
        "fase_lunar": "Mondphase: {lunar}.",
        "hora_puesta": "🌇 Sonnenuntergang",
        "hora_amanecer": "🌅 Sonnenaufgang",
        "desc_day": "Tagesbeschreibung:",
        "consejos_title": "Tipps:",
        "consejo_uv": "• Verwenden Sie Sonnenschutz SPF 50+, Sonnenbrille und vermeiden Sie direkte Sonne zwischen 12:00 und 16:00.",
        "consejo_rain": "• Nehmen Sie einen Regenschirm oder Regenjacke mit; Regen kann plötzlich auftreten.",
        "consejo_windcold": "• Eine leichte Jacke ist unerlässlich; schützt vor Wind und Kälte.",
        "consejo_ligera": "• Leichte und bequeme Kleidung reicht für den ganzen Tag.",
        "consejo_capa": "• Nehmen Sie eine Extra-Schicht für Nachmittag oder Abend wegen Temperaturschwankungen.",
        "consejo_coast": "• Genießen Sie die Meeresbrise für einen angenehmen Spaziergang an der Küste.",
        "consejo_mountain": "• In Berggebieten bereiten Sie sich auf nächtliche Temperaturschwankungen vor.",
        "separator": "───────────────────",
        "estado_despejado": "Klar mit Brise.",
        "estado_nublado": "Bewölkt mit möglichen Schauern.",
        "estado_fallback": "Teilweise bewölkt.",
        "luna_llena": "Vollmond (95-100%)",
        "luna_creciente": "Zunehmender Mond (60-70%)",
        "luna_fallback": "Vollmond (96%)",
        "luna_nueva": "Neumond (0-5%)",
        "wind_desc_calma": "völlige Ruhe",
        "wind_desc_ligera": "leichte Brise",
        "wind_desc_moderada": "mäßige Brise",
        "wind_desc_fuerte": "frischer Wind",
        "wind_desc_muy_fuerte": "starker Wind",
        "wind_desc_tormenta": "Sturm",
        "desc_clear": "• Meist klar und sonniger Tag.",
        "desc_partly": "• Tag mit Wolken und klaren Intervallen.",
        "desc_cloudy": "• Bewölkter Tag oder mit Schauern.",
        "desc_wind_strong": "• Mäßiger bis starker Wind am Nachmittag.",
        "desc_wind_light": "• Leichte Brise tagsüber.",
        "desc_wind_calma": "• Ruhiger Wind.",
        "desc_temp_hot": "• Spürbare Hitze, bleiben Sie hydriert.",
        "desc_temp_cool": "• Kühles Klima, ideal für Aktivitäten.",
        "desc_temp_pleasant": "• Angenehme und komfortable Temperaturen.",
        "desc_coast": "• Typische Meeresbrise an der Küste.",
        "desc_mountain": "• Typisches Bergklima mit möglichen Variationen.",
        "uv_bajo": "Niedrig (SPF 15-30 empfohlen)",
        "uv_moderado": "Mäßig (SPF 30-50 empfohlen)",
        "uv_alto": "Hoch (SPF 50+ empfohlen)",
        "uv_muy_alto": "Sehr hoch (SPF 50+ und Sonne vermeiden empfohlen)",
        "uv_extremo": "Extrem (SPF 50+ und Exposition vermeiden empfohlen)",
        "sea_temp": "🌊 Wassertemperatur des Meeres: {sea}°C.",
        "humedad": "💧 Relative Luftfeuchtigkeit: {hum}%.",
        "info_envios": "Die Vorhersagen werden automatisch um 8:00 für den aktuellen Tag und um 20:00 für den nächsten Tag gesendet.",
        "rain_hours": "☔ Mögliche Regen um: {hours}.",
        "brief_title": "Kurze Vorhersage für die nächsten 3 Tage:",
        "brief_days": ["Morgen", "Übermorgen", "In 3 Tagen"],
        "brief_format": "• {day_label}: Max {max_t}°C Min {min_t}°C Regen {rain_prob}% Wind {wind_kmh} km/h",
    },
    "FR": {
        "idioma_cmd": "/langue", "poblacion_cmd": "/localisation",
        "idioma": "Sélectionnez la langue",
        "bienvenido": "✅ Bot activé\nLocalisation actuelle : {loc}",
        "cambiar": "Choisissez votre localisation :",
        "buscando": "✅ Changé en **{loc}**\nRécupération des données...\nVeuillez patienter.\n📍 Pour changer à nouveau utilisez /poblacion",
        "footer": "🌍 Changer de langue : /start\n📍 Changer de localisation : /poblacion",
        "siguiente_8": "Prochain message à 20:00\nBonne journée !",
        "siguiente_20": "Prochain message à 8:00\nBonne nuit !",
        "temp_actual_title": "🌡️ Température actuelle :",
        "sensacion": " (ressenti {sens}°C).",
        "estado_actual": "☀️ Condition actuelle : {estado}",
        "prediccion_hoy": "Prévision pour aujourd'hui",
        "prediccion_manana": "Prévision pour demain",
        "temp_max": "🔼 Température maximale : {max_t}°C.",
        "temp_min": "🔽 Température minimale : {min_t}°C.",
        "prob_lluvia": "☔ Probabilité de pluie : {rain_prob}%.",
        "int_viento": "🌬️ Vent : {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Intensité UV maximale : {uv_text}.",
        "fase_lunar": "Phase lunaire : {lunar}.",
        "hora_puesta": "🌇 Coucher du soleil",
        "hora_amanecer": "🌅 Lever du soleil",
        "desc_day": "Description de la journée :",
        "consejos_title": "Conseils :",
        "consejo_uv": "• Utilisez une crème solaire SPF 50+, des lunettes de soleil et évitez le soleil direct entre 12h et 16h.",
        "consejo_rain": "• Prenez un parapluie ou un imperméable ; la pluie peut apparaître soudainement.",
        "consejo_windcold": "• Une veste légère est indispensable ; protège du vent et du froid.",
        "consejo_ligera": "• Des vêtements légers et confortables suffisent toute la journée.",
        "consejo_capa": "• Prenez une couche supplémentaire pour l'après-midi ou la nuit en raison des changements de température.",
        "consejo_coast": "• Profitez de la brise marine pour une agréable promenade côtière.",
        "consejo_mountain": "• Dans les zones de montagne, préparez-vous aux changements de température nocturnes.",
        "separator": "───────────────────",
        "estado_despejado": "Dégagé avec brise.",
        "estado_nublado": "Nuageux avec averses possibles.",
        "estado_fallback": "Partiellement nuageux.",
        "luna_llena": "Pleine lune (95-100%)",
        "luna_creciente": "Croissant de lune (60-70%)",
        "luna_fallback": "Pleine lune (96%)",
        "luna_nueva": "Nouvelle lune (0-5%)",
        "wind_desc_calma": "calme total",
        "wind_desc_ligera": "brise légère",
        "wind_desc_moderada": "brise modérée",
        "wind_desc_fuerte": "vent frais",
        "wind_desc_muy_fuerte": "vent fort",
        "wind_desc_tormenta": "tempête",
        "desc_clear": "• Journée principalement dégagée et ensoleillée.",
        "desc_partly": "• Journée avec des nuages et des éclaircies.",
        "desc_cloudy": "• Journée nuageuse ou avec averses.",
        "desc_wind_strong": "• Vent modéré à fort l'après-midi.",
        "desc_wind_light": "• Brise légère pendant la journée.",
        "desc_wind_calma": "• Vent calme.",
        "desc_temp_hot": "• Chaleur notable, restez hydraté.",
        "desc_temp_cool": "• Environnement frais, idéal pour les activités.",
        "desc_temp_pleasant": "• Températures agréables et confortables.",
        "desc_coast": "• Brise marine typique de la côte.",
        "desc_mountain": "• Climat typique de montagne avec variations possibles.",
        "uv_bajo": "Faible (FPS 15-30 recommandé)",
        "uv_moderado": "Modéré (FPS 30-50 recommandé)",
        "uv_alto": "Élevé (FPS 50+ recommandé)",
        "uv_muy_alto": "Très élevé (FPS 50+ et éviter le soleil recommandé)",
        "uv_extremo": "Extrême (FPS 50+ et éviter l'exposition recommandé)",
        "sea_temp": "🌊 Température de l'eau de mer : {sea}°C.",
        "humedad": "💧 Humidité relative : {hum}%.",
        "info_envios": "Les prévisions sont envoyées automatiquement à 8h pour le jour courant et à 20h pour le jour suivant.",
        "rain_hours": "☔ Pluie possible vers : {hours}.",
        "brief_title": "Prévision brève pour les 3 prochains jours :",
        "brief_days": ["Demain", "Après-demain", "Dans 3 jours"],
        "brief_format": "• {day_label} : Max {max_t}°C Min {min_t}°C Pluie {rain_prob}% Vent {wind_kmh} km/h",
    },
    "IT": {
        "idioma_cmd": "/lingua", "poblacion_cmd": "/posizione",
        "idioma": "Seleziona lingua",
        "bienvenido": "✅ Bot attivato\nPosizione attuale: {loc}",
        "cambiar": "Scegli la tua località:",
        "buscando": "✅ Cambiato a **{loc}**\nRecupero dati aggiornati...\nAttendi un momento.\n📍 Per cambiare di nuovo usa /poblacion",
        "footer": "🌍 Cambia lingua: /start\n📍 Cambia località: /poblacion",
        "siguiente_8": "Prossimo messaggio alle 20:00\nBuona giornata!",
        "siguiente_20": "Prossimo messaggio alle 8:00\nBuona notte!",
        "temp_actual_title": "🌡️ Temperatura attuale:",
        "sensacion": " (percepita {sens}°C).",
        "estado_actual": "☀️ Condizione attuale: {estado}",
        "prediccion_hoy": "Previsione per oggi",
        "prediccion_manana": "Previsione per domani",
        "temp_max": "🔼 Temperatura massima: {max_t}°C.",
        "temp_min": "🔽 Temperatura minima: {min_t}°C.",
        "prob_lluvia": "☔ Probabilità di pioggia: {rain_prob}%.",
        "int_viento": "🌬️ Vento: {wind_kmh} km/h ({wind_desc}).",
        "int_uv": "☀️ Intensità UV massima: {uv_text}.",
        "fase_lunar": "Fase lunare: {lunar}.",
        "hora_puesta": "🌇 Tramonto",
        "hora_amanecer": "🌅 Alba",
        "desc_day": "Descrizione del giorno:",
        "consejos_title": "Consigli:",
        "consejo_uv": "• Usa crema solare SPF 50+, occhiali da sole ed evita il sole diretto tra le 12:00 e le 16:00.",
        "consejo_rain": "• Porta un ombrello o impermeabile; la pioggia può arrivare improvvisamente.",
        "consejo_windcold": "• Una giacca leggera è essenziale; protegge dal vento e dal freddo.",
        "consejo_ligera": "• Vestiti leggeri e comodi sono sufficienti per tutto il giorno.",
        "consejo_capa": "• Porta uno strato extra per il pomeriggio o la sera a causa dei cambiamenti di temperatura.",
        "consejo_coast": "• Goditi la brezza marina per una piacevole passeggiata sulla costa.",
        "consejo_mountain": "• Nelle zone di montagna, preparati ai cambiamenti di temperatura notturni.",
        "separator": "───────────────────",
        "estado_despejado": "Sereno con brezza.",
        "estado_nublado": "Nuvoloso con possibili rovesci.",
        "estado_fallback": "Parzialmente nuvoloso.",
        "luna_llena": "Luna piena (95-100%)",
        "luna_creciente": "Luna crescente (60-70%)",
        "luna_fallback": "Luna piena (96%)",
        "luna_nueva": "Luna nuova (0-5%)",
        "wind_desc_calma": "calma totale",
        "wind_desc_ligera": "brezza leggera",
        "wind_desc_moderada": "brezza moderata",
        "wind_desc_fuerte": "vento fresco",
        "wind_desc_muy_fuerte": "vento forte",
        "wind_desc_tormenta": "tempesta",
        "desc_clear": "• Giornata prevalentemente serena e soleggiata.",
        "desc_partly": "• Giornata con intervalli di nuvole e schiarite.",
        "desc_cloudy": "• Giornata nuvolosa o con rovesci.",
        "desc_wind_strong": "• Vento moderato a forte nel pomeriggio.",
        "desc_wind_light": "• Brezza leggera durante il giorno.",
        "desc_wind_calma": "• Vento calmo.",
        "desc_temp_hot": "• Caldo notevole, mantieniti idratato.",
        "desc_temp_cool": "• Ambiente fresco, ideale per attività.",
        "desc_temp_pleasant": "• Temperature piacevoli e confortevoli.",
        "desc_coast": "• Brezza marina tipica della costa.",
        "desc_mountain": "• Clima tipico di montagna con possibili variazioni.",
        "uv_bajo": "Basso (SPF 15-30 consigliato)",
        "uv_moderado": "Moderato (SPF 30-50 consigliato)",
        "uv_alto": "Alto (SPF 50+ consigliato)",
        "uv_muy_alto": "Molto alto (SPF 50+ e evitare sole consigliato)",
        "uv_extremo": "Estremo (SPF 50+ e evitare esposizione consigliato)",
        "sea_temp": "🌊 Temperatura dell'acqua del mare: {sea}°C.",
        "humedad": "💧 Umidità relativa: {hum}%.",
        "info_envios": "Le previsioni vengono inviate automaticamente alle 8:00 per il giorno corrente e alle 20:00 per il giorno successivo.",
        "rain_hours": "☔ Pioggia possibile intorno alle: {hours}.",
        "brief_title": "Previsione breve per i prossimi 3 giorni:",
        "brief_days": ["Domani", "Dopodomani", "Tra 3 giorni"],
        "brief_format": "• {day_label}: Max {max_t}°C Min {min_t}°C Pioggia {rain_prob}% Vento {wind_kmh} km/h",
    }
}

# ====================== FUNCIONES AUXILIARES ======================
# (get_lunar_phase, wind_description, uv_explanation, get_day_description, get_consejos)
# Copiadas exactamente igual que en la versión anterior (no las repito aquí para no alargar, pero están en el código que ya tenías)

# ====================== OBTENER DATOS ======================
async def get_real_weather(loc_name: str):
    now_ts = time_module.time()
    if loc_name in weather_cache and now_ts - weather_cache[loc_name]["ts"] < 1200:
        c = weather_cache[loc_name]
        return c["data"], "openmeteo", c["sea"], c["hum"]

    if loc_name in ["LOS TABLONES", "EL MORREÓN", "LAS BARRERAS", "BAYACAS"]:
        lat, lon = COORDS["ÓRGIVA"]
    else:
        lat, lon = COORDS.get(loc_name, (36.90, -3.42))

    sea_temp = None
    if loc_name in COASTAL_PUEBLOS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&daily=sea_surface_temperature_max&timezone=Europe/Madrid")
                if r.status_code == 200:
                    sea_temp = round(r.json()["daily"]["sea_surface_temperature_max"][0])
        except: pass

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m,uv_index&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max,wind_speed_10m_max&timezone=Europe/Madrid&forecast_days=4"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                humidity = data["current"].get("relative_humidity_2m", 60)
                weather_cache[loc_name] = {"data": data, "sea": sea_temp, "hum": humidity, "ts": now_ts}
                return data, "openmeteo", sea_temp, humidity
    except: pass
    return None, "fallback", None, 60

# ====================== MENSAJE FINAL ======================
# (build_weather_message exactamente igual que en la versión anterior)

# ====================== COMANDOS y MAIN ======================
# (cmd_actualizar, cmd_idioma, lang_callback, cmd_poblacion, loc_callback, weather_job, main)
# Exactamente igual que en la versión anterior, con los imports corregidos

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook borrado correctamente")
    app.post_init = post_init

    app.add_handler(CommandHandler(["start", "idioma", "language"], cmd_idioma))
    app.add_handler(CommandHandler(["poblacion", "location"], cmd_poblacion))
    app.add_handler(CommandHandler(["actualizar", "update"], cmd_actualizar))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(loc_callback, pattern="^loc_"))

    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=5)
    else:
        jq.run_daily(weather_job, time=dt_time(hour=8, minute=0))
        jq.run_daily(weather_job, time=dt_time(hour=20, minute=0))

    jq.run_repeating(lambda c: logging.info("Keep-alive ping"), interval=840)

    logging.info("✅ BOT INICIADO | TODOS IDIOMAS COMPLETOS | Caché + Pronóstico 3 días")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
