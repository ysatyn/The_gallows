import asyncio
import json
import os
from dotenv import load_dotenv
import random
import sqlite3
import string
import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from wordfreq import word_frequency

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Логирование успешно настроено")

try:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    bot = AsyncTeleBot(token)
    logger.info("Токен бота успешно подключён")
except Exception as e:
    logger.critical(f"Ошибка при подключении к Telegram-боту: {e}")
    raise e

conn = sqlite3.connect("hanged_men.db", check_same_thread=False)
c = conn.cursor()

c.execute(  # Создание таблицы со словами у пользователей
    f"""CREATE TABLE IF NOT EXISTS user_words (
    user_id INTEGER PRIMARY KEY,  
    current_word TEXT,
    current_step INTEGER DEFAULT 0,
    guessed_letters TEXT DEFAULT "",
    wrong_letters TEXT DEFAULT "",
    attempts INTEGER DEFAULT 0
    )"""
)
c.execute(f"""CREATE TABLE IF NOT EXISTS unique_words (
word TEXT PRIMARY KEY UNIQUE ,
link TEXT)""")


def is_real(word, min_freq=0.000000000000000001): # проверка на реальность слова
    return word_frequency(word.lower(), 'ru') > min_freq

RUSSIAN_LETTERS = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")  # все русские буквы
stages = [ # стадии изображения повешенного человека
    """
      ---------
      |      |
      |     ☠️
      |     /|\\
      |      /\\
     ___

    """,
    """
      ---------
      |      |
      |     😭
      |     /|\\
      |      /
     ___

    """,
    """
      ---------
      |      |
      |     ☹️
      |     /|\\
      |      
     ___

    """,
    """
      ---------
      |      |
      |     😞
      |      |
      |      
     ___

    """,
    """
      ---------
      |      |
      |     🤨
      |     
      |      
     ___

    """,
    """
      ---------
      |      |
      |     
      |     
      |      
     ___

    """,
    """
      
      |      
      |     
      |     
      |      
     ___

    """,
    """
    
    """
]

def create_link(link):
    """
    Создаёт ссылку для начала игры с пользовательским словом
    :param link: Закодированное пользовательское слово
    :return: Ссылка
    """
    for_return = f"https://t.me/hang_yourself_bot?start={link}"
    return for_return


@bot.message_handler(commands=["start"])
async def start(message):
    """
    Простой обработчик команды /start
    :param message: Сообщение написанное пользователем
    """

    user_id = message.from_user.id
    command_parts = message.text.split(" ")
    if len(command_parts) > 1:  # проверяем есть ли ссылка на определённое слово
        link_code = command_parts[1]  # получаем ссылку

        c.execute(f"SELECT word FROM unique_words WHERE link = ?", (link_code,))  # достаём зашифрованное слово
        result = c.fetchone()
        if result is not None:  # если ссылка корректна и слово существует
            word = result[0]

            c.execute(f"SELECT user_id FROM user_words WHERE user_id = ?", (user_id,))
            user_exists = c.fetchone()
            if user_exists is not None:  # если юзер уже угадывает слово

                c.execute(f"""DELETE * FRON user_words WHERE user_id = {user_id}"""
                )  #  удаляем текущее слово пользователя

            c.execute(
                f"""INSERT INTO user_words (user_id, current_word) VALUES (?, ?)""",
                (user_id, word),
            )  # присваиваем пользователю новое слово
            conn.commit()
            empty_symbols = ""
            for _ in range(len(word)):  # создание пустого слова
                empty_symbols += "_ "
            await bot.send_message(message.chat.id,
                                   f"Вы начали игру по персональной ссылке. Ваше слово состоит из {len(word)} букв. Удачи!"
                                   f"\n{empty_symbols}")
        else:  # если ссылка неверна
            await bot.send_message(message.chat.id, "Неверная ссылка!")
    else:  # если пользователь просто отправил команду /start

        preview_path = os.path.join(os.path.dirname(__file__), "photos", "preview.jpg")  # создаём универсальный путь до файла
        with open(preview_path, "rb") as file:
            preview = file.read()  # загружаем фотографию для сообщения
        text = "Привет! Это бот по простой игре 'Виселица'. \nДля начала игры просто нажми команду /game, а чтобы получить помощь используй команду /help"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="Ссылка на исходный код бота", url="https://github.com/ysatyn/The_gallows"))  # ССЫЛКА НА ИСХОДНИК

        await bot.send_photo(user_id, preview, text, reply_markup=markup)


