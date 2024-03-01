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
TOKEN = config('TELEGRAM_BOT_TOKEN')

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
USER_CHAT_ID = [int(user['chat_id']) for user in admin_users['users']]

def require_admin(func):
    """Декоратор для ограничения доступа к команде неадминистраторам."""
    def wrapper(message, *args, **kwargs):
        if message.chat.id not in ADMIN_CHAT_ID:
            bot.reply_to(message, 'У вас нет прав доступа к этой команде.')
            return
        return func(message, *args, **kwargs)
    return wrapper

def require_user(func):
    """Декоратор для ограничения доступа к команде не юзерам."""
    def wrapper(message, *args, **kwargs):
        if message.chat.id not in USER_CHAT_ID + ADMIN_CHAT_ID:
            bot.reply_to(message, 'У вас нет прав доступа к этой команде.')
            return
        return func(message, *args, **kwargs)
    return wrapper


@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel_callback(call):
    """Обрабатывает нажатие кнопки "Отменить"."""
    chat_id = call.message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, 'Действие отменено.')
    
    
@bot.message_handler(commands=['start'])
@require_user
def start_command(message):
    # """Приветствует пользователя и объясняет назначение бота."""
    # markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # markup.add('Добавить букет')
    # markup.add('Добавить пропавшие цветы')
    # markup.add('Отчет')
    # bot.reply_to(message, 'Выберите действие:', reply_markup=markup)
    # a = telebot.types.ReplyKeyboardRemove()
    # bot.send_message(message.from_user.id, 'Что', reply_markup=a)
    bot.reply_to(message, 'Привет! Этот бот для цветочного магазина. Используйте /help для справки.')


@bot.message_handler(commands=['help'])
@require_user
def help_command(message):
    """Предоставляет информацию о командах бота."""
    help_text = """Этот бот предназначен для учета цветов в цветочном магазине.
    Доступные команды:

    - /start: Поприветствует вас и расскажет о возможностях бота.
    - /help: Покажет эту справку.
    - /add_bouquet: Добавит новый букет в вашу базу данных.
    - /add_lost_flowers: Зарегистрирует пропавшие цветы.
    - /sell_bouquet: Учтет проданный букет

    Пожалуйста, вводите команды в точности так, как они указаны.
    """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['add_bouquet'])
@require_user
def add_bouquet_command(message):
    """Инициирует процесс добавления нового букета."""
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    
    chat_id = message.chat.id
    bouquet_key = datetime.now().isoformat() ## Пока только время

    # Создает новый словарь букета для текущего чата
    bouquets.setdefault(chat_id, {})[bouquet_key] = {'price': 0, 'composition': {}}

    bot.reply_to(message, 'Введите стоимость нового букета:', reply_markup=keyboard)
    bot.register_next_step_handler(message, get_bouquet_price, bouquet_key)


def get_bouquet_price(message, bouquet_key):
    """Получает цену букета и переходит к вводу состава."""
    chat_id = message.chat.id
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)

    try:
        msg = '''Введите состав букета в формате \nцвет1 количество1 \nцвет2 количество2 \nи т.д.'''
        price = float(message.text.replace(',', '.'))
        bouquets[chat_id][bouquet_key]['price'] = price
        bot.reply_to(message, msg, reply_markup=keyboard)
        bot.register_next_step_handler(message, get_composition, bouquet_key)
    except ValueError:
        bot.reply_to(message, 'Пожалуйста, введите корректную стоимость в виде числа', reply_markup=keyboard)
        bot.register_next_step_handler(message, get_bouquet_price, bouquet_key)


def get_composition(message, bouquet_key):
    """
    Получает состав букета и сохраняет данные.

    Args:
        message (telebot.types.Message): Telegram message object.
        bouquet_key (str): Идентификатор букета.

    Returns:
        None.
    """
    chat_id = message.chat.id
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    
    composition_text = message.text
    composition_items = [item.strip() for item in composition_text.split('\n')]

    is_valid_composition = True

    for item in composition_items:
        try:
            flower, quantity = " ".join(item.split(' ')[:-1]).strip(), item.split(' ')[-1]
            assert flower != ''
            assert not any(char.isdigit() for char in flower)
            bouquets[chat_id][bouquet_key]['composition'][flower.strip()] = int(quantity)
            bouquets[chat_id][bouquet_key]['sold_flag'] = 0
            bouquets[chat_id][bouquet_key]['seller_id'] = ''
            bouquets[chat_id][bouquet_key]['sold_data'] = ''

        except Exception:
            is_valid_composition = False
            bot.reply_to(message, 'Некорректный формат ввода. \nИспользуйте формат: \nцвет1 количество1 \nцвет2 количество2 \nи т.д.', reply_markup=keyboard)
            bot.register_next_step_handler(message, get_composition, bouquet_key)
    
    if is_valid_composition:
        bot.reply_to(message, 'Букет успешно добавлен!')
        bouquets_handler.save(bouquets)


