import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from vininfo import Vin
import requests

# Загрузка переменных окружения
load_dotenv()
telegram_token = os.getenv('TELEGRAM_TOKEN')  # Telegram API-ключ
prlg_api_key = os.getenv('PRLG_API_KEY')      # API-ключ pr-lg.ru

# Установка уровня логирования
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

# Обработка текста
async def handle_text(update: Update, context):
    user_input = update.message.text.strip()

    if 'awaiting_part' in context.user_data and context.user_data['awaiting_part']:
        await handle_part_input(update, context)
        return

    # Если VIN-код уже сохранен, переходим к запросу запчасти
    if 'vin_code' in context.user_data:
        if user_input.lower() in ['да', 'верно']:
            await update.message.reply_text(
                "Отлично! Пожалуйста, введите название или артикул необходимой запчасти."
            )
            context.user_data['awaiting_part'] = True
        else:
            await update.message.reply_text("Пожалуйста, введите корректный VIN-код.")
            context.user_data.clear()
        return

    # Обработка VIN-кода
    vin_code = user_input.upper()
    if len(vin_code) == 17:
        car_info = await asyncio.to_thread(decode_vin, vin_code)
        if car_info:
            context.user_data['vin_code'] = vin_code
            context.user_data['car_info'] = car_info
            await update.message.reply_text(
                f"Ваш автомобиль: {car_info}. Верно? (да/нет)"
            )
        else:
            await update.message.reply_text("Не удалось получить информацию о машине по VIN-коду.")
    else:
        await update.message.reply_text("Некорректный VIN-код. Пожалуйста, введите корректный VIN-код.")

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
        car_info = await asyncio.to_thread(decode_vin, vin_code)
        if car_info:
            context.user_data['car_info'] = car_info
            await update.message.reply_text(
                f"Ваш автомобиль: {car_info}. Верно? (да/нет)"
            )
        else:
            await update.message.reply_text("Не удалось получить информацию о машине по VIN-коду.")
    else:
        await update.message.reply_text("Не удалось распознать VIN-код с фотографии. Пожалуйста, попробуйте снова.")

# Функция для декодирования VIN-кода
def decode_vin(vin_code):
    try:
        vin = Vin(vin_code)
        vin_data = vin.parse()
        car_info = f"{vin_data['manufacturer']} {vin_data['model_year']}"
        return car_info
    except Exception as e:
        logger.error(f"Ошибка при декодировании VIN-кода: {e}")
        return None

# Функция для извлечения VIN-кода из фотографии
def extract_vin_from_photo(photo_path):
    try:
        image = Image.open(photo_path)
        text = pytesseract.image_to_string(image)
        vin_code = ''.join(filter(str.isalnum, text)).upper()
        if len(vin_code) == 17:
            return vin_code
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении VIN-кода из фото: {e}")
        return None

# Обработка запроса запчасти
async def process_request(update: Update, context):
    await update.message.reply_text(
        "Пожалуйста, введите название или артикул необходимой запчасти."
    )
    context.user_data['awaiting_part'] = True

# Обработка ввода запчасти
async def handle_part_input(update: Update, context):
    user_input = update.message.text.strip()
    context.user_data['awaiting_part'] = False

    # Здесь можно добавить логику для поиска артикула по названию запчасти
    # Пока предполагаем, что пользователь ввел артикул

    article = user_input.upper()
    # Поиск на pr-lg.ru по артикулу
    prlg_data = await asyncio.to_thread(get_prlg_data_by_article, article)
    if prlg_data:
        message = "Вот что удалось найти на pr-lg.ru:\n"
        for item in prlg_data:
            message += f"Название: {item['description']}, Цена: {item['price']} руб., Наличие: {item['quantity']}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("Не удалось найти запчасть на pr-lg.ru.")

# Функция для поиска на pr-lg.ru по артикулу
def get_prlg_data_by_article(article):
    api_key = prlg_api_key
    url = f"https://api.pr-lg.ru/search/items?secret={api_key}&article={article}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            prlg_data = response.json()
            return prlg_data.get('data', [])
        else:
            logger.error(f"Ошибка API pr-lg.ru: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при запросе к pr-lg.ru: {e}")
        return None

# Основная функция
def main():
    application = Application.builder().token(telegram_token).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск бота
    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == '__main__':
    main()
