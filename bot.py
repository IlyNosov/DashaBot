import os
import telebot
import psycopg2
from psycopg2.extras import RealDictCursor

token = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(token)

DATABASE_URL = os.getenv('DATABASE_URL')


def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def create_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS whitelists (
                    chat_id BIGINT NOT NULL,
                    username TEXT NOT NULL,
                    PRIMARY KEY (chat_id, username)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT NOT NULL PRIMARY KEY,
                    user_id BIGINT NOT NULL
                )
            ''')
            conn.commit()


create_tables()


def add_user_to_whitelist(chat_id, username):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO whitelists (chat_id, username) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (chat_id, username)
            )
            conn.commit()


def is_user_in_whitelist(chat_id, username):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM whitelists WHERE chat_id = %s AND username = %s",
                (chat_id, username)
            )
            return cur.fetchone() is not None


def add_user_to_database(username, user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, user_id) VALUES (%s, %s) ON CONFLICT (username) DO UPDATE SET user_id = EXCLUDED.user_id",
                (username, user_id)
            )
            conn.commit()


def is_admin(chat_id, user_id):
    member = bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']


def is_user_in_chat(chat_id, user_id):
    member = bot.get_chat_member(chat_id, user_id)
    return member.status in ['member', 'administrator', 'creator']


@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.type != 'private':
        bot.send_message(message.chat.id,
                         'Я работаю! Для подробностей пропиши /info')
        return
    bot.send_message(
        message.chat.id,
        'Привет! Я помогу организовать белый список для вашего нового чата! '
        'Добавьте меня в группу, чтобы начать работу.'
    )


def is_bot(chat_id, user_id):
    member = bot.get_chat_member(chat_id, user_id)
    return member.status in ['bot']


@bot.message_handler(content_types=['new_chat_members'])
def new_chat_members(message):
    for user in message.new_chat_members:
        if user.id == bot.get_me().id:
            continue
        username = f"@{user.username}" if user.username else user.first_name
        add_user_to_database(username, user.id)
        if is_admin(message.chat.id, user.id) or is_bot(message.chat.id, user.id):
            continue
        if not is_user_in_whitelist(message.chat.id, username):
            if not is_admin(message.chat.id, bot.get_me().id):
                bot.send_message(message.chat.id,
                                 f'Пользователь {username} не состоит в белом списке! '
                                 f'Он не был удален из чата, поскольку у меня нет прав администратора.')
                return
            bot.kick_chat_member(message.chat.id, user.id)
            bot.send_message(message.chat.id, f'Пользователь {username} удален, так как он не в белом списке.')


@bot.message_handler(commands=['add'])
def add(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, 'Эта команда работает только в группах.')
        return
    if not is_admin(message.chat.id, message.from_user.id):
        bot.send_message(message.chat.id, 'У вас нет прав для изменения белого списка.')
        return
    if len(message.entities) < 2:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите @username пользователей, которых нужно добавить.')
        return
    mentions = [message.text[entity.offset:entity.offset + entity.length] for entity in message.entities if
                entity.type == 'mention']
    if not mentions:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите хотя бы одного пользователя для добавления.')
        return
    added = []
    skipped = []
    for username in mentions:
        if username == '@' + bot.get_me().username:
            continue
        if not is_user_in_whitelist(message.chat.id, username):
            add_user_to_whitelist(message.chat.id, username)
            added.append(username)
        else:
            skipped.append(username)
    response = ''
    if added:
        response += f'Добавлены: {", ".join(added)}\n'
    if skipped:
        response += f'Пропущены: {", ".join(skipped)}'
    bot.send_message(message.chat.id, response.strip())


@bot.message_handler(commands=['remove'])
def remove(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, 'Эта команда работает только в группах.')
        return
    if not is_admin(message.chat.id, message.from_user.id):
        bot.send_message(message.chat.id, 'У вас нет прав для изменения белого списка.')
        return
    if len(message.entities) < 2:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите @username пользователей, которых нужно удалить.')
        return
    mentions = [message.text[entity.offset:entity.offset + entity.length] for entity in message.entities if
                entity.type == 'mention']
    if not mentions:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите хотя бы одного пользователя для удаления.')
        return
    removed = []
    skipped = []
    kicked = False
    for username in mentions:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM whitelists WHERE chat_id = %s AND username = %s",
                            (message.chat.id, username))
                user = cur.fetchone()
                cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                user_id = cur.fetchone()['user_id']
                if user and not is_admin(message.chat.id, user_id):
                    cur.execute("DELETE FROM whitelists WHERE chat_id = %s AND username = %s",
                                (message.chat.id, username))
                    conn.commit()
                    if is_admin(message.chat.id, bot.get_me().id) and is_user_in_chat(message.chat.id, user_id):
                        bot.kick_chat_member(message.chat.id, user_id)
                        kicked = True
                    removed.append(username)
                else:
                    skipped.append(username)
    response = ''
    if removed:
        response += f'Удалены: {", ".join(removed)}\n'
    if skipped:
        response += f'Пропущены: {", ".join(skipped)}'
    if not is_admin(message.chat.id, bot.get_me().id) and removed and kicked:
        response += '\n\nПользователи не были удалены из чата, так как у меня нет прав администратора.'
    bot.send_message(message.chat.id, response.strip())


@bot.message_handler(commands=['list'])
def whitelist(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, '*Эта команда работает только в группах.*', parse_mode='Markdown')
        return
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT username FROM whitelists WHERE chat_id = %s", (message.chat.id,))
                users = cur.fetchall()
    except Exception as e:
        bot.send_message(message.chat.id, f'⚠️ *Ошибка базы данных:* {e}', parse_mode='Markdown')
        return
    if not users:
        bot.send_message(message.chat.id, '_Белый список для этой группы пуст._', parse_mode='Markdown')
        return
    user_list = ', '.join(user['username'] for user in users)
    bot.send_message(message.chat.id, f'*Список пользователей белого списка:*', parse_mode='Markdown')
    bot.send_message(message.chat.id, user_list)


@bot.message_handler(commands=['info'])
def info(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, '*Эта команда работает только в группах.*', parse_mode='Markdown')
        return
    admin_info = 'Для полноценной работы мне необходимо быть *администратором* группы.'
    if is_admin(message.chat.id, bot.get_me().id):
        admin_info = 'Я *администратор* группы и могу удалять пользователей из чата.'
    bot.send_message(
        message.chat.id,
        '*Я помогаю организовать белый список пользователей канала!*\n\n'
        '*Доступные команды:*\n'
        '/add - _добавить пользователя в белый список_\n'
        '/remove - _удалить пользователя из белого списка_\n'
        f'/list - _показать список пользователей белого списка_\n\n {admin_info}',
        parse_mode='Markdown')


bot.infinity_polling()
