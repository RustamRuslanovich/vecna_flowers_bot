import json
import pandas as pd
import hashlib
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from decouple import config


TOKEN = config('TELEGRAM_BOT_TOKEN')

bouquets_file = 'bouquets.json'
lost_flowers_file = 'lost_flowers.json'
report_file = 'report.xlsx'

ADMIN_CHAT_ID =  [int(admin_id) for admin_id in config('ADMIN_CHAT_ID').split(',')]

# Проверка и создание файлов, если они отсутствуют
try:
    with open(bouquets_file, 'r', encoding='utf-8') as file:
        bouquets = json.load(file)
except FileNotFoundError:
    bouquets = {}

try:
    with open(lost_flowers_file, 'r', encoding='utf-8') as file:
        lost_flowers = json.load(file)
except FileNotFoundError:
    lost_flowers = {}

def save_data():
    """Сохраняет данные в соответствующие файлы."""
    with open(bouquets_file, 'w', encoding='utf-8') as file:
        json.dump(bouquets, file, ensure_ascii=False)

    with open(lost_flowers_file, 'w', encoding='utf-8') as file:
        json.dump(lost_flowers, file, ensure_ascii=False)

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    update.message.reply_text('Привет! Этот бот для цветочного магазина. Чтобы начать, используйте команду /help.')

