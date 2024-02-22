import os
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
DATA_FILE_PATH = '.'

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

    # context.user_data.pop('bouquet_key', None)
    
    chat_id = update.message.chat_id
    # user_id = update.message.from_user.id

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
        print(float(update.message.text))
        price = float(update.message.text)
        bouquets[chat_id][bouquet_key]['price'] = price

        update.message.reply_text('Введите состав букета (формат: цвет1 - количество1, цвет2 - количество2):')
        return 'GET_COMPOSITION'
    
    except ValueError as e:
        # Печать сообщения об ошибке для отладки
        print(f"Ошибка при вводе стоимости букета: {e}")

        # Пожалуйста, введите корректную стоимость в виде числа.
        update.message.reply_text('Пожалуйста, введите корректную стоимость в виде числа.')
        return add_bouquet(update, context)

    
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
        except:
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
        # if len(parts) == 2:
        try:
            flower, quantity = parts[0].strip(), parts[1].strip()
            lost_flowers.setdefault(chat_id, {}).setdefault(timestamp, {})[flower] = int(quantity)
        except:
            update.message.reply_text('Некорректный формат ввода')
            return add_lost_flowers(update, context)
        # else:
        #     update.message.reply_text('Некорректный формат ввода. Используйте формат: цвет1 - количество1, цвет2 - количество2.')
        #     return add_lost_flowers(update, context)  # Возвращаемся к началу процесса

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
def load_admin_user_data():
    # Загрузка данных из файла
    if os.path.exists(DATA_FILE_PATH):
        with open(DATA_FILE_PATH, 'r') as file:
            data = json.load(file)
    else:
        data = {"admins": [], "users": []}
    return data

def save_user_admin_data(data):
    # Сохранение данных в файл
    with open(DATA_FILE_PATH, 'w') as file:
        json.dump(data, file, indent=2)


# Функция начала добавления пользователя
def select_type(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Выберите тип пользователя:\n1. Администратор\n2. Пользователь")
    return 'SELECT_TYPE'

# Функция добавления пользователя
def add_user(update: Update, context: CallbackContext) -> int:
    user_id = int(update.message.text)
    user_type = context.user_data['user_type']
    
    data = load_admin_user_data()
    
    user_data = {"user_id": user_id, "username": update.message.from_user.username}

    if user_type == "admins":
        data["admins"].append(user_data)
    elif user_type == "users":
        data["users"].append(user_data)
    
    save_data(data)
    update.message.reply_text(f"Пользователь с ID {user_id} успешно добавлен в список {user_type}.")
    
    return ConversationHandler.END

# Функция отмены операции
def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Операция отменена.')
    return ConversationHandler.END


#################################################################################

def main() -> None:
    updater = Updater(TOKEN)

    dp = updater.dispatcher

    conv_handler_bouquet = ConversationHandler(
        entry_points=[CommandHandler('add_bouquet', add_bouquet)],
        states={
            # 'GET_BOUQUET_PRICE': [MessageHandler(Filters.text & (Filters.regex(r'^\d+(\.\d+)?$') ), get_bouquet_price)],
            'GET_BOUQUET_PRICE': [MessageHandler(Filters.text & ~Filters.command, get_bouquet_price)],
            'GET_COMPOSITION': [MessageHandler(Filters.text & ~Filters.command, get_composition)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="my_conversation",
    )

    conv_handler_lost_flowers = ConversationHandler(
        entry_points=[CommandHandler('add_lost_flowers', add_lost_flowers)],
        states={
            'GET_LOST_FLOWERS': [MessageHandler(Filters.text & ~Filters.command, get_lost_flowers)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="my_conversation1",
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