@bot.message_handler(commands=["game"])
async def game(message):
    """
    Обработчик команды /game
    Начинает новую игру
    :param message: Сообщение, которое написал пользователь
    """

    user_id = message.from_user.id
    if message.chat.type != "private":  # бот работает только в приватных чатах
        return
    c.execute(f"SELECT user_id FROM user_words WHERE user_id = {user_id}")
    result = c.fetchone()
    if result is not None:  # проверяем, угадывает ли сейчас пользователь слово или нет
        await bot.send_message(user_id, "Вы уже угадываете слово!")
        return
    with open("words.json", "r", encoding="utf-8") as f:  # загрузка файла с словами
        words = json.load(f)
    word = random.choice(words)  # выбираем случайное слово из файла
    empty_symbols = ""
    for i in range(len(word)):  # создаём пустое слово
        empty_symbols += "_ "
    text = f"Вам выпало слово из {len(word)} букв. Время угадывать!\n{empty_symbols}"
    c.execute(
        f"""INSERT INTO user_words (user_id, current_word, attempts) VALUES (?, ?, ?)""",
        (user_id, word, 0),
    )  # обновляем данные в таблице
    conn.commit()
    await bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["stop"])
async def stop(message):
    """
    Обработчик команды /stop
    Останавливает текущую игру и удаляет данные об угадываемом слове у пользователя
    :param message: Сообщение, которое написал пользователь
    """

    user_id = message.from_user.id
    if message.chat.type != "private":  # бот работает только в личном чате
        return
    c.execute(f"SELECT current_word FROM user_words WHERE user_id = {user_id}")
    result = c.fetchone()
    if result is None:  # если пользователь не угадывал слово
        await bot.send_message(user_id, "Вы не угадывали слово!")
        return
    word = result[0]
    c.execute(f"DELETE FROM user_words WHERE user_id = {user_id}")  # удаляем данные о слове пользователя
    conn.commit()
    await bot.send_message(user_id, f"Игра была прервана. Ваше слово было: {word}")


@bot.message_handler(commands=["help"])
async def help_command(message):
    """
    Обработчик команды /help
    Показывает информацию о боте и его возможностях
    :param message: Сообщение, которое написал пользователь
    """

    user_id = message.from_user.id
    help_text = """
    Привет! Я помогу тебе с игрой "Виселица".

    Команды:
    /start - начать новую игру
    /game - начать новую игру
    /guess - угадать слово целиком
    /stop - прервать текущую игру
    /make_link - создать ссылку на своё слово
    /help - показать это сообщение

    Чтобы угадать букву, просто отправь мне ее в личном чате.
    """
    await bot.send_message(user_id, help_text)


@bot.message_handler(commands=["make_link"])
async def make_link(message):
    """
    Обработчик команды /make_link
    Создает ссылку на своё слово
    :param message: Сообщение, которое написал пользователь
    """

    if len(message.text.split(' ')) != 2:  # проверяем что в тексте сообщения команда и только одно слово
        await bot.send_message(message.chat.id, "Используйте команду в формате /make_link {ваше слово}.")
        return
    user_id = message.from_user.id
    word = message.text.split(" ")[1].lower()   # получаем пользовательское слово
    if not is_real(word):  # проверяем существует ли такое слово
        await bot.send_message(user_id, "Используйте только реальные слова")
        return
    c.execute(f"""SELECT link FROM unique_words WHERE word = ?""", (word,))
    link = c.fetchone()
    if link is not None:  # если существует ссылка на такое слово
        link = create_link(link[0])
        await bot.send_message(user_id, f"Попробуй угадать слово которое я загадал! "
                                        f"\n<a href='{link}'>Перейти к боту</a>", parse_mode="HTML",
                               disable_web_page_preview=True)
        return
    letters = string.ascii_letters
    code = ''.join(random.choice(letters) for _ in range(20))  # делаем уникальный код для слова
    link = create_link(code)  # делаем ссылку на это слово
    c.execute(f"INSERT INTO unique_words (word, link) VALUES (?, ?)", (word, code))  # добавляем слово в каталог
    conn.commit()
    await bot.send_message(user_id, f"Попробуй угадать слово которое я загадал! "
                                    f"\n<a href='{link}'>Перейти к боту</a>", parse_mode="HTML",
                           disable_web_page_preview=True)

