import logging
import sqlite3
import feedparser
from googletrans import Translator
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from datetime import timedelta
import pytz

# === НАСТРОЙКИ ===
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL")
SUPPORT_LINK = "SUPPORT"

# === Telegram бот ===
bot = Bot(token=TOKEN)

# === Переводчик ===
translator = Translator()

# === БД для хранения уже отправленных новостей ===
conn = sqlite3.connect("news.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS posted_links (link TEXT, timestamp DATETIME)")
conn.commit()

# === Переменные ===
last_ad_time = datetime.now(pytz.UTC) - timedelta(days=4)

# === RSS источники ===
rss_feeds = [
    "https://www.ign.com/articles/rss",
    "https://www.gamespot.com/feeds/mashup/",
    "https://www.polygon.com/rss/index.xml",
    "https://www.playground.ru/news",
    "https://stopgame.ru/news",
    "https://www.goha.ru/videogames",
    "https://gameguru.ru/articles/rubrics_news",
    "https://vkplay.ru/media/",
    "https://cubiq.ru/news/"
]

# === Перевод текста ===
def translate_text(text):
    try:
        return translator.translate(text, src='en', dest='ru').text
    except:
        return text  # если перевод не сработает, оставим как есть

# === Отправка рекламы ===
def send_advertisement():
    global last_ad_time
    time_diff = datetime.now(pytz.UTC) - last_ad_time
    if time_diff.total_seconds() < 3 * 24 * 60 * 60:
        logging.info(f"Реклама ещё не отправлена. Осталось {3 * 24 * 60 * 60 - time_diff.total_seconds()} секунд.")
        return

    # Полный рекламный текст (вся инфа идёт в caption под фото)
    ad_caption = (
        "<b>————————————РЕКЛАМА——————————————</b>\n\n"
        "Хэй, тут есть один канал, там чел выкладывает свой life и делает розыгрыши.\n"
        "Подписывайтесь на него и выигрывайте в розыгрышах."
    )

    # Ссылка на картинку (можно с PostImg или другой хостинг, главное — прямой URL к изображению)
    ad_image_url = "https://i.postimg.cc/CxwC7B8R/forestroad.jpg"

    # Кнопка на канал
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Forest Road 🌲", url="https://t.me/ForestRoad1")]
    ])

    try:
        # Всё в одном сообщении
        bot.send_photo(
            chat_id=CHANNEL,
            photo=ad_image_url,
            caption=ad_caption,
            parse_mode='HTML',
            reply_markup=keyboard
        )

        logging.info("Реклама отправлена.")
        last_ad_time = datetime.now(pytz.UTC)

    except Exception as e:
        logging.error(f"Ошибка отправки рекламы: {e}")

# === Парсинг и отправка новостей ===
def fetch_and_send_news():
    current_time = datetime.now(pytz.UTC)
    
    for url in rss_feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.link

            # Проверка на повторы за последние 35 минут
            cursor.execute("SELECT * FROM posted_links WHERE link=? AND timestamp > ?", (link, current_time - timedelta(minutes=35)))
            if cursor.fetchone():
                continue  # Пропустить, если новость была отправлена недавно

            title = translate_text(entry.title)
            summary = translate_text(entry.summary)

            image = None
            if 'media_content' in entry and entry.media_content:
                image = entry.media_content[0]['url']
            elif 'media_thumbnail' in entry and entry.media_thumbnail:
                image = entry.media_thumbnail[0]['url']

            caption = f"<b>{title}</b>\n\n{summary}\n\n<a href='{link}'>Читать полностью</a>\n\nПоддержка: <a href='{SUPPORT_LINK}'>Forest Road</a>"

            try:
                if image:
                    bot.send_photo(chat_id=CHANNEL, photo=image, caption=caption, parse_mode='HTML')
                else:
                    bot.send_message(chat_id=CHANNEL, text=caption, parse_mode='HTML')

                logging.info(f"Отправлена новость: {title}")
                cursor.execute("INSERT INTO posted_links (link, timestamp) VALUES (?, ?)", (link, current_time))
                conn.commit()

            except Exception as e:
                logging.error(f"Ошибка отправки новости: {e}")

# === Планировщик ===
scheduler = BackgroundScheduler(timezone=pytz.UTC)
scheduler.add_job(fetch_and_send_news, 'interval', minutes=35)
scheduler.add_job(send_advertisement, 'interval', minutes= 3 * 24 * 60)  # Каждые 3 дня
scheduler.start()

# === Запуск ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Бот запущен")
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        conn.close()