def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help."""
    update.message.reply_text('Этот бот предназначен для учета цветов в цветочном магазине.')

def add_bouquet(update: Update, context: CallbackContext) -> int:
    """Начинает процесс добавления нового букета."""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if chat_id not in bouquets:
        bouquets[chat_id] = {}

    bouquet_key = datetime.now().isoformat()  # Используем isoformat времени в качестве ключа
    bouquets[chat_id][bouquet_key] = {'price': 0, 'composition': {}}

    update.message.reply_text('Введите стоимость нового букета:')
    context.user_data['bouquet_key'] = bouquet_key
    return 'GET_BOUQUET_PRICE'

def get_bouquet_price(update: Update, context: CallbackContext) -> int:
    """Обрабатывает ввод стоимости букета."""
    chat_id = update.message.chat_id
    bouquet_key = context.user_data.get('bouquet_key')  

    if not bouquet_key:
        update.message.reply_text('Что-то пошло не так. Пожалуйста, начните снова с команды /add_bouquet.')
        return ConversationHandler.END

    try:
        price = float(update.message.text)
        bouquets[chat_id][bouquet_key]['price'] = price

        update.message.reply_text('Введите состав букета (формат: цвет1 - количество1, цвет2 - количество2):')
        return 'GET_COMPOSITION'
    except ValueError:
        update.message.reply_text('Пожалуйста, введите корректную стоимость в виде числа.')
        return 'GET_BOUQUET_PRICE'

def get_composition(update: Update, context: CallbackContext) -> int:
    """Обрабатывает ввод состава букета."""
    chat_id = update.message.chat_id
    bouquet_key = context.user_data.get('bouquet_key')  

    if not bouquet_key:
        update.message.reply_text('Что-то пошло не так. Пожалуйста, начните снова с команды /add_bouquet.')
        return ConversationHandler.END

    composition_text = update.message.text
    composition_items = composition_text.split(',')

    for item in composition_items:
        try:
            flower, quantity = item.strip().split('-')
            bouquets[chat_id][bouquet_key]['composition'][flower.strip()] = int(quantity)
        except ValueError:
            update.message.reply_text('Некорректный формат ввода. Используйте формат: цвет1 - количество1, цвет2 - количество2.')

    update.message.reply_text('Букет успешно добавлен!')
    save_data()
    return ConversationHandler.END

def add_lost_flowers(update: Update, context: CallbackContext) -> int:
    """Начинает процесс добавления пропавших цветов."""
    chat_id = update.message.chat_id

    if chat_id not in lost_flowers:
        lost_flowers[chat_id] = {}

    timestamp = datetime.now().isoformat()  # Теперь используем isoformat времени
    lost_flowers[chat_id][timestamp] = {}

    update.message.reply_text('Введите пропавшие цветы (формат: цвет1 - количество1, цвет2 - количество2):')
    context.user_data['timestamp'] = timestamp  # Сохраняем timestamp в context.user_data
    return 'GET_LOST_FLOWERS'

def get_lost_flowers(update: Update, context: CallbackContext) -> int:
    """Обрабатывает ввод пропавших цветов."""
    chat_id = update.message.chat_id
    timestamp = context.user_data.get('timestamp')  

    if not timestamp:
        update.message.reply_text('Что-то пошло не так. Пожалуйста, начните снова с команды /add_lost_flowers.')
        return ConversationHandler.END

    lost_flowers_text = update.message.text
    lost_flowers_items = [item.strip() for item in lost_flowers_text.split(',')]

    for item in lost_flowers_items:
        parts = item.split('-')
        if len(parts) == 2:
            try:
                flower, quantity = parts[0].strip(), parts[1].strip()
                lost_flowers.setdefault(chat_id, {}).setdefault(timestamp, {})[flower] = int(quantity)
            except ValueError:
                update.message.reply_text('Некорректный формат ввода. Используйте формат: цвет1 - количество1, цвет2 - количество2.')

    update.message.reply_text('Пропавшие цветы успешно учтены!')
    save_data()
    return ConversationHandler.END



def generate_report() -> pd.ExcelWriter:
    """Генерирует отчет в формате Excel."""
    writer = pd.ExcelWriter(report_file, engine='xlsxwriter')

    # Добавляем данные о букетах в отчет
    for chat_id, bouquets_data in bouquets.items():
        df_bouquets = pd.DataFrame(bouquets_data).T
        df_bouquets.index.name = 'Bouquet ID'
        df_bouquets.to_excel(writer, sheet_name=f'Bouquets_{chat_id}')

    # Добавляем данные о пропавших цветах в отчет
    for chat_id, lost_flowers_data in lost_flowers.items():
        for timestamp, lost_flowers_item in lost_flowers_data.items():
            # Обрежем timestamp до максимальной длины 31 символ
            timestamp_shortened = timestamp[:10]

            df_lost_flowers = pd.DataFrame({timestamp_shortened: lost_flowers_item}).T
            df_lost_flowers.index.name = 'Lost Flowers'
            df_lost_flowers.to_excel(writer, sheet_name=f'Lost_Flowers_{timestamp_shortened}')

    return writer

def admin_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /admin - создание отчета для админов."""
    if update.message.chat_id not in ADMIN_CHAT_ID:
        update.message.reply_text('У вас нет прав доступа к этой команде.')
        return

    try:
        writer = generate_report()
        writer.save()
        update.message.reply_document(open(report_file, 'rb'), caption='Отчет по букетам и пропавшим цветам')
    except Exception as e:
        update.message.reply_text(f'Произошла ошибка при создании отчета: {e}')

def main() -> None:
    updater = Updater(TOKEN)

    dp = updater.dispatcher

    conv_handler_bouquet = ConversationHandler(
        entry_points=[CommandHandler('add_bouquet', add_bouquet)],
        states={
            'GET_BOUQUET_PRICE': [MessageHandler(Filters.text & (Filters.regex(r'^\d+(\.\d+)?$')), get_bouquet_price)],
            'GET_COMPOSITION': [MessageHandler(Filters.text & ~Filters.command, get_composition)],
        },
        fallbacks=[],
    )

    conv_handler_lost_flowers = ConversationHandler(
        entry_points=[CommandHandler('add_lost_flowers', add_lost_flowers)],
        states={
            'GET_LOST_FLOWERS': [MessageHandler(Filters.text & ~Filters.command, get_lost_flowers)],
        },
        fallbacks=[],
    )

    dp.add_handler(conv_handler_bouquet)
    dp.add_handler(conv_handler_lost_flowers)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("admin", admin_command))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()