@bot.message_handler(commands=["guess"])
async def guess_word(message):
    """
    Обработчик команды /guess
    Позволяет пользователю угадать слово целиком
    :param message: Сообщение, которое написал пользователь
    """

    user_id = message.from_user.id
    c.execute(f"SELECT current_word FROM user_words WHERE user_id = {user_id}")
    result = c.fetchone()
    if result is None:  # если пользователь не угадывал слово, то предлагаем ему начать новую игру
        await bot.send_message(user_id, "Вы не угадывали слово! Чтобы начать игру введите команду /game")
        return

    current_word = result[0]
    text = message.text

    if len(text.split(" ")) != 2:  # проверяем формат сообщения
        await bot.send_message(user_id, "Используйте команду в формате /guess {слово}")
        return

    message_word = text.split(" ")[1]  # получаем слово, которое предложил пользователь в сообщении

    if message_word.lower() != current_word.lower():  # если угадал неправильно
        c.execute(f"""SELECT attempts FROM user_words WHERE user_id = {user_id}""")  # получаем количество попыток
        attempts = c.fetchone()[0]
        attempts += 2  # увеличиваем количество попыток
        if attempts <= len(stages):  # проверяем есть ли стадия для текущей попытки
            current_stage = stages[len(stages) - attempts - 1]
        else:  # если нет, берём последнюю
            current_stage = stages[0]

        if attempts >= 8:  # если пользователь исчерпал все попытки
            await bot.send_message(user_id, f"Вы исчерпали все попытки. Игра окончена. \n\n{current_stage}\n"
                                            f"Ваше слово было: {current_word}")
            c.execute(f"DELETE FROM user_words WHERE user_id = {user_id}")  # удаляем данные из таблицы
            conn.commit()
            return
        else:  # если у пользователя ещё остались попытки
            c.execute(f"""SELECT wrong_letters, guessed_letters FROM user_words WHERE user_id = {user_id}""")  # получаем правильные и неправильные буквы пользователя
            wrong_letters, guessed_letters = c.fetchone()

            new_word = ""
            for i in current_word: # составляем слово из угаданных букв
                if i in guessed_letters:
                    new_word += i + " "
                else:
                    new_word += "_ "
            list_of_wrong_letters = ""  # неправильные букквы
            for i in wrong_letters:
                list_of_wrong_letters += i.upper() + ", "  # строка с перечислением неправильных букв
            text = f"Слово {message_word.lower()} неправильный ответ! \n {new_word}\n\n{current_stage}\n\nНеправильно угаданные буквы: {list_of_wrong_letters}"
            c.execute(
                f"UPDATE user_words SET attempts = ? WHERE user_id = ?",
                (attempts, user_id),
            )  # обновляем попытки пользователя в таблице
            conn.commit()
            await bot.send_message(user_id, text)

    else:  # есди пользователь угадал слово
        c.execute(f"""DELETE FROM user_words WHERE user_id = {user_id}""")  # удаляем данные из таблицы
        conn.commit()

        await bot.send_message(user_id, f"Вы угадали слово! Ваше слово: {current_word.lower()}")


