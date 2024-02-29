import os
import json
import pandas as pd
from datetime import datetime
import telebot
from telebot import types
from decouple import config
from openpyxl import Workbook
from functools import partial
from typing import Dict, Any
import logging

# Константы
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
BOUQUETS_FILE = os.path.join(DATA_DIR, 'bouquets.json')
LOST_FLOWERS_FILE = os.path.join(DATA_DIR, 'lost_flowers.json')
REPORT_FILE = os.path.join(DATA_DIR, 'report.xlsx')
ADMIN_USERS_FILE = os.path.join(DATA_DIR, 'admin_users.json')
TOKEN = config('ADMIN_BOT_TOKEN')

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(os.path.join(BASE_DIR, 'bot.log'), encoding='utf-8', mode='w')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

class DataHandler:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        with open(self.file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

# Инициализация обработчиков данных
bouquets_handler = DataHandler(BOUQUETS_FILE)
lost_flowers_handler = DataHandler(LOST_FLOWERS_FILE)
admin_users_handler = DataHandler(ADMIN_USERS_FILE)

# Загрузка данных
bouquets = bouquets_handler.load()
lost_flowers = lost_flowers_handler.load()
admin_users = admin_users_handler.load()
ADMIN_CHAT_ID = [int(admin['chat_id']) for admin in admin_users['admins']]

def require_admin(func):
    """Декоратор для ограничения доступа к команде неадминистраторам."""
    def wrapper(message, *args, **kwargs):
        if message.chat.id not in ADMIN_CHAT_ID:
            bot.reply_to(message, 'У вас нет прав доступа к этой команде.')
            return
        return func(message, *args, **kwargs)
    return wrapper



@bot.message_handler(commands=['start'])
@require_admin
def start_command(message):
    bot.reply_to(message, 'Привет! Этот бот для админов цветочного магазина. Используйте /help для справки.')
    

def help_command(message):
    """Предоставляет информацию о командах бота."""
    # if message.chat.id not in ADMIN_CHAT_ID:
    help_text = """Этот бот предназначен для учета цветов в цветочном магазине.
        Доступные команды:

        - /start: Поприветствует вас и расскажет о возможностях бота.
        - /help: Покажет эту справку.
        - /report: Сгенерирует отчет по букетам и пропавшим цветам.
        - /add_user: Добавить нового пользователя.
        - /del_user: удалить пользователя
        - /users_list: Список всех админов и пользователей

        Пожалуйста, вводите команды в точности так, как они указаны.
        """
    bot.reply_to(message, help_text)
    
@bot.message_handler(commands=['report'])
@require_admin
def report_command(message):
    """Генерирует отчет и отправляет его администраторам."""
    try:
        writer = generate_report()
        writer.save()
        with open(REPORT_FILE, 'rb') as file:
            bot.send_document(message.chat.id, file, caption='Отчет по букетам и пропавшим цветам')
    except Exception as e:
        bot.reply_to(message, f'Произошла ошибка при создании отчета: {e}')


def generate_report() -> pd.ExcelWriter:
    """Генерирует отчет в формате Excel."""
    writer = pd.ExcelWriter(REPORT_FILE, engine='xlsxwriter')

    # Создадим таблицу с именами и chat_id
    data = admin_users_handler.load()

    id_names = pd.DataFrame(data['admins'] + data['users'])

    # Добавляем данные о букетах в отчет
    if bouquets:    
        df = pd.DataFrame(columns=['chat_id', 'date', 'price', 'Название цветка', 'Количество', 'sold_flag', 'seller_id'])
        
        # Проходим по данным и добавляем строки в DataFrame
        for chat_id_key, bouquets_info in bouquets.items():
            for bouquet_key, bouquet_data in bouquets_info.items():
                    price = bouquet_data['price']
                    composition = bouquet_data['composition']
                    sold_flag = bouquet_data['sold_flag']
                    seller_id = bouquet_data['seller_id']
                    # Создаем временный DataFrame для composition
                    temp_df = pd.DataFrame.from_dict(composition, orient='index', columns=['Количество'])
                    
                    # Добавляем колонку "Название цветка"
                    temp_df['Название цветка'] = temp_df.index
                    
                    # Добавляем остальные колонки
                    temp_df['chat_id'] = chat_id_key
                    temp_df['date'] = bouquet_key
                    temp_df['price'] = price
                    temp_df['sold_flag'] = sold_flag
                    temp_df['seller_id'] = seller_id
                    
                    # Объединяем временный DataFrame с основным
                    df = pd.concat([df, temp_df])

        # Сбрасываем мультииндекс для корректного отображения
        # df.reset_index(drop=True, inplace=True)
        timestamp_shortened = bouquet_key[:10]
        
        df = df.merge(id_names, on='chat_id', how='left') # Добавим имена в отчет
        
        id_names_ = id_names.rename({'name': 'seller_name'}, axis=1)
        
        df = df.merge(id_names_, left_on='seller_id',
                    right_on='chat_id', how='left', suffixes=('', '_')).drop(['chat_id_'], axis=1)

        df = df[['chat_id', 'name', 'date', 'price', 'Название цветка', 
                'Количество', 'sold_flag', 'seller_id', 'seller_name']]
        df.to_excel(writer, sheet_name=f'Bouquets_{timestamp_shortened}', index=False)
    else:
        pass

    # Добавляем данные о пропавших цветах в отчет
    if lost_flowers:
        df_lost = pd.DataFrame(columns=['chat_id', 'timestamp', 'Название цветка', 'Количество'])

        # Проходим по данным и добавляем строки в DataFrame
        for chat_id_key, timestamps_info in lost_flowers.items():
            for timestamp, flowers_info in timestamps_info.items():
                # Создаем временный DataFrame для цветов
                temp_df = pd.DataFrame.from_dict(flowers_info, orient='index', columns=['Количество'])
                
                # Добавляем колонку "Название цветка"
                temp_df['Название цветка'] = temp_df.index
                
                # Добавляем остальные колонки
                temp_df['chat_id'] = int(chat_id_key)
                temp_df['timestamp'] = timestamp
                
                # Объединяем временный DataFrame с основным
                df_lost = pd.concat([df_lost, temp_df])

        # Сбрасываем индекс для корректного отображения
        df_lost.reset_index(drop=True, inplace=True)
        timestamp_shortened = timestamp[:10]

        df_lost = df_lost.merge(id_names, on='chat_id', how='left') # Добавим имена в отчет
        df_lost = df_lost[['chat_id', 'name', 'timestamp', 'Название цветка', 'Количество']]
        df_lost.to_excel(writer, sheet_name=f'Lost_flowers_{timestamp_shortened}', index=False, index_label=['chat_id', 'timestamp'])
    else:
        pass
        
    return writer

######################################
@bot.message_handler(commands=['add_user'])
@require_admin
def add_user_command(message):
    """
    Добавляет нового пользователя.

    Args:
        message (telebot.types.Message): Telegram message object.

    Returns:
        None.
    """
    role = 'users'
    bot.reply_to(message, 'Введите ID пользователя:')
    bot.register_next_step_handler(message, process_user_id, role)


# @bot.message_handler(commands=['add_admin'])
# @require_admin
# def add_admin_command(message):
#     """
#     Добавляет нового админа.

#     Args:
#         message (telebot.types.Message): Telegram message object.

#     Returns:
#         None.
#     """
#     role = 'admins'
#     bot.reply_to(message, 'Введите ID пользователя:')
#     bot.register_next_step_handler(message, process_user_id, role)


def process_user_id(message, role):
    """
    Запрашивает имя пользователя.

    Args:
        message (telebot.types.Message): Telegram message object.

    Returns:
        None.
    """
    role = role
    user_id = message.text

    bot.reply_to(message, 'Введите имя пользователя:')
    bot.register_next_step_handler(message, process_admin_user_file, role, user_id)


def process_admin_user_file(message, role, user_id):
    """
    Сохраняет информацию о пользователе в JSON-файле.

    Args:
        message (telebot.types.Message): Telegram message object.
        user_id (int): ID пользователя Telegram.
        username (str): Имя пользователя.

    Returns:
        None.
    """
    username = message.text

    try:
        int(user_id)   ##### ПОТОМ ДОПИШИ НОРМАЛЬНО
        # Загружаем данные из JSON-файла
        users_data = admin_users_handler.load()

        # Добавляем нового пользователя
        new_user = {"chat_id": user_id, "name": username}
        users_data[role].append(new_user)

        # Сохраняем обновленные данные
        admin_users_handler.save(users_data)

        bot.reply_to(message, f'Пользователь {username} ({user_id}) добавлен с ролью {role}')
    except Exception as e:
        bot.reply_to(message, f'Ошибка при добавлении пользователя: {e}')


####################################################
@bot.message_handler(commands=['del_user'])
@require_admin
def del_user_command(message):
    """
    Удаляет пользователя из списка пользователей.

    Args:
        message (telebot.types.Message): Telegram message object.

    Returns:
        None.
    """
    bot.reply_to(message, 'Введите ID пользователя:')
    bot.register_next_step_handler(message, process_user_id_for_del)


def process_user_id_for_del(message):
    """
    Запрашивает подтверждение удаления пользователя.

    Args:
        message (telebot.types.Message): Telegram message object.

    Returns:
        None.
    """
    user_id = int(message.text)

    bot.reply_to(message, f'Вы уверены, что хотите удалить пользователя {user_id}?\nНапишите да или нет')
    bot.register_next_step_handler(message, confirm_user_deletion, user_id)


def confirm_user_deletion(message, user_id):
    """
    Удаляет пользователя из JSON-файла.

    Args:
        message (telebot.types.Message): Telegram message object.
        user_id (int): ID пользователя Telegram.

    Returns:
        None.
    """
    confirmation = message.text.lower()

    if confirmation in ('да', 'удалить'):
        try:
            delete_user(user_id)
            bot.reply_to(message, f'Пользователь {user_id} удален.')
        except Exception as e:
            bot.reply_to(message, f'Ошибка при удалении пользователя: {e}')
    else:
        bot.reply_to(message, 'Удаление пользователя отменено.')

def delete_user(user_id):
    """
    Удаляет пользователя из JSON-файла по chat_id.

    Args:
        chat_id (int): ID чата пользователя Telegram.

    Returns:
        None.
    """
    # Загружаем данные из JSON-файла
    data = admin_users_handler.load()

    # Находим пользователя в списке "admins"
    for user in data["users"]:
        if user["chat_id"] == str(user_id): ####### Исправить потом
            data["users"].remove(user)
            break

    # Сохраняем обновленные данные
    admin_users_handler.save(data)

@bot.message_handler(commands=['users_list'])
@require_admin
def show_users_command(message):
    """
    Отображает список всех пользователей.

    Args:
        message (telebot.types.Message): Telegram message object.

    Returns:
        None.
    """
    # Загружаем данные из JSON-файла
    try:
        data = admin_users_handler.load()

        admins_text = get_users_info(data["admins"])
        users_text = get_users_info(data["users"])

        text = f"**Администраторы:**\n{admins_text}\n\n**Пользователи:**\n{users_text}"
        bot.reply_to(message, text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f'Произошла ошибка при получении списка пользователей: {e}')


def get_users_info(users):
    """
    Формирует текст с информацией о пользователях.

    Args:
        users (list): Список пользователей.

    Returns:
        str: Текст с информацией о пользователях.
    """
    if not users:
        return "Список пуст."

    text = ""
    for user in users:
        text += f"- {user['name']} ({user['chat_id']})\n"

    return text

#####################################

if __name__ == "__main__":
    
    bot.polling(none_stop=True)