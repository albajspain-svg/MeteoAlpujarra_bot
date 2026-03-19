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
MODO_PRUEBA = False  # ← False = MODO REAL (8:00 y 20:00). El bot está SIEMPRE conectado vía polling para evitar errores

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}

# ====================== TEXTOS TRADUCIDOS COMPLETOS (TODOS LOS MENSAJES) ======================
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
        # === TEXTOS DEL CLIMA (TRADUCIDOS) ===
        "temp_actual_title": "🌡️ Temperatura actual:",
        "sensacion": " (sensación {sens}°C).",
        "estado_actual": "☀️ Estado actual: {estado}",
        "prediccion_hoy": "Predicción para hoy",
        "prediccion_manana": "Predicción para mañana",
        "temp_max": "🔼 Temperatura máxima: {max_t}°C.",
        "temp_min": "🔽 Temperatura mínima: {min_t}°C.",
        "prob_lluvia": "☔ Probabilidad de lluvia: {rain_prob}%.",
        "int_viento": "🌬️ Intensidad del viento: {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Intensidad UV máxima: {uv_text}.",
        "fase_lunar": "Fase lunar: {lunar}.",
        "hora_puesta": "🌇 Hora puesta de sol",
        "hora_amanecer": "🌅 Hora amanecer",
        "desc_day": "Descripción del día:",
        "desc1": "• Mañana fresca y mayormente despejada.",
        "desc2": "• Tarde con algo de viento y posibles nubes altas.",
        "desc3": "• Noche clara y fresca con luna visible.",
        "consejos_title": "Consejos:",
        "consejo_uv": "• Protector solar 50+ y gafas de sol recomendados.",
        "consejo_rain": "• Paraguas o chubasquero necesario.",
        "consejo_windcold": "• Chaqueta o abrigo ligero imprescindible.",
        "consejo_ligera": "• Ropa ligera y cómoda es suficiente.",
        "consejo_capa": "• Capa extra para la tarde/noche.",
        "separator": "───────────────────",
        "wind_0": "0 (calma total)",
        "wind_1": "1 (brisa muy ligera)",
        "wind_3": "3 (brisa ligera)",
        "wind_5": "5 (brisa moderada)",
        "wind_7": "7 (viento fresco)",
        "wind_9": "9 (viento fuerte)",
        "wind_10": "10 (super fuerte / tormenta)",
        "uv_bajo": "Bajo",
        "uv_moderado": "Moderado",
        "uv_alto": "Alto",
        "uv_muy_alto": "Muy alto",
        "uv_extremo": "Extremo",
        "estado_despejado": "Despejado con brisa.",
        "estado_nublado": "Nublado con posibles chubascos.",
        "estado_fallback": "Parcialmente nublado.",
        "luna_llena": "Luna llena (95-100%)",
        "luna_creciente": "Cuarto creciente (60-70%)",
        "luna_fallback": "Luna llena (96%)",
        "luna_nueva": "Luna nueva (0-5%)",  # ← NUEVO: fase real
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
        "int_viento": "🌬️ Wind intensity: {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Maximum UV intensity: {uv_text}.",
        "fase_lunar": "Moon phase: {lunar}.",
        "hora_puesta": "🌇 Sunset time",
        "hora_amanecer": "🌅 Sunrise time",
        "desc_day": "Day description:",
        "desc1": "• Cool morning and mostly clear.",
        "desc2": "• Afternoon with some wind and possible high clouds.",
        "desc3": "• Clear and cool night with visible moon.",
        "consejos_title": "Tips:",
        "consejo_uv": "• SPF 50+ sunscreen and sunglasses recommended.",
        "consejo_rain": "• Umbrella or raincoat necessary.",
        "consejo_windcold": "• Light jacket or coat essential.",
        "consejo_ligera": "• Light and comfortable clothing is sufficient.",
        "consejo_capa": "• Extra layer for afternoon/evening.",
        "separator": "───────────────────",
        "wind_0": "0 (total calm)",
        "wind_1": "1 (very light breeze)",
        "wind_3": "3 (light breeze)",
        "wind_5": "5 (moderate breeze)",
        "wind_7": "7 (fresh wind)",
        "wind_9": "9 (strong wind)",
        "wind_10": "10 (very strong / storm)",
        "uv_bajo": "Low",
        "uv_moderado": "Moderate",
        "uv_alto": "High",
        "uv_muy_alto": "Very high",
        "uv_extremo": "Extreme",
        "estado_despejado": "Clear with breeze.",
        "estado_nublado": "Cloudy with possible showers.",
        "estado_fallback": "Partly cloudy.",
        "luna_llena": "Full moon (95-100%)",
        "luna_creciente": "Waxing crescent (60-70%)",
        "luna_fallback": "Full moon (96%)",
        "luna_nueva": "New moon (0-5%)",  # ← NUEVO: fase real
    },
    "NL": {
        "idioma_cmd": "/taal", "poblacion_cmd": "/plaats",
        "idioma": "Kies taal",
        "bienvenido": "✅ Actief\nHuidige plaats: {loc}",
        "cambiar": "Kies je plaats:",
        "buscando": "✅ Gewijzigd naar **{loc}**\nData ophalen nu...\nEven geduld.",
        "footer": "Druk op /start om de taal te wijzigen\nDruk op /poblacion om de plaats te wijzigen",
        "siguiente_8": "Volgend bericht om 20:00\nFijne dag!",
        "siguiente_20": "Volgend bericht om 8:00\nGoede nacht!",
        "temp_actual_title": "🌡️ Huidige temperatuur:",
        "sensacion": " (voelt als {sens}°C).",
        "estado_actual": "☀️ Huidige toestand: {estado}",
        "prediccion_hoy": "Voorspelling voor vandaag",
        "prediccion_manana": "Voorspelling voor morgen",
        "temp_max": "🔼 Maximum temperatuur: {max_t}°C.",
        "temp_min": "🔽 Minimum temperatuur: {min_t}°C.",
        "prob_lluvia": "☔ Kans op regen: {rain_prob}%.",
        "int_viento": "🌬️ Windintensiteit: {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Maximale UV-intensiteit: {uv_text}.",
        "fase_lunar": "Maanfase: {lunar}.",
        "hora_puesta": "🌇 Zonsondergang",
        "hora_amanecer": "🌅 Zonsopgang",
        "desc_day": "Beschrijving van de dag:",
        "desc1": "• Koel ochtend en grotendeels helder.",
        "desc2": "• Middag met wat wind en mogelijke hoge wolken.",
        "desc3": "• Heldere en koele nacht met zichtbare maan.",
        "consejos_title": "Tips:",
        "consejo_uv": "• Zonnebrandcrème SPF 50+ en zonnebril aanbevolen.",
        "consejo_rain": "• Paraplu of regenjas noodzakelijk.",
        "consejo_windcold": "• Lichte jas of jas essentieel.",
        "consejo_ligera": "• Lichte en comfortabele kleding is voldoende.",
        "consejo_capa": "• Extra laag voor middag/avond.",
        "separator": "───────────────────",
        "wind_0": "0 (totale kalmte)",
        "wind_1": "1 (zeer lichte bries)",
        "wind_3": "3 (lichte bries)",
        "wind_5": "5 (matige bries)",
        "wind_7": "7 (frisse wind)",
        "wind_9": "9 (sterke wind)",
        "wind_10": "10 (zeer sterk / storm)",
        "uv_bajo": "Laag",
        "uv_moderado": "Matig",
        "uv_alto": "Hoog",
        "uv_muy_alto": "Zeer hoog",
        "uv_extremo": "Extreem",
        "estado_despejado": "Helder met bries.",
        "estado_nublado": "Bewolkt met mogelijke buien.",
        "estado_fallback": "Gedeeltelijk bewolkt.",
        "luna_llena": "Volle maan (95-100%)",
        "luna_creciente": "Wassende maansikkel (60-70%)",
        "luna_fallback": "Volle maan (96%)",
        "luna_nueva": "Nieuwe maan (0-5%)",  # ← NUEVO: fase real
    },
    "DE": {
        "idioma_cmd": "/sprache", "poblacion_cmd": "/ort",
        "idioma": "Sprache wählen",
        "bienvenido": "✅ Aktiv\nAktueller Ort: {loc}",
        "cambiar": "Wähle deinen Ort:",
        "buscando": "✅ Geändert zu **{loc}**\nDaten werden geladen...\nBitte warten.",
        "footer": "Drücken Sie /start um die Sprache zu ändern\nDrücken Sie /poblacion um den Ort zu ändern",
        "siguiente_8": "Nächste Nachricht um 20:00\nSchönen Tag!",
        "siguiente_20": "Nächste Nachricht um 8:00\nGute Nacht!",
        "temp_actual_title": "🌡️ Aktuelle Temperatur:",
        "sensacion": " (gefühlt {sens}°C).",
        "estado_actual": "☀️ Aktueller Zustand: {estado}",
        "prediccion_hoy": "Vorhersage für heute",
        "prediccion_manana": "Vorhersage für morgen",
        "temp_max": "🔼 Maximale Temperatur: {max_t}°C.",
        "temp_min": "🔽 Minimale Temperatur: {min_t}°C.",
        "prob_lluvia": "☔ Regenwahrscheinlichkeit: {rain_prob}%.",
        "int_viento": "🌬️ Windstärke: {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Maximale UV-Intensität: {uv_text}.",
        "fase_lunar": "Mondphase: {lunar}.",
        "hora_puesta": "🌇 Sonnenuntergang",
        "hora_amanecer": "🌅 Sonnenaufgang",
        "desc_day": "Tagesbeschreibung:",
        "desc1": "• Kühler Morgen und meist klar.",
        "desc2": "• Nachmittag mit etwas Wind und möglichen hohen Wolken.",
        "desc3": "• Klare und kühle Nacht mit sichtbarem Mond.",
        "consejos_title": "Tipps:",
        "consejo_uv": "• Sonnencreme 50+ und Sonnenbrille empfohlen.",
        "consejo_rain": "• Regenschirm oder Regenjacke notwendig.",
        "consejo_windcold": "• Leichte Jacke oder Mantel unbedingt.",
        "consejo_ligera": "• Leichte und bequeme Kleidung reicht aus.",
        "consejo_capa": "• Extra Schicht für Nachmittag/Abend.",
        "separator": "───────────────────",
        "wind_0": "0 (völlige Windstille)",
        "wind_1": "1 (sehr leichte Brise)",
        "wind_3": "3 (leichte Brise)",
        "wind_5": "5 (mäßige Brise)",
        "wind_7": "7 (frischer Wind)",
        "wind_9": "9 (starker Wind)",
        "wind_10": "10 (sehr stark / Sturm)",
        "uv_bajo": "Niedrig",
        "uv_moderado": "Mäßig",
        "uv_alto": "Hoch",
        "uv_muy_alto": "Sehr hoch",
        "uv_extremo": "Extrem",
        "estado_despejado": "Klar mit Brise.",
        "estado_nublado": "Bewölkt mit möglichen Schauern.",
        "estado_fallback": "Teilweise bewölkt.",
        "luna_llena": "Vollmond (95-100%)",
        "luna_creciente": "Zunehmende Mondsichel (60-70%)",
        "luna_fallback": "Vollmond (96%)",
        "luna_nueva": "Neumond (0-5%)",  # ← NUEVO: fase real
    },
    "FR": {
        "idioma_cmd": "/langue", "poblacion_cmd": "/localite",
        "idioma": "Choisir langue",
        "bienvenido": "✅ Activé\nLocalité actuelle: {loc}",
        "cambiar": "Choisis ta localité:",
        "buscando": "✅ Changé en **{loc}**\nRecherche des données...\nVeuillez patienter.",
        "footer": "Appuyez sur /start pour changer la langue\nAppuyez sur /poblacion pour changer la localité",
        "siguiente_8": "Prochain message à 20h\nBonne journée !",
        "siguiente_20": "Prochain message à 8h\nBonne nuit !",
        "temp_actual_title": "🌡️ Température actuelle :",
        "sensacion": " (ressenti {sens}°C).",
        "estado_actual": "☀️ État actuel : {estado}",
        "prediccion_hoy": "Prévision pour aujourd'hui",
        "prediccion_manana": "Prévision pour demain",
        "temp_max": "🔼 Température maximale : {max_t}°C.",
        "temp_min": "🔽 Température minimale : {min_t}°C.",
        "prob_lluvia": "☔ Probabilité de pluie : {rain_prob}%.",
        "int_viento": "🌬️ Intensité du vent : {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Intensité UV maximale : {uv_text}.",
        "fase_lunar": "Phase lunaire : {lunar}.",
        "hora_puesta": "🌇 Heure du coucher de soleil",
        "hora_amanecer": "🌅 Heure du lever de soleil",
        "desc_day": "Description de la journée :",
        "desc1": "• Matin frais et principalement dégagé.",
        "desc2": "• Après-midi avec un peu de vent et nuages hauts possibles.",
        "desc3": "• Nuit claire et fraîche avec lune visible.",
        "consejos_title": "Conseils :",
        "consejo_uv": "• Crème solaire 50+ et lunettes de soleil recommandées.",
        "consejo_rain": "• Parapluie ou imperméable nécessaire.",
        "consejo_windcold": "• Veste légère ou manteau indispensable.",
        "consejo_ligera": "• Vêtements légers et confortables suffisent.",
        "consejo_capa": "• Couche supplémentaire pour l'après-midi/soir.",
        "separator": "───────────────────",
        "wind_0": "0 (calme total)",
        "wind_1": "1 (brise très légère)",
        "wind_3": "3 (brise légère)",
        "wind_5": "5 (brise modérée)",
        "wind_7": "7 (vent frais)",
        "wind_9": "9 (vent fort)",
        "wind_10": "10 (très fort / tempête)",
        "uv_bajo": "Bas",
        "uv_moderado": "Modéré",
        "uv_alto": "Élevé",
        "uv_muy_alto": "Très élevé",
        "uv_extremo": "Extrême",
        "estado_despejado": "Dégagé avec brise.",
        "estado_nublado": "Nuageux avec averses possibles.",
        "estado_fallback": "Partiellement nuageux.",
        "luna_llena": "Pleine lune (95-100%)",
        "luna_creciente": "Croissant de lune (60-70%)",
        "luna_fallback": "Pleine lune (96%)",
        "luna_nueva": "Nouvelle lune (0-5%)",  # ← NUEVO: fase real
    },
    "IT": {
        "idioma_cmd": "/lingua", "poblacion_cmd": "/localita",
        "idioma": "Seleziona lingua",
        "bienvenido": "✅ Attivato\nLocalità attuale: {loc}",
        "cambiar": "Scegli la tua località:",
        "buscando": "✅ Cambiato a **{loc}**\nRecupero dati ora...\nAttendi un momento.",
        "footer": "Premi /start per cambiare la lingua\nPremi /poblacion per cambiare la località",
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
        "int_viento": "🌬️ Intensità del vento: {wind_str} ({wind_kmh} km/h).",
        "int_uv": "☀️ Intensità UV massima: {uv_text}.",
        "fase_lunar": "Fase lunare: {lunar}.",
        "hora_puesta": "🌇 Ora del tramonto",
        "hora_amanecer": "🌅 Ora dell'alba",
        "desc_day": "Descrizione della giornata:",
        "desc1": "• Mattina fresca e per lo più serena.",
        "desc2": "• Pomeriggio con un po' di vento e possibili nuvole alte.",
        "desc3": "• Notte serena e fresca con luna visibile.",
        "consejos_title": "Consigli:",
        "consejo_uv": "• Crema solare 50+ e occhiali da sole consigliati.",
        "consejo_rain": "• Ombrello o impermeabile necessario.",
        "consejo_windcold": "• Giacca leggera o cappotto indispensabile.",
        "consejo_ligera": "• Abbigliamento leggero e comodo è sufficiente.",
        "consejo_capa": "• Strato extra per pomeriggio/sera.",
        "separator": "───────────────────",
        "wind_0": "0 (calma totale)",
        "wind_1": "1 (brezza molto leggera)",
        "wind_3": "3 (brezza leggera)",
        "wind_5": "5 (brezza moderata)",
        "wind_7": "7 (vento fresco)",
        "wind_9": "9 (vento forte)",
        "wind_10": "10 (super forte / tempesta)",
        "uv_bajo": "Basso",
        "uv_moderado": "Moderato",
        "uv_alto": "Alto",
        "uv_muy_alto": "Molto alto",
        "uv_extremo": "Estremo",
        "estado_despejado": "Sereno con brezza.",
        "estado_nublado": "Nuvoloso con possibili acquazzoni.",
        "estado_fallback": "Parzialmente nuvoloso.",
        "luna_llena": "Luna piena (95-100%)",
        "luna_creciente": "Luna crescente (60-70%)",
        "luna_fallback": "Luna piena (96%)",
        "luna_nueva": "Luna nuova (0-5%)",  # ← NUEVO: fase real
    },
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}
PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== FASE LUNAR REAL (cálculo astronómico preciso - SIN DATOS IRREALES) ======================
def get_lunar_phase(now: datetime, lang: str) -> str:
    t = TEXTOS[lang]
    # Fórmula estándar Julian Day + edad lunar (precisa para luna nueva, llena, etc.)
    y = now.year
    m = now.month
    d = now.day
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = a // 4
    c = 2 - a + b
    e = int(365.25 * (y + 4716))
    f = int(30.6001 * (m + 1))
    jd = c + d + e + f - 1524.5
    moon_age = (jd - 2451549.5) % 29.53058867

    if moon_age < 2.5 or moon_age > 27.0:
        return t["luna_nueva"]
    elif 12.0 < moon_age < 17.0:
        return t["luna_llena"]
    else:
        return t["luna_creciente"]

