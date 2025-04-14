import logging
import os
import re
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import yt_dlp  # --- TikTok support ---

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)

# Функция для скачивания видео
async def download_video(url: str, chat_id: int) -> str:
    try:
        safe_chat_id = str(chat_id).lstrip('-')
        output_path = f"{safe_chat_id}_video.%(ext)s"
        command = [
            'yt-dlp',
            '-f', 'mp4',
            '-o', output_path,
            url
        ]
        subprocess.run(command, check=True)
        downloaded_file = output_path.replace('%(ext)s', 'mp4')
        
        # Получаем название видео
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video')
        
        return downloaded_file, video_title
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при скачивании видео: {e}")
        return None, None

# Функция для извлечения аудио из видео
async def extract_audio(video_file: str, video_title: str, chat_id: int) -> str:
    try:
        safe_chat_id = str(chat_id).lstrip('-')
        audio_file = f"{video_title}_{safe_chat_id}_audio.mp3"
        command = [
            './ffmpeg',
            '-i', video_file,
            '-vn',
            '-acodec', 'libmp3lame',
            '-ar', '44100',
            '-ac', '2',
            audio_file
        ]
        with open('ffmpeg_log.txt', 'w') as log_file:
            subprocess.run(command, check=True, stdout=log_file, stderr=log_file)
        return audio_file
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при извлечении аудио: {e}")
        return None

# --- TikTok support ---
async def download_tiktok_video(url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        safe_chat_id = str(chat_id).lstrip('-')
        output_path = f"{safe_chat_id}_tiktok.%(ext)s"
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'mp4',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)
            video_title = info.get('title', 'video')
            if os.path.exists(video_file):
                # Отправляем видео
                with open(video_file, 'rb') as video:
                    await context.bot.send_video(chat_id=chat_id, video=video)
                logging.info(f"Видео TikTok успешно отправлено в чат: {video_file}")

                # Извлекаем и отправляем аудио
                audio_file = await extract_audio(video_file, video_title, chat_id)
                if audio_file and os.path.exists(audio_file):
                    with open(audio_file, 'rb') as audio:
                        await context.bot.send_audio(chat_id=chat_id, audio=audio)
                    logging.info(f"Аудио успешно отправлено в чат: {audio_file}")
                    os.remove(audio_file)
                else:
                    await context.bot.send_message(chat_id=chat_id, text="Не удалось извлечь аудио из видео.")
                
                os.remove(video_file)
            else:
                await context.bot.send_message(chat_id=chat_id, text="Не удалось найти загруженное видео.")
    except Exception as e:
        logging.error(f"Ошибка при скачивании видео TikTok: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Произошла ошибка при скачивании видео TikTok.")
# --- End of TikTok support ---

# Обработчик входящих сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    chat_id = update.effective_chat.id

    youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+)'
    tiktok_regex = r'(https?://(?:www\.)?(?:tiktok\.com/@[\w\.-]+/video/\d+|vm\.tiktok\.com/\S+))'  # --- TikTok support ---

    if re.search(youtube_regex, message_text):
        url = re.search(youtube_regex, message_text).group(1)
        await context.bot.send_message(chat_id=chat_id, text="Йоу, качаю видео, скоро отдам. А следом и аудио из него сворую для тебя. Только не шуми")
        logging.info(f"Начало загрузки видео по ссылке: {url}")

        video_file, video_title = await download_video(url, chat_id)
        if video_file and os.path.exists(video_file):
            try:
                # Отправляем видео
                with open(video_file, 'rb') as video:
                    await context.bot.send_video(chat_id=chat_id, video=video)
                logging.info(f"Видео успешно отправлено в чат: {video_file}")

                # Извлекаем и отправляем аудио
                audio_file = await extract_audio(video_file, video_title, chat_id)
                if audio_file and os.path.exists(audio_file):
                    with open(audio_file, 'rb') as audio:
                        await context.bot.send_audio(chat_id=chat_id, audio=audio)
                    logging.info(f"Аудио успешно отправлено в чат: {audio_file}")
                    os.remove(audio_file)
                else:
                    await context.bot.send_message(chat_id=chat_id, text="Не удалось извлечь аудио из видео.")
                
                os.remove(video_file)
            except Exception as e:
                logging.error(f"Ошибка при отправке видео: {e}")
                await context.bot.send_message(chat_id=chat_id, text="Произошла ошибка при отправке видео.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Не удалось скачать видео. Проверьте ссылку.")
    elif re.search(tiktok_regex, message_text):  # --- TikTok support ---
        url = re.search(tiktok_regex, message_text).group(1)
        await context.bot.send_message(chat_id=chat_id, text="Эй, ворую TikTok видео для тебя, скоро отдам, а заодно и аудио с видоса.")
        logging.info(f"Начало загрузки TikTok видео по ссылке: {url}")
        await download_tiktok_video(url, chat_id, context)
    else:
        logging.info("Сообщение не содержит ссылку на поддерживаемый ресурс.")

# Основная функция запуска бота

import shutil

def check_tools():
    missing = []
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    if missing:
        print(f"Ошибка: не найдены утилиты: {', '.join(missing)}")
        exit(1)


def main():
    check_tools()
    application = ApplicationBuilder().token(os.getenv('BOT_TOKEN')).build()  #7690359419:AAFO0dgpL0IaAP44WCMtNOTPMq5plBmPWlA
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
