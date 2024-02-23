import os
import json
import pandas as pd
from datetime import datetime
import telebot
from telebot import types
from decouple import config
from openpyxl import Workbook


TOKEN = config('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

bouquets_file = './data/bouquets.json'
lost_flowers_file = './data/lost_flowers.json'
report_file = './data/report.xlsx'
admin_users_file = './data/admin_users.json'

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


def save_data():
    """Сохраняет данные в JSON-файлы."""
    with open(bouquets_file, 'w', encoding='utf-8') as file:
        json.dump(bouquets, file, ensure_ascii=False)
    with open(lost_flowers_file, 'w', encoding='utf-8') as file:
        json.dump(lost_flowers, file, ensure_ascii=False)


def require_admin(func):
    """Декоратор для ограничения доступа к команде администраторам."""
    def wrapper(message, *args, **kwargs):
        if message.chat.id not in ADMIN_CHAT_ID:
            bot.reply_to(message, 'У вас нет прав доступа к этой команде.')
            return
        return func(message, *args, **kwargs)
    return wrapper


@bot.message_handler(commands=['start'])
def start_command(message):
    """Приветствует пользователя и объясняет назначение бота."""
    bot.reply_to(message, 'Привет! Этот бот для цветочного магазина. Используйте /help для справки.')


@bot.message_handler(commands=['help'])
def help_command(message):
    """Предоставляет информацию о командах бота."""
    if message.chat.id not in ADMIN_CHAT_ID:
        help_text = """Этот бот предназначен для учета цветов в цветочном магазине.
        Доступные команды:

        - /start: Поприветствует вас и расскажет о возможностях бота.
        - /help: Покажет эту справку.
        - /add_bouquet: Добавит новый букет в вашу базу данных.
        - /add_lost_flowers: Зарегистрирует пропавшие цветы.

        Пожалуйста, вводите команды в точности так, как они указаны.
        """
    else: 
        help_text = """Этот бот предназначен для учета цветов в цветочном магазине.
        Доступные команды:

        - /start: Поприветствует вас и расскажет о возможностях бота.
        - /help: Покажет эту справку.
        - /add_bouquet: Добавит новый букет в вашу базу данных.
        - /add_lost_flowers: Зарегистрирует пропавшие цветы.
        Тлько для администраторов
        - /report (только для администраторов): Сгенерирует отчет по букетам и пропавшим цветам.
        - /add_user: Добавить нового пользователя.
        - /del_user: удалить пользователя
        - /users_list: Список всех админов и пользователей

        Пожалуйста, вводите команды в точности так, как они указаны.
        """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['add_bouquet'])
def add_bouquet_command(message):
    """Инициирует процесс добавления нового букета."""
    chat_id = message.chat.id
    bouquet_key = datetime.now().isoformat()

    # Создает новый словарь букета для текущего чата
    bouquets.setdefault(chat_id, {})[bouquet_key] = {'price': 0, 'composition': {}}

    bot.reply_to(message, 'Введите стоимость нового букета:')
    bot.register_next_step_handler(message, get_bouquet_price, bouquet_key)


def get_bouquet_price(message, bouquet_key):
    """Получает цену букета и переходит к вводу состава."""
    chat_id = message.chat.id

    try:
        price = float(message.text)
        bouquets[chat_id][bouquet_key]['price'] = price
        bot.reply_to(message, 'Введите состав букета (формат: цвет1 - количество1, цвет2 - количество2):')
        bot.register_next_step_handler(message, get_composition, bouquet_key)
    except ValueError:
        bot.reply_to(message, 'Пожалуйста, введите корректную стоимость в виде числа.')
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

    composition_text = message.text
    composition_items = [item.strip() for item in composition_text.split(',')]

    for item in composition_items:
        try:
            flower, quantity = item.split('-')
            bouquets[chat_id][bouquet_key]['composition'][flower.strip()] = int(quantity)
        except ValueError:
            bot.reply_to(message, 'Некорректный формат ввода. Используйте формат: цвет1 - количество1, цвет2 - количество2.')

    bot.reply_to(message, 'Букет успешно добавлен!')
    save_data()

@bot.message_handler(commands=['add_lost_flowers'])
def add_lost_flowers_command(message):
    """Инициирует процесс добавления информации о пропавших цветах."""
    chat_id = message.chat.id
    timestamp = datetime.now().isoformat()

    # Создает новый словарь пропавших цветов для текущего чата
    lost_flowers.setdefault(chat_id, {})[timestamp] = {}
    
    bot.reply_to(message, 'Введите пропавшие цветы (формат: цвет1 - количество1, цвет2 - количество2):')
    bot.register_next_step_handler(message, get_lost_flowers, timestamp)
    


def get_lost_flowers(message, timestamp):
    """Получает информацию о пропавших цветах и сохраняет данные."""
    chat_id = message.chat.id

    lost_flowers_text = message.text
    lost_flowers_items = [item.strip() for item in lost_flowers_text.split(',')]

    for item in lost_flowers_items:
        try:
            parts = item.split('-')
            flower, quantity = parts[0].strip(), parts[1].strip()
            lost_flowers.setdefault(chat_id, {}).setdefault(timestamp, {})[flower] = int(quantity)
        except Exception:
            bot.reply_to(message, 'Некорректный формат ввода')
            bot.register_next_step_handler(message, get_lost_flowers, timestamp)
            return

    bot.reply_to(message, 'Пропавшие цветы успешно учтены!')
    save_data()


@bot.message_handler(commands=['report'])
@require_admin
def report_command(message):
    """Генерирует отчет и отправляет его администраторам."""
    try:
        writer = generate_report()
        writer.save()
        with open(report_file, 'rb') as file:
            bot.send_document(message.chat.id, file, caption='Отчет по букетам и пропавшим цветам')
    except Exception as e:
        bot.reply_to(message, f'Произошла ошибка при создании отчета: {e}')


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
    user_id = int(message.text)

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
        # Загружаем данные из JSON-файла
        with open(admin_users_file, 'r', encoding='utf-8') as file:
            users_data = json.load(file)

        # Добавляем нового пользователя
        new_user = {"chat_id": user_id, "name": username}
        users_data[role].append(new_user)

        # Сохраняем обновленные данные
        with open(admin_users_file, 'w', encoding='utf-8') as file:
            json.dump(users_data, file, ensure_ascii=False)

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
    with open(admin_users_file, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Находим пользователя в списке "admins"
    for user in data["users"]:
        if user["chat_id"] == user_id:
            data["users"].remove(user)
            break

    # Сохраняем обновленные данные
    with open(admin_users_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False)

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
    with open(admin_users_file, 'r', encoding='utf-8') as file:
        data = json.load(file)

    admins_text = get_users_info(data["admins"])
    users_text = get_users_info(data["users"])

    text = f"**Администраторы:**\n{admins_text}\n\n**Пользователи:**\n{users_text}"
    bot.reply_to(message, text, parse_mode='Markdown')


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
        text += f"* {user['name']} ({user['chat_id']})\n"

    return text


if __name__ == "__main__":
    bot.polling(none_stop=True)