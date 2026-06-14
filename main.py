import os
import sys
import threading
from flask import Flask
import telebot
import pandas as pd

# 1. Веб-сервер для прохождения проверок портов Render
app = Flask('')

@app.route('/')
def home():
    return "Сервер активен, бот в приватном режиме."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. ИЗОЛЯЦИЯ ДАННЫХ: Запрос токена и ID владельца из системы
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ALLOWED_ID_STR = os.environ.get('ALLOWED_TELEGRAM_ID')

if not TOKEN or not ALLOWED_ID_STR:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Проверьте настройки Environment на Render! Отсутствует TOKEN или ALLOWED_TELEGRAM_ID.", file=sys.stderr)
    sys.exit(1)

try:
    ALLOWED_ID = int(ALLOWED_ID_STR)
except ValueError:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: ALLOWED_TELEGRAM_ID должен содержать только цифры!", file=sys.stderr)
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR = "/tmp/processed_files"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 3. Функция проверки прав доступа (Фейсконтроль)
def is_admin(message):
    return message.from_user.id == ALLOWED_ID

# 4. Обработка команд и файлов с жесткой проверкой ID
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    if not is_admin(message):
        print(f"🔒 Заблокирована попытка доступа от постороннего ID: {message.from_user.id}")
        return  # Бот просто проигнорирует чужака и ничего ему не ответит

    bot.send_message(
        message.chat.id, 
        "Привет! Я ваш приватный облачный бот для сегментации баз данных.\n\n"
        "📁 **Отправьте мне файл Excel (.xlsx)**, и я разделю его по вкладкам."
    )

@bot.message_handler(content_types=['document'])
def handle_excel_file(message):
    if not is_admin(message):
        print(f"🔒 Заблокирована попытка отправки файла от постороннего ID: {message.from_user.id}")
        return  # Файл постороннего человека даже не начнет скачиваться на сервер

    try:
        file_name = message.document.file_name
        if not file_name.endswith('.xlsx'):
            bot.reply_to(message, "❌ Ошибка! Принимаются только файлы с расширением .xlsx")
            return

        bot.reply_to(message, "⏳ Файл получен. Начинаю обработку и распределение по сегментам...")

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = os.path.join(DOWNLOAD_DIR, file_name)
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        df = pd.read_excel(input_path)

        if 'segment_days' not in df.columns:
            bot.send_message(message.chat.id, "❌ Ошибка: В таблице не найдена обязательная колонка `segment_days`.")
            os.remove(input_path)
            return

        df['segment_days'] = pd.to_numeric(df['segment_days'], errors='coerce')

        # Фильтрация по категориям дней
        cl_df = df[(df['segment_days'] >= 9) & (df['segment_days'] <= 30)]
        cl2_df = df[(df['segment_days'] >= 31) & (df['segment_days'] <= 90)]
        cl3_df = df[(df['segment_days'] >= 91) & (df['segment_days'] <= 365)]

        output_filename = f"сегментированный_{file_name}"
        output_path = os.path.join(DOWNLOAD_DIR, output_filename)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Вся база', index=False)
            cl_df.to_excel(writer, sheet_name='CL (9-30d)', index=False)
            cl2_df.to_excel(writer, sheet_name='CL2 (31-90d)', index=False)
            cl3_df.to_excel(writer, sheet_name='CL3 (91-365d)', index=False)

        with open(output_path, 'rb') as result_file:
            bot.send_document(message.chat.id, result_file, caption="🎉 Сегментация базы успешно завершена!")

        # БЕЗОПАСНОСТЬ ДАННЫХ: Полное физическое удаление файлов с диска сервера сразу после отправки
        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка при обработке файла: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    print("🚀 Приватный облачный бот успешно запущен и защищен...")
    bot.infinity_polling()
