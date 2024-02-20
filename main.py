import json
import pandas as pd
import hashlib
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from decouple import config


TOKEN = config('TELEGRAM_BOT_TOKEN')

bouquets_file = './data/bouquets.json'
lost_flowers_file = './data/lost_flowers.json'
report_file = './data/report.xlsx'

ADMIN_CHAT_ID = [int(admin_id) for admin_id in config('ADMIN_CHAT_ID').split(',')]

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
print('ABOBA')


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
    df = pd.DataFrame(columns=['chat_id', 'date', 'price', 'Название цветка', 'Количество'])

    # Проходим по данным и добавляем строки в DataFrame
    for chat_id, bouquets_info in bouquets.items():
        for bouquet_key, bouquet_data in bouquets_info.items():
            price = bouquet_data['price']
            composition = bouquet_data['composition']
            
            # Создаем временный DataFrame для composition
            temp_df = pd.DataFrame.from_dict(composition, orient='index', columns=['Количество'])
            
            # Добавляем колонку "Название цветка"
            temp_df['Название цветка'] = temp_df.index
            
            # Добавляем остальные колонки
            temp_df['chat_id'] = chat_id
            temp_df['date'] = bouquet_key
            temp_df['price'] = price
            
            # Объединяем временный DataFrame с основным
            df = pd.concat([df, temp_df])

    # Сбрасываем мультииндекс для корректного отображения
    # df.reset_index(drop=True, inplace=True)
    timestamp_shortened = bouquet_key[:10]
    df.to_excel(writer, sheet_name=f'Bouquets_{timestamp_shortened}', index=False)
    
    # Добавляем данные о пропавших цветах в отчет
    df_lost = pd.DataFrame(columns=['chat_id', 'timestamp', 'Название цветка', 'Количество'])

    # Проходим по данным и добавляем строки в DataFrame
    for chat_id, timestamps_info in lost_flowers.items():
        for timestamp, flowers_info in timestamps_info.items():
            # Создаем временный DataFrame для цветов
            temp_df = pd.DataFrame.from_dict(flowers_info, orient='index', columns=['Количество'])
            
            # Добавляем колонку "Название цветка"
            temp_df['Название цветка'] = temp_df.index
            
            # Добавляем остальные колонки
            temp_df['chat_id'] = chat_id
            temp_df['timestamp'] = timestamp
            
            # Объединяем временный DataFrame с основным
            df_lost = pd.concat([df_lost, temp_df])

    # Сбрасываем индекс для корректного отображения
    df_lost.reset_index(drop=True, inplace=True)
    timestamp_shortened = timestamp[:10]
    df_lost.to_excel(writer, sheet_name=f'Lost_flowers_{timestamp_shortened}', index=False, index_label=['chat_id', 'timestamp'])

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

############################################## ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ ##########################################
# def add_user(update: Update, context: CallbackContext) -> int:
#     """Обработчик команды /add_user (доступно только админам)."""
#     if update.message.chat_id not in ADMIN_CHAT_ID:
#         update.message.reply_text('Вы не являетесь администратором. Доступ запрещен.')
#         return ConversationHandler.END

#     update.message.reply_text('Теперь введите тип пользователя (admins или users) для добавления.')
#     context.user_data['stage'] = 1
#     return 1

# def handle_user(update: Update, context: CallbackContext) -> int:
#     """Обработчик ввода типа пользователя и имени."""
#     stage = context.user_data['stage']
#     user_input = update.message.text.lower()

#     if stage == 1:
#         context.user_data['user_type'] = user_input
#         update.message.reply_text(f'Теперь введите имя пользователя для добавления в категорию {user_input}.')
#     elif stage == 0:
#         user_type = context.user_data['user_type']
#         chat_id = update.message.chat_id

#         # Вызываем функцию добавления пользователя в файл
#         add_user_to_json('.', user_type, user_input, chat_id)

#         # Сбрасываем ожидание данных
#         del context.user_data['user_type']
#         update.message.reply_text(f"Пользователь {user_input} успешно добавлен в категорию {user_type}.")

#         return ConversationHandler.END

#     return stage

# def add_user_to_json(file_path, user_type, name, chat_id):
#     """Функция добавления пользователя в JSON-файл."""
#     # Загружаем текущие данные из файла
#     with open(file_path, 'r') as file:
#         data = json.load(file)

#     # Проверяем, существует ли ключ для данного типа пользователей
#     if user_type not in data:
#         data[user_type] = []

#     # Проверяем, что пользователь с таким chat_id не существует
#     if all(user['chat_id'] != chat_id for user in data[user_type]):
#         # Добавляем нового пользователя
#         data[user_type].append({
#             "name": name,
#             "chat_id": chat_id
#         })

#         # Записываем обновленные данные в файл
#         with open(file_path, 'w') as file:
#             json.dump(data, file, indent=2)

# def cancel(update: Update, context: CallbackContext) -> int:
#     """Обработчик команды /cancel."""
#     update.message.reply_text('Операция отменена.')
#     return ConversationHandler.END
#################################################################################

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

    # conv_handler_users = ConversationHandler(
    #     entry_points=[CommandHandler('start', start)],
    #     states={
    #         0: [CommandHandler('add_user', add_user)],
    #         1: [MessageHandler(Filters.text & ~Filters.command, handle_user)],
    #     },
    #     fallbacks=[CommandHandler('cancel', cancel)],
    # )

    dp.add_handler(conv_handler_bouquet)
    dp.add_handler(conv_handler_lost_flowers)
    # dp.add_handler(conv_handler_users)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("admin", admin_command))
    # dp.add_handler(CommandHandler("add_user", add_user))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()