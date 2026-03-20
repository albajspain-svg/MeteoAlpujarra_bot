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

MODO_PRUEBA = False  # ← False = 8:00 y 20:00 reales

# ====================== LOCALIDADES ======================
COORDS = {
    "BAYACAS": (36.90, -3.42), "BUBIÓN": (36.90, -3.42), "CAPILEIRA": (36.90, -3.42),
    "EL MORREÓN": (36.90, -3.42), "LANJARÓN": (36.92, -3.48), "LAS BARRERAS": (36.90, -3.42),
    "LOS TABLONES": (36.90, -3.42), "ÓRGIVA": (36.90, -3.42), "PAMPANEIRA": (36.90, -3.42),
    "TREVÉLEZ": (36.90, -3.42), "UGÍJAR": (36.96, -3.43), "YEGEN": (36.90, -3.40),
    "MOTRIL": (36.75, -3.52), "ALMUÑÉCAR": (36.73, -3.69), "SALOBREÑA": (36.74, -3.59),
}
COASTAL_PUEBLOS = ["MOTRIL", "ALMUÑÉCAR", "SALOBREÑA"]

# ====================== TEXTOS COMPLETOS (TODOS LOS IDIOMAS) ======================
TEXTOS = {
    "ES": {
        "idioma_cmd": "/idioma", "poblacion_cmd": "/poblacion",
        "idioma": "Selecciona idioma",
        "bienvenido": "✅ Bot activado\nPoblación actual: {loc}",
        "cambiar": "Elige tu localidad:",
        "buscando": "✅ Cambiado a **{loc}**\nBuscando datos actualizados...\nEspere un momento.",
        "footer": "🌍 Cambiar idioma: /start\n📍 Cambiar localización: /poblacion\n🌡️ Conocer el tiempo actual: /actualizar",
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
        "actualizar_cmd": "Para conocer el tiempo actual pulse /actualizar",
    },
    "EN": {
        "idioma_cmd": "/language", "poblacion_cmd": "/location",
        "idioma": "Select language",
        "bienvenido": "✅ Activated\nCurrent location: {loc}",
        "cambiar": "Choose your location:",
        "buscando": "✅ Changed to **{loc}**\nFetching updated data...\nPlease wait.",
        "footer": "🌍 Change language: /start\n📍 Change location: /poblacion\n🌡️ Current weather: /actualizar",
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
        "actualizar_cmd": "To get the current weather press /actualizar",
    },
    "NL": {
        "idioma_cmd": "/taal", "poblacion_cmd": "/locatie",
        "idioma": "Selecteer taal",
        "bienvenido": "✅ Bot geactiveerd\nHuidige locatie: {loc}",
        "cambiar": "Kies je locatie:",
        "buscando": "✅ Gewijzigd naar **{loc}**\nGegevens ophalen...\nEen moment geduld.",
        "footer": "🌍 Taal wijzigen: /start\n📍 Locatie wijzigen: /poblacion\n🌡️ Huidig weer: /actualizar",
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
        "actualizar_cmd": "Om het huidige weer te krijgen druk op /actualizar",
    },
    "DE": {
        "idioma_cmd": "/sprache", "poblacion_cmd": "/standort",
        "idioma": "Sprache auswählen",
        "bienvenido": "✅ Bot aktiviert\nAktueller Standort: {loc}",
        "cambiar": "Wählen Sie Ihren Standort:",
        "buscando": "✅ Geändert zu **{loc}**\nDaten abrufen...\nBitte warten.",
        "footer": "🌍 Sprache ändern: /start\n📍 Standort ändern: /poblacion\n🌡️ Aktuelles Wetter: /actualizar",
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
        "actualizar_cmd": "Um das aktuelle Wetter zu erhalten, drücken Sie /actualizar",
    },
    "FR": {
        "idioma_cmd": "/langue", "poblacion_cmd": "/localisation",
        "idioma": "Sélectionnez la langue",
        "bienvenido": "✅ Bot activé\nLocalisation actuelle : {loc}",
        "cambiar": "Choisissez votre localisation :",
        "buscando": "✅ Changé en **{loc}**\nRécupération des données...\nVeuillez patienter.",
        "footer": "🌍 Changer de langue : /start\n📍 Changer de localisation : /poblacion\n🌡️ Météo actuelle : /actualizar",
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
        "actualizar_cmd": "Pour connaître le temps actuel appuyez sur /actualizar",
    },
    "IT": {
        "idioma_cmd": "/lingua", "poblacion_cmd": "/posizione",
        "idioma": "Seleziona lingua",
        "bienvenido": "✅ Bot attivato\nPosizione attuale: {loc}",
        "cambiar": "Scegli la tua località:",
        "buscando": "✅ Cambiato a **{loc}**\nRecupero dati aggiornati...\nAttendi un momento.",
        "footer": "🌍 Cambia lingua: /start\n📍 Cambia località: /poblacion\n🌡️ Meteo attuale: /actualizar",
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
        "actualizar_cmd": "Per conoscere il tempo attuale premi /actualizar",
    },
}

user_data = {"lang": "ES", "location": "ÓRGIVA"}
PUEBLOS_ALFA = ["BAYACAS", "BUBIÓN", "CAPILEIRA", "EL MORREÓN", "LANJARÓN", "LAS BARRERAS", "LOS TABLONES", "ÓRGIVA", "PAMPANEIRA", "TREVÉLEZ", "UGÍJAR", "YEGEN"]

