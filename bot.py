import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- Logging ----------------
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------- Configuración ----------------
TOKEN = "TU_BOT_TOKEN_AQUI"
CHAT_ID = "TU_CHAT_ID_AQUI"
WEATHER_URL = "https://wttr.in/?format=j1"

# ---------------- Scheduler ----------------
scheduler = AsyncIOScheduler()

# ---------------- Función de parseo de clima ----------------
def parse_weather(data):
    """
    Devuelve el mensaje de clima en 5 idiomas.
    Si no existe current_condition, toma la última hora con datos.
    Incluye mañana y tarde, UV y probabilidad de lluvia.
    """
    try:
        # Tomar current_condition o última hora
        if "current_condition" in data and len(data["current_condition"]) > 0:
            curr = data["current_condition"][0]
        else:
            # Buscar última hora con datos
            weather_today = data.get("weather", [])
            if weather_today and len(weather_today[0].get("hourly", [])) > 0:
                curr = weather_today[0]["hourly"][-1]
            else:
                return "❌ No se pudo obtener información del clima."

        temp_c = curr.get("temp_C", curr.get("tempC", "N/A"))
        uv = curr.get("uvIndex", "N/A")
        rain = curr.get("chanceofrain", "N/A")

        # Predicción mañana y tarde
        forecast_msg = ""
        weather_today = data.get("weather", [])
        if weather_today:
            hourly = weather_today[0].get("hourly", [])
            if len(hourly) >= 2:
                forecast_msg = (
                    f"\n🌅 Mañana: {hourly[0].get('tempC','N/A')}°C, "
                    f"{hourly[0].get('chanceofrain','N/A')}% lluvia"
                    f"\n🌇 Tarde: {hourly[1].get('tempC','N/A')}°C, "
                    f"{hourly[1].get('chanceofrain','N/A')}% lluvia"
                )

        # Mensaje en 5 idiomas
        message = (
            f"🌤️ Clima actual:\n"
            f"🇪🇸 ESP: Temp {temp_c}°C, UV {uv}, Lluvia {rain}%{forecast_msg}\n"
            f"🇬🇧 EN: Temp {temp_c}°C, UV {uv}, Rain {rain}%{forecast_msg}\n"
            f"🇫🇷 FR: Temp {temp_c}°C, UV {uv}, Pluie {rain}%{forecast_msg}\n"
            f"🇩🇪 DE: Temp {temp_c}°C, UV {uv}, Regen {rain}%{forecast_msg}\n"
            f"🇳🇱 NL: Temp {temp_c}°C, UV {uv}, Regen {rain}%{forecast_msg}"
        )
        return message
    except Exception as e:
        logging.error(f"Error parseando clima: {e}")
        return "❌ Error procesando la información del clima."

# ---------------- Función de envío de clima ----------------
async def send_weather(context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el clima y lo envía al chat."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(WEATHER_URL)
            data = resp.json()
        text = parse_weather(data)
        await context.bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        logging.error(f"Error enviando clima: {e}")
        await context.bot.send_message(chat_id=CHAT_ID, text="❌ Error obteniendo clima.")

# ---------------- Comandos ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot iniciado.\n"
        "Envía /clima para obtener el clima actual.\n"
        "Clima automático cada 5 minutos activado."
    )

async def weather_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para enviar clima manualmente."""
    await send_weather(context)

# ---------------- Función principal ----------------
async def main():
    # Limpiar sesiones antiguas
    print("🔥 Sesiones antiguas limpiadas")

    # Crear aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clima", weather_now))

    # Scheduler cada 5 minutos
    scheduler.add_job(lambda: asyncio.create_task(send_weather(app.bot)), 'interval', minutes=5)
    scheduler.start()

    # Iniciar bot
    print("Bot corriendo limpio")
    await app.run_polling()

# ---------------- Ejecutar ----------------
if __name__ == "__main__":
    asyncio.run(main())
