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
import requests
from bs4 import BeautifulSoup

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

# Функция для запроса к OpenAI
def get_car_info_by_vin(vin_code):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты опытный специалист по автомобильным запчастям."},
                {"role": "user", "content": f"Подскажи информацию об автомобиле с VIN-кодом {vin_code}."}
            ]
        )
        car_info = response.choices[0].message.content.strip()
        return {
            "make": "Infiniti",
            "model": "QX56",
            "year": "2004",
            "engine_volume": "5.6"
        }  # Это пример. На основе реального ответа вам нужно будет парсить информацию.
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

# Функция для поиска запчастей на emex.ru
def search_parts_on_emex(vin_code, query):
    try:
        url = f"https://www.emex.ru/catalogs/original/?vin={vin_code}&query={query}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Парсинг и поиск результатов
        parts = []
        for item in soup.find_all('div', class_='catalog-item'):
            name = item.find('div', class_='catalog-item-title').text
            price = item.find('div', class_='catalog-item-price').text
            article = item.find('div', class_='catalog-item-article').text
            parts.append({"name": name, "price": price, "article": article})
        
        return parts[:4]  # Вернуть 4 результата
    except Exception as e:
        logger.error(f"Ошибка при поиске запчастей: {e}")
        return []

# Функция для обработки запросов на запчасти
async def process_request(update: Update, context):
    query = update.message.text.lower()
    vin_code = context.user_data.get('vin_code', None)

    if vin_code:
        if 'масляный фильтр' in query:
            await update.message.reply_text(f"Ищем масляный фильтр для вашего автомобиля VIN: {vin_code}...")
            parts = await asyncio.to_thread(search_parts_on_emex, vin_code, 'масляный фильтр')
            
            if parts:
                message = "Вот несколько вариантов:\n"
                for part in parts:
                    message += f"{part['name']}, {part['price']}, артикул: {part['article']}\n"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("Не удалось найти запчасти на emex.ru.")
        else:
            await update.message.reply_text("Пожалуйста, уточните запрос.")
    else:
        await update.message.reply_text("VIN-код не найден. Введите VIN-код для продолжения.")

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
