import os
import threading
from flask import Flask
import telebot
import pandas as pd

# Инициализируем Flask для обмана проверок портов Render
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run_flask():
    # Render автоматически передает номер порта в переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Инициализируем Telegram бота
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8914792143:AAEieFUabeaZr8hdP4aVkC1VInoWo5rmVqk')
bot = telebot.TeleBot(TOKEN)

DOWNLOAD_DIR = "/tmp/processed_files"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(
        message.chat.id, 
        "Привет! Я облачный бот-сегментатор базы.\n\n"
        "📁 **Отправьте мне ваш файл Excel (.xlsx)**, и я автоматически разделю его на сегменты по вкладкам."
    )

@bot.message_handler(content_types=['document'])
def handle_excel_file(message):
    try:
        file_name = message.document.file_name
        if not file_name.endswith('.xlsx'):
            bot.reply_to(message, "❌ Ошибка! Нужен файл Excel с расширением .xlsx")
            return

        bot.reply_to(message, "⏳ Файл получен. Считаю дни и распределяю по сегментам...")

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = os.path.join(DOWNLOAD_DIR, file_name)
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        df = pd.read_excel(input_path)

        if 'segment_days' not in df.columns:
            bot.send_message(message.chat.id, f"❌ Ошибка: В таблице не найдена колонка `segment_days`.")
            os.remove(input_path)
            return

        df['segment_days'] = pd.to_numeric(df['segment_days'], errors='coerce')

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
            bot.send_document(message.chat.id, result_file, caption="🎉 Сегментация завершена!")

        os.remove(input_path)
        os.remove(output_path)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")

if __name__ == '__main__':
    # Запускаем веб-сервер в отдельном потоке, чтобы он не мешал боту
    threading.Thread(target=run_flask).start()
    print("🤖 Облачный бот успешно запущен...")
    bot.infinity_polling()