@bot.message_handler(func=lambda message: message.chat.type == "private")
async def guess_letter(message):
    """
    Обработчик бота для ответа на букву
    :param message: Сообщение, которое написал пользователь
    """

    letter = message.text.lower()
    if len(letter) > 1:  # если сообщения больше чем из одной буквы
        return
    user_id = message.from_user.id
    if message.chat.type != "private":  # бот работает только в приватных чатах
        return
    c.execute(f"SELECT current_word, wrong_letters, guessed_letters FROM user_words WHERE user_id = {user_id}")  # получаем текущее слово и буквы пользователя
    result = c.fetchone()

    if result is None:  # если пользователь не угадывал слово
        await bot.send_message(user_id, "Вы не угадывали слово! Чтобы начать игру введите команду /game")
        return
    word, wrong_letters, guessed_letters = result

    if letter not in RUSSIAN_LETTERS:  # если буква не из русского алфавита
        await bot.send_message(user_id, "Это не буква русского алфавита!")
        return

    if letter in guessed_letters or letter in wrong_letters:  # если пользователь уже пробовал эту букву
        await bot.send_message(user_id, "Вы уже пробовали эту букву!")
        return

    if letter in word:  # если пользователь угадал букву
        guessed_letters += letter  # прибавляем букву к списку угаданных

        new_word = ""
        count = 0
        for i in word:  # составляем слово
            if i in guessed_letters:
                new_word += i + " "
                count += 1
            else:
                new_word += "_ "
        c.execute(f"""SELECT attempts FROM user_words WHERE user_id = {user_id}""")
        attempts = int(c.fetchone()[0])

        current_stage = stages[len(stages) - attempts - 1]  # получаем стадию для текущей попытки

        list_of_wrong_letters = ""
        for i in wrong_letters:
            list_of_wrong_letters += i.upper() + ", "  # составляем строку с неправильно использованными буквами

        text = f"Вы угадали букву {letter}! \n {new_word}\n\n{current_stage}\n\nНеправильно угаданные буквы: {list_of_wrong_letters}"

        c.execute(
            f"UPDATE user_words SET guessed_letters = ? WHERE user_id = ?",
            (guessed_letters, user_id),
        )  # обновляем угаданные буквы
        conn.commit()

        if count == len(word):  # если пользователь полностью составил слово
            await bot.send_message(user_id, f"Вы угадали слово! Это было: {word}")
            c.execute(f"DELETE FROM user_words WHERE user_id = {user_id}")  # удаляем данные из таблицы
            conn.commit()
        else:
            await bot.send_message(user_id, text)
    else:  # если пользователь не угадал букву

        c.execute(f"""SELECT attempts FROM user_words WHERE user_id = {user_id}""")  # получаем количество попыток
        attempts = int(c.fetchone()[0])
        attempts += 1  # увеличиваем количество попыток
        wrong_letters += letter  # добавляем неугаданную букву к списку неправильных букв

        if attempts <= len(stages):  # проверяем есть ли стадия для текущей попытки
            current_stage = stages[len(stages) - attempts - 1]
        else:  # если нет, берём последнюю
            current_stage = stages[0]

        new_word = ""
        for i in word:  # составляем слово из угаданных букв
            if i in guessed_letters:
                new_word += i + " "
            else:
                new_word += "_ "

        list_of_wrong_letters = ""
        for i in wrong_letters:
            list_of_wrong_letters += i.upper() + ", "  # строка с перечислением неправильных букв

        text = f"Буквы {letter} нет в нашем слове.\n {new_word}\n\n{current_stage}\n\nНеправильно угаданные буквы: {list_of_wrong_letters}"
        c.execute(
            f"UPDATE user_words SET wrong_letters = ?, attempts = ? WHERE user_id = ?",
            (wrong_letters, attempts, user_id),
        )  # обновляем неправильные буквы и попытки пользователя в таблице
        conn.commit()

        if attempts >= 8:  # если пользователь исчерпал все попытки

            await bot.send_message(user_id, f"Вы исчерпали все попытки. Игра окончена. \n\n{current_stage}\n"
                                                f"Ваше слово было: {word}")
            c.execute(f"DELETE FROM user_words WHERE user_id = {user_id}")  # удаляем данные из таблицы
            conn.commit()

        else: # если у пользователя ещё остались попытки

            await bot.send_message(user_id, text)


async def main():
    logger.info("Запуск бота...")
    commands = [
        BotCommand("game", "Начать новую игру"),
        BotCommand("guess", "Угадать слово сразу"),
        BotCommand("stop", "Остановить текущую игру"),
        BotCommand("make_link", "Создать своё слово"),
        BotCommand("help", "Получить помощь")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота установлены")

    try:
        logger.info("Бот начинает работу")
        await bot.polling(non_stop=True)
    except Exception as Exc:
        logger.error(f"Произошла ошибка при работе бота: {Exc}")
    finally:
        logger.info("Бот завершил работу")


if __name__ == "__main__":
    asyncio.run(main())