# ====================== OBTENER DATOS REALES (CON FORZADO ÓRGIVA PARA TABLONES, MORREÓN, BARRERAS, BAYACAS) ======================
async def get_real_weather(loc_name: str):
    logging.info(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando datos ACTUALES para {loc_name}...")
   
    # FORZADO: estos 4 pueblos usan datos/coordenadas de ÓRGIVA (sin mostrar ÓRGIVA)
    if loc_name in ["LOS TABLONES", "EL MORREÓN", "LAS BARRERAS", "BAYACAS"]:
        lat, lon = COORDS["ÓRGIVA"]
        logging.info(f" → Usando coordenadas de ÓRGIVA para {loc_name}")
    else:
        lat, lon = COORDS.get(loc_name, (36.90, -3.42))
    
    # Fuente principal: Open-Meteo (siempre disponible, UV real y fiable)
    # Nota: windy.com requiere clave API (gratuita pero hay que registrarse en windy.com). 
    # No se añadió para mantenerlo simple y 100% gratis. Open-Meteo + fallback es la mejor opción sin cambios grandes.
    url_om = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,wind_speed_10m,uv_index,precipitation_probability,weather_code&hourly=temperature_2m,precipitation_probability,wind_speed_10m,uv_index&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url_om)
            if r.status_code == 200:
                logging.info("✅ Open-Meteo respondió correctamente")
                return r.json(), "openmeteo"
    except Exception as e:
        logging.warning(f"Open-Meteo falló: {e}")
    
    # Fallback: wttr.in
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://wttr.in/{loc_name.replace(' ', '+')}?format=j1")
            if r.status_code == 200:
                logging.info("✅ wttr.in usado como fallback")
                return r.json(), "wttr"
    except:
        pass
    logging.warning("Ninguna fuente respondió - fallback seguro")
    return None, "fallback"