@bot.message_handler(commands=['add_lost_flowers'])
@require_user
def add_lost_flowers_command(message):
    """Инициирует процесс добавления информации о пропавших цветах."""
    chat_id = message.chat.id
    timestamp = datetime.now().isoformat()
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    
    # Создает новый словарь пропавших цветов для текущего чата
    lost_flowers.setdefault(chat_id, {})[timestamp] = {}
    
    bot.reply_to(message, 'Введите состав букета в формате \nцвет1 количество1 \nцвет2 количество2 \nи т.д.', reply_markup=keyboard)
    bot.register_next_step_handler(message, get_lost_flowers, timestamp)
    


def get_lost_flowers(message, timestamp):
    """Получает информацию о пропавших цветах и сохраняет данные."""
    chat_id = message.chat.id
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    
    lost_flowers_text = message.text
    lost_flowers_items = [item.strip() for item in lost_flowers_text.split('\n')]

    for item in lost_flowers_items:
        try:
            flower, quantity = " ".join(item.split(' ')[:-1]).strip(), item.split(' ')[-1]
            assert flower != ''
            assert not any(char.isdigit() for char in flower)
            # parts = item.split('-')
            # flower, quantity = parts[0].strip(), parts[1].strip()
            lost_flowers.setdefault(chat_id, {}).setdefault(timestamp, {})[flower] = int(quantity)
        except Exception:
            bot.reply_to(message, '''Некорректный формат ввода \nИспользуйте формат: \nцвет1 количество1 \nцвет2 количество2 \nи т.д.''', reply_markup=keyboard)
            bot.register_next_step_handler(message, get_lost_flowers, timestamp)
            return

    bot.reply_to(message, 'Пропавшие цветы успешно учтены!')
    lost_flowers_handler.save(lost_flowers)




@bot.message_handler(commands=['sell_bouquet', 'lost_bouquet'])
@require_user
def process_bouquet_command(message):
    chat_id = message.chat.id
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)

    command = message.text.split()[0].lower()
    
    if command == '/sell_bouquet':
        field = 'sold_flag'
        # message_text = 'Букет успешно продан!'
    elif command == '/lost_bouquet':
        field = 'is_lost'
        # message_text = 'Букет помечен как пропавший!'
    else:
        bot.send_message(chat_id, 'Неверная команда. Используйте /help для справки.')
        return

    bot.send_message(chat_id, f'Введите цену букета:', reply_markup=keyboard)
    bot.register_next_step_handler(message, partial(find_bouquets_by_price, field=field))

def find_bouquets_by_price(message, field):
    """Находит букеты с указанной ценой и выводит их список."""
    chat_id = message.chat.id
    
    keyboard = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    
    try:
        price = float(message.text.replace(',', '.'))
        matching_bouquets = []
        for chat_id_key, bouquets_info in bouquets.items():
            for timestamp, bouquet_data in bouquets_info.items():
                if  (bouquet_data["sold_flag"] == 0 and bouquet_data["is_lost"] == 0) and bouquet_data["price"] == price:
                    matching_bouquets.append((timestamp, bouquet_data))

        if matching_bouquets:
            display_bouquets_list(message, matching_bouquets, field)

        else:
            bot.send_message(chat_id, f'Букетов по цене {price} руб. не найдено.')
    except ValueError:
        bot.send_message(chat_id, 'Пожалуйста, введите корректную цену в виде числа.', reply_markup=keyboard)

def display_bouquets_list(message, matching_bouquets, field):
    """Выводит список букетов с указанной ценой.
        chat_id здесь совпадает с seller_chat_id"""
    chat_id = message.chat.id
    keyboard = types.InlineKeyboardMarkup()
    text = 'Выберите букет:\n\n'

    for i, (timestamp, bouquet_data) in enumerate(matching_bouquets, 1):
        composition_str = ', '.join(f'{k}: {v}' for k, v in bouquet_data["composition"].items())
        text += f'{i}. {bouquet_data["price"]} руб. ({timestamp})\nСостав: {composition_str}\n\n'

        callback_data = json.dumps((chat_id, matching_bouquets[i-1][0], field))
        keyboard.add(types.InlineKeyboardButton(i, callback_data=callback_data))

    cancel_button = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    keyboard.add(cancel_button)
    bot.send_message(chat_id, text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data)
def select_bouquet_by_number(call):
    """Обрабатывает выбор пользователя по номеру и помечает букет как проданный или пропавший."""
    call_data = json.loads(call.data)
    seller_chat_id = call_data[0]
    field = call_data[2]
    # message_text = call_data[3]

    date_time = json.loads(call.data)[1]

    for chat_id_key, bouquets_info in bouquets.items():
        for timestamp, bouquet_data in bouquets_info.items():
            if timestamp == date_time:
                bouquet_data[field] = 1
                bouquet_data['seller_id'] = seller_chat_id
                bouquet_data['sold_data'] = datetime.now().isoformat()

                bouquets_handler.save(bouquets)

                bot.send_message(seller_chat_id, "Букет учтен")


if __name__ == "__main__":

    bot.polling(none_stop=True)