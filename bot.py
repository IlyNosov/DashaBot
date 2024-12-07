import telebot

token = 'TOKEN'
bot = telebot.TeleBot(token)

whitelists = {}
users = {}


def is_admin(chat_id, user_id):
    member = bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        'Привет! Я помогу организовать белый список для вашего нового чата! Добавьте меня в группу, чтобы начать '
        'работу.'
    )


@bot.message_handler(content_types=['new_chat_members'])
def new_chat_members(message):
    global whitelists
    for user in message.new_chat_members:
        if user.id != bot.get_me().id:
            wl = whitelists.get(message.chat.id, [])
            username = f"@{user.username}" if user.username else user.first_name
            if username not in users:
                users[username] = user.id
            if username not in wl:
                if not is_admin(message.chat.id, bot.get_me().id):
                    bot.send_message(message.chat.id, f'Пользователь {username} не состоит в белом списке! Он был '
                                                      f'удален из чата, поскольку у меня нет прав администратора.')
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
    global whitelists
    if message.chat.id not in whitelists:
        whitelists[message.chat.id] = []
    if len(message.entities) < 2:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите @username пользователей, которых нужно добавить.')
        return
    mentions = [message.text[entity.offset:entity.offset + entity.length]
                for entity in message.entities if entity.type == 'mention']
    if not mentions:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите хотя бы одного пользователя для добавления.')
        return
    added = []
    skipped = []
    for username in mentions:
        if username not in whitelists[message.chat.id]:
            whitelists[message.chat.id].append(username)
            added.append(username)
        else:
            skipped.append(username)
    response = ''
    if added:
        response += f'Добавлены: {", ".join(added)}\n'
    if skipped:
        response += f'Пропущены (уже есть): {", ".join(skipped)}'
    bot.send_message(message.chat.id, response.strip())


@bot.message_handler(commands=['remove'])
def remove(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, 'Эта команда работает только в группах.')
        return
    if not is_admin(message.chat.id, message.from_user.id):
        bot.send_message(message.chat.id, 'У вас нет прав для изменения белого списка.')
        return
    if not is_admin(message.chat.id, bot.get_me().id):
        bot.send_message(message.chat.id, 'Для работы мне необходимы права администратора.')
        return
    global whitelists
    if message.chat.id not in whitelists or len(whitelists[message.chat.id]) == 0:
        bot.send_message(message.chat.id, 'Белый список для этой группы пуст.')
        return
    if len(message.entities) < 2:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите @username пользователей, которых нужно удалить.')
        return
    mentions = [message.text[entity.offset:entity.offset + entity.length]
                for entity in message.entities if entity.type == 'mention']
    if not mentions:
        bot.send_message(message.chat.id, 'Пожалуйста, укажите хотя бы одного пользователя для удаления.')
        return
    removed = []
    skipped = []
    for username in mentions:
        if username in whitelists[message.chat.id]:
            whitelists[message.chat.id].remove(username)
            if username in users:
                bot.kick_chat_member(message.chat.id, users[username])
            removed.append(username)
        else:
            skipped.append(username)
    response = ''
    if removed:
        response += f'Удалены: {", ".join(removed)}\n'
    if skipped:
        response += f'Пропущены (не найдены): {", ".join(skipped)}'
    bot.send_message(message.chat.id, response.strip())
    for username in removed:
        if username in users:
            bot.send_message(message.chat.id, f'Пользователь {username} удален из чата.')
            bot.kick_chat_member(message.chat.id, users[username])


@bot.message_handler(commands=['whitelist'])
def whitelist(message):
    if message.chat.type == 'private':
        bot.send_message(message.chat.id, 'Эта команда работает только в группах.')
        return
    global whitelists
    if message.chat.id not in whitelists or len(whitelists[message.chat.id]) == 0:
        bot.send_message(message.chat.id, 'Белый список для этой группы пуст.')
        return
    bot.send_message(message.chat.id, 'Список пользователей белого списка: ' +
                     ', '.join(whitelists[message.chat.id]))


bot.infinity_polling()