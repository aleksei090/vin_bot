import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)
import requests
from dotenv import load_dotenv
import pytesseract
from PIL import Image

# Загрузка переменных окружения из файла .env
load_dotenv()
telegram_token = os.getenv('TELEGRAM_TOKEN')  # Telegram API-ключ

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
        "👋 Добро пожаловать! Пожалуйста, выберите способ ввода VIN-кода.",
        reply_markup=reply_markup
    )

# Обработка нажатия на кнопки
async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'upload_photo':
        await query.edit_message_text(text="Пожалуйста, загрузите фото с VIN-кодом.")
    elif query.data == 'enter_vin':
        await query.edit_message_text(text="Пожалуйста, введите VIN-код.")

# Обработка подтверждения VIN и продолжение работы
async def handle_confirmation(update: Update, context):
    user_reply = update.message.text.lower()
    vin_code = context.user_data.get('vin_code', None)
    
    if vin_code:
        if user_reply == "да":
            await update.message.reply_text("Теперь можете запросить нужную запчасть.")
        elif user_reply == "нет":
            await update.message.reply_text("Пожалуйста, введите корректный VIN-код.")
        else:
            await update.message.reply_text("Некорректный ответ. Пожалуйста, ответьте 'да' или 'нет'.")
    else:
        await update.message.reply_text("Пожалуйста, введите VIN-код для начала.")

# Обновленный обработчик текста
async def handle_text(update: Update, context):
    user_input = update.message.text.lower()

    # Если уже подтвержден VIN и запрашивается запчасть
    if 'vin_code' in context.user_data:
        await process_request(update, context)
    else:
        # Обработка VIN-кода
        vin_code = user_input.strip().upper()
        if len(vin_code) == 17:
            car_info = await asyncio.to_thread(get_car_info_by_vin, vin_code)
            if car_info:
                context.user_data['vin_code'] = vin_code
                await update.message.reply_text(
                    f"Ваш автомобиль: {car_info['make']} {car_info['model']}, {car_info['year']}, объем двигателя {car_info['engine_volume']} л. Верно? (да/нет)"
                )
            else:
                await update.message.reply_text("Не удалось получить информацию о машине.")
        else:
            await update.message.reply_text("Некорректный VIN-код. Попробуйте снова.")

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
        context.user_data['vin_code'] = vin_code
        await update.message.reply_text(f"Обнаружен VIN-код: {vin_code}. Запрос информации...")
        car_info = await asyncio.to_thread(get_car_info_by_vin, vin_code)
        if car_info:
            await update.message.reply_text(
                f"Ваш автомобиль: {car_info['make']} {car_info['model']}, {car_info['year']}, объем двигателя {car_info['engine_volume']} л. Верно? (да/нет)"
            )
        else:
            await update.message.reply_text("Не удалось получить информацию о машине.")
    else:
        await update.message.reply_text("Не удалось распознать VIN-код с фотографии. Пожалуйста, попробуйте снова.")

# Функция для запроса данных о машине (можно заменить на реальный источник данных)
def get_car_info_by_vin(vin_code):
    # В данном случае мы не делаем реальный запрос, а возвращаем пример данных
    return {
        "make": "Infiniti",
        "model": "QX56",
        "year": "2004",
        "engine_volume": "5.6"
    }

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

# Функция для поиска запчастей по VIN-коду через API
def get_parts_by_vin(vin_code):
    api_key = "5c52f6e4db91259648e10e3dfab5828e"
    url = f"http://partsapi.ru/api.php?method=getPartsbyVIN&key={api_key}&vin={vin_code}&type=oem"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            parts_data = response.json()
            return parts_data  # Возвращаем список запчастей
        else:
            logger.error(f"Ошибка API: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при запросе к API: {e}")
        return None

# Функция для обработки запросов на запчасти
async def process_request(update: Update, context):
    query = update.message.text.lower()
    vin_code = context.user_data.get('vin_code', None)

    if vin_code and 'масляный фильтр' in query:
        await update.message.reply_text(f"Ищем масляный фильтр для вашего автомобиля VIN: {vin_code}...")
        parts_data = get_parts_by_vin(vin_code)
        
        if parts_data and 'parts' in parts_data:
            message = "Вот несколько вариантов:\n"
            for part in parts_data['parts']:
                message += f"Название: {part['name']}, Артикул: {part['article']}, Цена: {part['price']} руб.\n"
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("Не удалось найти запчасти.")
    else:
        await update.message.reply_text("Пожалуйста, уточните ваш запрос.")

# Основная функция
def main():
    application = Application.builder().token(telegram_token).build()

    # Регистрация команд и обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Запуск бота
    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == '__main__':
    main()
