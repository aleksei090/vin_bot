import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import openai
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')
telegram_token = os.getenv('TELEGRAM_TOKEN')

openai.api_key = openai_api_key

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Приветственное сообщение и запрос на способ ввода VIN
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("📸 Загрузить фото VIN-кода", callback_data='upload_photo')],
        [InlineKeyboardButton("✏️ Ввести VIN-код вручную", callback_data='enter_vin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать! Как вы хотите ввести VIN-код?\n"
        "📸 Загрузить фото или ✏️ Ввести вручную.",
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

# Обработка введенного VIN-кода и предоставление информации о машине
async def handle_text(update: Update, context):
    vin_code = update.message.text.strip().upper()
    logger.info(f"VIN-код получен: {vin_code}")

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

# Поиск запчастей по VIN и запросу
async def process_request(update: Update, context):
    vin_code = context.user_data.get('vin_code', None)
    if vin_code:
        query = update.message.text.lower()
        if "фильтр" in query:
            part_type = "масляный фильтр"
            await update.message.reply_text(f"Ищем {part_type} для автомобиля с VIN {vin_code}...")

            # Здесь будет вызов API для поиска запчастей
            parts = await search_parts(vin_code, part_type)

            # Предложение 4 вариантов запчастей
            if parts:
                keyboard = [[InlineKeyboardButton(f"{part['name']} - {part['price']} руб.", callback_data=part['article'])] for part in parts]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Вот что мы нашли для вас:", reply_markup=reply_markup)
            else:
                await update.message.reply_text("Не удалось найти запчасти. Попробуйте снова.")
        else:
            await update.message.reply_text("Пожалуйста, уточните, что именно вам нужно.")
    else:
        await update.message.reply_text("Пожалуйста, сначала введите VIN-код.")

# Запоминание выбранной запчасти
async def select_part(update: Update, context):
    query = update.callback_query
    article = query.data
    context.user_data['selected_part'] = article
    await query.answer()
    await query.edit_message_text(text=f"Вы выбрали запчасть с артикулом: {article}. Мы запомнили ваш выбор.")

# Функция для получения информации о машине
def get_car_info_by_vin(vin_code):
    # Здесь будет логика обращения к API для получения информации о машине
    return {
        "make": "Infiniti",
        "model": "QX56",
        "year": 2004,
        "engine_volume": 5.6
    }

# Функция для поиска запчастей
async def search_parts(vin_code, part_type):
    # Это место для вызова внешнего API, где будут возвращены варианты запчастей
    return [
        {"name": "Дешевый фильтр", "price": "500", "article": "12345"},
        {"name": "Средний фильтр 1", "price": "1500", "article": "12346"},
        {"name": "Средний фильтр 2", "price": "2000", "article": "12347"},
        {"name": "Оригинальный фильтр", "price": "3500", "article": "12348"}
    ]

# Основная функция
def main():
    application = Application.builder().token(telegram_token).build()

    # Регистрация команд и обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(select_part, pattern=r'\d+'))  # Для выбора запчасти
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_request))

    # Запуск бота
    logger.info("Бот запущен и готов к работе.")
    application.run_polling()

if __name__ == '__main__':
    main()
