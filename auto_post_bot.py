# -*- coding: utf-8 -*-
import os
import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 📦 Завантаження змінних середовища з .env
load_dotenv()

# 🔑 Ключі та налаштування
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ініціалізація
client = AsyncOpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
logging.basicConfig(level=logging.INFO)
posted_links = set()

# Отримати зображення з HTML
def get_image_from_article(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                return og_image["content"]
    except Exception as e:
        logging.warning(f"⚠️ Помилка зображення: {e}")
    return None

# Переклад тексту GPT
async def translate_text(text):
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Переклади текст українською мовою як новину."},
                {"role": "user", "content": text}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.warning(f"❌ GPT переклад не вдався: {e}")
        return text

# Надіслати пост
async def send_post(title, link, summary, image_url=None):
    if link in posted_links:
        logging.info(f"⏭ Пропущено (вже публікувалось): {link}")
        return

    summary = BeautifulSoup(summary, "html.parser").get_text()
    caption = f"📰 <b>{title}</b>\n\n{summary}\n\n🔗 <a href='{link}'>читати повністю</a>"
    try:
        if image_url:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=caption[:1024], parse_mode="HTML")
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=caption[:4096], parse_mode="HTML")
        posted_links.add(link)
        logging.info(f"✅ Опубліковано: {title}")
    except Exception as e:
        logging.error(f"❌ Помилка надсилання: {e}")

# Новини з нових джерел
async def post_rss_news(feed_url, tag):
    logging.info(f"🌐 Читання RSS: {feed_url}")
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        if entry.link and entry.link not in posted_links:
            translated = await translate_text(entry.title + "\n\n" + entry.summary)
            image_url = get_image_from_article(entry.link)
            emoji = {
                "Jobs": "💼",
                "Crypto": "💰",
                "Tech": "🚀",
                "Business": "📊",
                "Startups": "🌱",
                "Ukraine": "🇺🇦"
            }.get(tag, "📰")
            await send_post(f"{emoji} {entry.title}", entry.link, translated, image_url)
            break

# 🔹 Повний ручний тест усіх джерел
async def manual_test_all():
    await post_rss_news("https://www.prace.cz/hledat/?searchForm%5Blocality_codes%5D=&searchForm%5Bprofs%5D=&searchForm%5Bother%5D=&searchForm%5Bemployment_type_codes%5D%5B%5D=201300001&searchForm%5Bemployment_type_codes%5D%5B%5D=201300002&searchForm%5Bemployment_type_codes%5D%5B%5D=201300004&searchForm%5Bminimal_salary%5D=30000&searchForm%5Beducation%5D=&searchForm%5Bsuitable_for%5D=&searchForm%5Bsearch%5D=", "Jobs")
    await post_rss_news("https://cryptoslate.com/feed/", "Crypto")
    await post_rss_news("https://techcrunch.com/feed/", "Tech")
    await post_rss_news("https://www.forbes.com/business/feed/", "Business")
    await post_rss_news("https://www.wired.com/feed/rss", "Tech")
    await post_rss_news("https://www.eu-startups.com/feed/", "Startups")
    await post_rss_news("https://www.pravda.com.ua/rss/", "Ukraine")

# 🔹 Тестовий запуск: перевірка доступу
async def test_message():
    await bot.send_message(chat_id=CHANNEL_ID, text="👋 Привіт з тесту! Якщо ти це бачишь — бот працює!")

# Планувальник
scheduler = AsyncIOScheduler()
scheduler.add_job(lambda: post_rss_news("https://www.prace.cz/hledat/?searchForm%5Blocality_codes%5D=&searchForm%5Bprofs%5D=&searchForm%5Bother%5D=&searchForm%5Bemployment_type_codes%5D%5B%5D=201300001&searchForm%5Bemployment_type_codes%5D%5B%5D=201300002&searchForm%5Bemployment_type_codes%5D%5B%5D=201300004&searchForm%5Bminimal_salary%5D=30000&searchForm%5Beducation%5D=&searchForm%5Bsuitable_for%5D=&searchForm%5Bsearch%5D=", "Jobs"), 'cron', hour=9)
scheduler.add_job(lambda: post_rss_news("https://www.forbes.com/business/feed/", "Business"), 'cron', hour=11)
scheduler.add_job(lambda: post_rss_news("https://www.wired.com/feed/rss", "Tech"), 'cron', hour=13)
scheduler.add_job(lambda: post_rss_news("https://cryptoslate.com/feed/", "Crypto"), 'cron', hour=15)
scheduler.add_job(lambda: post_rss_news("https://www.eu-startups.com/feed/", "Startups"), 'cron', hour=17)
scheduler.add_job(lambda: post_rss_news("https://www.pravda.com.ua/rss/", "Ukraine"), 'cron', hour=18)
scheduler.add_job(lambda: post_rss_news("https://www.prace.cz/hledat/?searchForm%5Blocality_codes%5D=&searchForm%5Bprofs%5D=&searchForm%5Bother%5D=&searchForm%5Bemployment_type_codes%5D%5B%5D=201300001&searchForm%5Bemployment_type_codes%5D%5B%5D=201300002&searchForm%5Bemployment_type_codes%5D%5B%5D=201300004&searchForm%5Bminimal_salary%5D=30000&searchForm%5Beducation%5D=&searchForm%5Bsuitable_for%5D=&searchForm%5Bsearch%5D=", "Jobs"), 'cron', hour=19)

# Запуск
async def main():
    logging.info("🤖 Бот запущено. Чекає на розклад...")
    await test_message()
    await manual_test_all()
    scheduler.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
