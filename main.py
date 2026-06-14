import os
import sys
import threading
from flask import Flask
import telebot
import pandas as pd

# 1. Микро-сервер для прохождения Port Binding проверок на Render
app = Flask('')

@app.route('/')
def home():
    return "Сервер активен, бот в сети!"

def run_flask():
    # Render автоматически передает порт в переменные окружения
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. ИЗОЛЯЦИЯ СЕКРЕТОВ: Токен запрашивается динамически из системы
TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN отсутствует в настройках сервера!", file=sys.stderr)
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR = "/tmp/processed_files"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 3. Обработка команд и файлов
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    bot.send_message(
        message.chat.id, 
        "Привет! Я облачный бот для сегментации баз данных Manato.\n\n"
        "📁 **Отправьте мне ваш файл Excel (.xlsx)**, и я автоматически разделю его по вкладкам на основе дней сегментации."
    )

@bot.message_handler(content_types=['document'])
def handle_excel_file(message):
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

        # Фильтрация по вашим категориям
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

        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка при обработке файла: {e}")

if __name__ == '__main__':
    # Запуск веб-сервера параллельно с ботом
    threading.Thread(target=run_flask).start()
    print("🚀 Облачный бот успешно инициализирован и запущен в фоновом режиме...")
    bot.infinity_polling()