# ====================== FASE LUNAR, VIENTO, UV, DESCRIPCIÓN, CONSEJOS ======================
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
    if uv <= 2: return f"{uv} ⚪ {t['uv_bajo']}"
    if uv <= 5: return f"{uv} 🟢 {t['uv_moderado']}"
    if uv <= 7: return f"{uv} 🟡 {t['uv_alto']}"
    if uv <= 10: return f"{uv} 🟠 {t['uv_muy_alto']}"
    return f"{uv} 🔴 {t['uv_extremo']}"

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
    if rain_prob < 20 and uv_max < 5 and temp > 18: cons.append(t["consejo_ligera"])
    else: cons.append(t["consejo_capa"])
    if loc_name in COASTAL_PUEBLOS: cons.append(t["consejo_coast"])
    else: cons.append(t["consejo_mountain"])
    return cons

# ====================== OBTENER DATOS ======================
async def get_real_weather(loc_name: str):
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

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,uv_index,precipitation_probability&hourly=temperature_2m,precipitation_probability,wind_speed_10m,uv_index&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=Europe/Madrid&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                humidity = data["current"].get("relative_humidity_2m", 60)
                return data, "openmeteo", sea_temp, humidity
    except: pass
    return None, "fallback", None, 60

# ====================== MENSAJE FINAL ======================
def build_weather_message(data, source, loc_name: str, lang: str, sea_temp=None, humidity=60):
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
        uv_max = max(h["uv_index"][idx*24:(idx+1)*24]) if "uv_index" in h else 5
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
    uv_text = uv_explanation(uv_max, lang)
    desc_lines = get_day_description(rain_prob, wind_kmh, max_t, lang, loc_name)
    consejos = get_consejos(uv_max, rain_prob, wind_kmh, temp, loc_name, lang)

    lines = [
        loc_name, "",
        t["temp_actual_title"],
        f" {temp}°C" + t["sensacion"].format(sens=sens),
        t["humedad"].format(hum=humidity),
        t["estado_actual"].format(estado=estado), "",
        t["prediccion_hoy"] if is_morning else t["prediccion_manana"], "",
        t["temp_max"].format(max_t=max_t),
        t["temp_min"].format(min_t=min_t),
        t["prob_lluvia"].format(rain_prob=rain_prob),
        t["int_viento"].format(wind_kmh=wind_kmh, wind_desc=wind_desc),
        t["int_uv"].format(uv_text=uv_text),
        (t["hora_puesta"] if is_morning else t["hora_amanecer"]) + f": {sunset if is_morning else sunrise}.",
        t["fase_lunar"].format(lunar=lunar),
    ]
    if sea_temp is not None:
        lines.append(t["sea_temp"].format(sea=sea_temp))
    lines.extend([
        "",
        "📅 " + t["desc_day"],
        *desc_lines,
        "",
        "💡 " + t["consejos_title"],
        *consejos,
        "",
        t["separator"],
        t["info_envios"],
        t["actualizar_cmd"],
        "",
        t["footer"]
    ])
    return "\n".join(lines)

# ====================== ENVÍO ======================
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    loc = user_data["location"]
    data, source, sea_temp, humidity = await get_real_weather(loc)
    text = build_weather_message(data, source, loc, lang, sea_temp, humidity)
    await context.bot.send_message(chat_id=CHAT_ID, text=text)
    logging.info(f"✅ Enviado | {loc} | fuente={source}")

async def weather_job(context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Job automático ejecutado a las {datetime.now().strftime('%H:%M:%S')}")
    await send_weather(context)

# ====================== COMANDOS ======================
async def cmd_actualizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_weather(context)

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
    text = TEXTOS[user_data["lang"]]["bienvenido"].format(loc=user_data["location"])
    await query.edit_message_text(text)
    await send_weather(context)

async def cmd_poblacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_data["lang"]
    kb = []
    row = []
    for p in PUEBLOS_ALFA:
        row.append(InlineKeyboardButton(p, callback_data=f"loc_{p}"))
        if len(row) == 3: kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("MOTRIL 🏖️", callback_data="loc_MOTRIL"),
               InlineKeyboardButton("ALMUÑÉCAR 🏖️", callback_data="loc_ALMUÑÉCAR"),
               InlineKeyboardButton("SALOBREÑA 🏖️", callback_data="loc_SALOBREÑA")])
    await update.message.reply_text(TEXTOS[lang]["cambiar"], reply_markup=InlineKeyboardMarkup(kb))

async def loc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_", 1)[1]
    user_data["location"] = loc
    text = TEXTOS[user_data["lang"]]["buscando"].format(loc=loc)
    await query.edit_message_text(text)
    await send_weather(context)

# ====================== MAIN ======================
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = ApplicationBuilder().token(TOKEN).build()

    async def post_init(application):
        await application.bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook borrado correctamente")

    app.post_init = post_init

    # COMANDOS ACTUALIZADOS CON ALIAS (ES + EN)
    app.add_handler(CommandHandler(["start", "idioma", "language"], cmd_idioma))
    app.add_handler(CommandHandler(["poblacion", "location"], cmd_poblacion))
    app.add_handler(CommandHandler(["actualizar", "update"], cmd_actualizar))

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(loc_callback, pattern="^loc_"))

    jq = app.job_queue
    if MODO_PRUEBA:
        jq.run_repeating(weather_job, interval=300, first=5)
    else:
        jq.run_daily(weather_job, time=time(hour=8, minute=0))
        jq.run_daily(weather_job, time=time(hour=20, minute=0))

    # Keep-alive
    jq.run_repeating(lambda c: logging.info("Keep-alive ping"), interval=840)

    logging.info("✅ BOT INICIADO | Todos idiomas completos | Footer con emojis + comandos simplificados | Aliases EN añadidos")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