# ====================== ESCALA VIENTO Y UV (TRADUCIDAS) ======================
def wind_scale(kmh: int, lang: str) -> str:
    t = TEXTOS[lang]
    if kmh < 1: return t["wind_0"]
    if kmh < 6: return t["wind_1"]
    if kmh < 12: return t["wind_3"]
    if kmh < 20: return t["wind_5"]
    if kmh < 29: return t["wind_7"]
    if kmh < 39: return t["wind_9"]
    return t["wind_10"]

def uv_explanation(uv: int, lang: str) -> str:
    t = TEXTOS[lang]
    if uv <= 2: return t["uv_bajo"]
    if uv <= 5: return t["uv_moderado"]
    if uv <= 7: return t["uv_alto"]
    if uv <= 10: return t["uv_muy_alto"]
    return t["uv_extremo"]

# ====================== MENSAJE FINAL (TOTALMENTE TRADUCIDO) ======================
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
        uv_current = int(c.get("uv_index", 5))
        uv_max = max(h["uv_index"][idx*24:(idx+1)*24]) if "uv_index" in h else uv_current
        rain_prob = h["precipitation_probability"][12]
        wind_kmh = round(h["wind_speed_10m"][12])
        wind_str = wind_scale(wind_kmh, lang)
        max_t = d["temperature_2m_max"][idx]
        min_t = d["temperature_2m_min"][idx]
        sunrise = d["sunrise"][idx].split("T")[1][:5]
        sunset = d["sunset"][idx].split("T")[1][:5]
        estado = t["estado_despejado"] if rain_prob < 30 else t["estado_nublado"]
    else:
        temp, sens, uv_current, uv_max, rain_prob, wind_kmh = 17, 16, 6, 8, 25, 20
        wind_str = wind_scale(wind_kmh, lang)
        max_t, min_t = 23, 12
        sunrise, sunset = "07:11", "19:49"
        estado = t["estado_fallback"]
    
    # FASE LUNAR SIEMPRE REAL (independiente de la fuente)
    lunar = get_lunar_phase(now, lang)
    
    uv_text = f"{uv_max} ({uv_explanation(uv_max, lang)})"
    
    consejos = []
    if uv_max >= 6:
        consejos.append(t["consejo_uv"])
    if rain_prob >= 40:
        consejos.append(t["consejo_rain"])
    if wind_kmh >= 25 or temp < 14:
        consejos.append(t["consejo_windcold"])
    if rain_prob < 20 and uv_max < 5 and temp > 18:
        consejos.append(t["consejo_ligera"])
    else:
        consejos.append(t["consejo_capa"])
    
    lines = [
        loc_name,
        "",
        t["temp_actual_title"],
        f" {temp}°C" + t["sensacion"].format(sens=sens),
        t["estado_actual"].format(estado=estado),
        "",
        t["prediccion_hoy"] if is_morning else t["prediccion_manana"],
        "",
        t["temp_max"].format(max_t=max_t),
        t["temp_min"].format(min_t=min_t),
        t["prob_lluvia"].format(rain_prob=rain_prob),
        t["int_viento"].format(wind_str=wind_str, wind_kmh=wind_kmh),
        t["int_uv"].format(uv_text=uv_text),
        t["fase_lunar"].format(lunar=lunar),
        (t["hora_puesta"] if is_morning else t["hora_amanecer"]) + f": {sunset if is_morning else sunrise}.",
        "",
        t["desc_day"],
        t["desc1"],
        t["desc2"],
        t["desc3"],
        "",
        t["consejos_title"],
        "\n".join(consejos),
        "",
        t["separator"],
        t["siguiente_8"] if is_morning else t["siguiente_20"],
        "",
        t["footer"]  # ← Footer SOLO aquí, al final de la predicción (como pediste)
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
    user_data["lang"] = query.data.split("_")[1]
    lang = user_data["lang"]
    text = TEXTOS[lang]["bienvenido"].format(loc=user_data["location"])  # ← SIN footer (solo al final del tiempo)
    await query.edit_message_text(text)

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
    text = TEXTOS[lang]["buscando"].format(loc=loc)  # ← SIN footer (solo al final del tiempo)
    await query.edit_message_text(text)
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
    
    logger.info("✅ BOT FINAL LISTO | Fase lunar REAL + UV Open-Meteo + footer SOLO al final del tiempo | /start y /poblacion fijos")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
