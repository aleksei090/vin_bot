import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)
import openai
from dotenv import load_dotenv
import pytesseract
from PIL import Image

# Загрузка переменных окружения из файла .env
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')  # OpenAI API-ключ
telegram_token = os.getenv('TELEGRAM_TOKEN')  # Telegram API-ключ

# Установка API-ключа OpenAI
openai.api_key = openai_api_key

# Установим уровень логирования для вывода ошибок
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Приветственное сообщение
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("📸 Загрузить фото VIN-кода", callback_data='upload_photo')],
        [InlineKeyboardButton("✏️ Ввести VIN-код вручную", callback_data='enter_vin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать в Мир аккумуляторов!\n\n🔧 Мы поможем вам найти запчасти для вашего автомобиля.\n\nВы можете:\n"
        "📸 Загрузить фото VIN-кода или ✏️ Ввести его вручную.\n"
        "Мы подберем для вас лучшие варианты запчастей.\n\nКак вам будет удобнее начать? 😊",
        reply_markup=reply_markup
    )

# Обработка нажатия на кнопки
async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'upload_photo':
        await query.edit_message_text(text="Пожалуйста, загрузите фото с VIN-кодом.")
        # Здесь можно добавить обработчик для получения фотографии
    elif query.data == 'enter_vin':
        await query.edit_message_text(text="Пожалуйста, введите VIN-код.")

# Обработка введенного VIN-кода
async def handle_text(update: Update, context):
    vin_code = update.message.text.strip().upper()
    logger.info(f"VIN-код получен: {vin_code}")

    if len(vin_code) == 17:  # Проверка длины VIN-кода
        await update.message.reply_text(f"Запрос информации для VIN: {vin_code}")

        # Вызов функции для получения информации
        car_info = await asyncio.to_thread(ask_chatgpt_for_car_info, vin_code)

        if car_info:
            await update.message.reply_text(f"Мы определили, что ваш автомобиль: {car_info}. Верно ли это? (да/нет)")
            # Здесь можно добавить обработку ответа пользователя (да/нет)
        else:
            await update.message.reply_text("Не удалось получить данные от сервера. Попробуйте снова.")
    else:
        await update.message.reply_text(f"Введен некорректный VIN-код: {vin_code}. Попробуйте снова.")

# Обработка фотографий
async def handle_photo(update: Update, context):
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"photos/{photo_file.file_id}.jpg"
    os.makedirs('photos', exist_ok=True)
    await photo_file.download_to_drive(photo_path)
    logger.info(f"Фото VIN-кода сохранено по пути: {photo_path}")

    # Извлечение VIN-кода из фотографии
    vin_code = await asyncio.to_thread(extract_vin_from_photo, photo_path)

    if vin_code:
        await update.message.reply_text(f"Обнаружен VIN-код: {vin_code}. Запрос информации...")
        car_info = await asyncio.to_thread(ask_chatgpt_for_car_info, vin_code)
        if car_info:
            await update.message.reply_text(f"Мы определили, что ваш автомобиль: {car_info}. Верно ли это? (да/нет)")
        else:
            await update.message.reply_text("Не удалось получить данные от сервера. Попробуйте снова.")
    else:
        await update.message.reply_text("Не удалось распознать VIN-код с фотографии. Пожалуйста, попробуйте снова.")

# Функция для запроса к OpenAI
def ask_chatgpt_for_car_info(vin_code):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты опытный специалист по автомобильным запчастям."},
                {"role": "user", "content": f"Подскажи информацию об автомобиле с VIN-кодом {vin_code}."}
            ]
        )
        car_info = response.choices[0].message.content.strip()
        return car_info
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        return None

# Функция для извлечения VIN-кода из фотографии
def extract_vin_from_photo(photo_path):
    try:
        image = Image.open(photo_path)
        text = pytesseract.image_to_string(image)
        vin_code = ''.join(filter(str.isalnum, text)).upper()
        if len(vin_code) >= 17:
            return vin_code[:17]
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении VIN-кода: {e}")
        return None

# Основная функция
def main():
    application = Application.builder().token(telegram_token).build()

    # Регистрация команд и обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))  # Добавлен обработчик фото

    # Запуск бота
    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == '__main__':
    main()
