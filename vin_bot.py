import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)
import openai
from dotenv import load_dotenv

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
        "👋 Добро пожаловать! Мы поможем вам найти запчасти для вашего автомобиля.\n"
        "Вы можете загрузить фото VIN-кода или ввести его вручную.",
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

# Обработка введенного VIN-кода
async def handle_text(update: Update, context):
    user_input = update.message.text.strip().lower()

    if len(user_input) == 17:  # Проверка на VIN-код
        vin_code = user_input.upper()
        logger.info(f"VIN-код получен: {vin_code}")
        await update.message.reply_text(f"Запрос информации по VIN: {vin_code}...")

        # Получение краткой информации о машине по VIN
        car_info = await asyncio.to_thread(ask_chatgpt_for_car_info, vin_code)
        if car_info:
            await update.message.reply_text(f"Ваш автомобиль: {car_info}. Верно ли это? (да/нет)")
        else:
            await update.message.reply_text("Не удалось получить данные. Попробуйте снова.")
    else:
        await handle_user_requests(user_input, update)

# Функция для обработки пользовательских запросов о запчастях
async def handle_user_requests(user_input, update: Update):
    if "масляный фильтр" in user_input or "фильтр" in user_input:
        part_info = await asyncio.to_thread(ask_chatgpt_for_part_info, user_input)
        if part_info:
            await update.message.reply_text(f"Совет по фильтру: {part_info}")
        else:
            await update.message.reply_text("Не удалось найти информацию по запросу.")
    else:
        await update.message.reply_text("Пожалуйста, уточните ваш запрос.")

# Функция для запроса краткой информации по VIN коду
def ask_chatgpt_for_car_info(vin_code):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты эксперт по автомобильным запчастям."},
                {"role": "user", "content": f"Какой автомобиль по VIN {vin_code}? Укажи марку, год и объем двигателя кратко."}
            ]
        )
        car_info = response.choices[0].message.content.strip()
        return car_info
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        return None

# Функция для получения информации о запчасти
def ask_chatgpt_for_part_info(part_query):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты специалист по автомобильным запчастям."},
                {"role": "user", "content": f"Найди информацию по запросу: {part_query}. Укажи лучший бренд, отзывы и артикул."}
            ]
        )
        part_info = response.choices[0].message.content.strip()
        return part_info
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        return None

# Основная функция
def main():
    application = Application.builder().token(telegram_token).build()

    # Регистрация команд и обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск бота
    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == '__main__':
    main()
