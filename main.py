import os
import time
import sqlite3
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telebot import TeleBot, types

# ==========================================================
# КОНФИГУРАЦИЯ БОТА (НОВЫЙ ТОКЕН УСПЕШНО ВПИСАН)
BOT_TOKEN = "8832332359:AAHZg3aOQRo3jZf1S-jedGnQYnrodAbCAw0"
ADMIN_USERNAME = "AhmedAli1718" 
ADMIN_ID = 784188637  
# ==========================================================

bot = TeleBot(BOT_TOKEN)
DB_FILE = "tg_game_bot.db"
logging.basicConfig(level=logging.INFO)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот работает стабильно!".encode("utf-8"))
    def log_message(self, format, *args):
        return

def run_web_server(port):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logging.info(f"Сервер заглушки запущен на порту {port}")
        server.serve_forever()
    except Exception as e:
        logging.error(f"Ошибка сервера: {e}")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            ants INTEGER DEFAULT 0,
            deposit REAL DEFAULT 0.0,
            profit REAL DEFAULT 0.0,
            last_update REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT ants, deposit, profit, last_update FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'ants': row[0], 'deposit': row[1], 'profit': row[2], 'last_update': row[3]}
    return None

def save_user(user_id, user_data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, ants, deposit, profit, last_update)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, user_data['ants'], user_data['deposit'], user_data['profit'], user_data['last_update']))
    conn.commit()
    conn.close()

def update_profit(user_id):
    user = get_user(user_id)
    if not user or user['ants'] == 0:
        return
    now = time.time()
    elapsed_time = now - user['last_update']
    profit_per_second_for_one_ant = (1.0 * 0.10) / 365 / 86400
    total_earned = user['ants'] * profit_per_second_for_one_ant * elapsed_time
    user['profit'] += total_earned
    user['last_update'] = now
    save_user(user_id, user)

def get_main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_buy = types.InlineKeyboardButton(text="➕ Купить муравья (1 USDT)", callback_data="buy_ant")
    btn_collect = types.InlineKeyboardButton(text="💸 Снять прибыль", callback_data="collect_profit")
    btn_sell = types.InlineKeyboardButton(text="🚪 Продать 1 муравья (Вернуть 1$)", callback_data="sell_ant")
    keyboard.add(btn_buy, btn_collect, btn_sell)
    return keyboard

@bot.message_handler(commands=['start'])
def start_game(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        user = {'ants': 0, 'deposit': 0.0, 'profit': 0.0, 'last_update': time.time()}
        save_user(user_id, user)
    update_profit(user_id)
    user = get_user(user_id)
    
    text = (
        f"🐜 **Добро пожаловать на Муравьиную Ферму!**\n\n"
        f"📦 Твои муравьи: {user['ants']} шт.\n"
        f"🔒 Депозит: {user['deposit']:.2f} USDT\n"
        f"💰 Прибыль: {user['profit']:.6f} USDT\n\n"
        f"_Прибыль начисляется в реальном времени (10% годовых)!_\n\n"
        f"🆔 Твой ID для покупки муравьев: `{user_id}`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['give'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет прав администратора для этой команды!")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "❌ Используй: /give ID_ПОЛЬЗОВАТЕЛЯ")
            return
            
        target_id = int(args[1])
        user = get_user(target_id)
        if not user:
            user = {'ants': 0, 'deposit': 0.0, 'profit': 0.0, 'last_update': time.time()}
        
        update_profit(target_id)
        user = get_user(target_id)
        user['ants'] += 1
        user['deposit'] += 1.0
        user['last_update'] = time.time()
        save_user(target_id, user)
        
        bot.reply_to(message, f"✅ Успешно начислен 1 муравей игроку {target_id}!")
        try:
            bot.send_message(target_id, "🎉 Администратор зачислил вам 1 муравья! Нажмите /start для обновления баланса.")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user: 
        return
    
    update_profit(user_id)
    user = get_user(user_id)
    
    if call.data == "buy_ant":
        text_pay = (
            f"💳 **Инструкция по покупке муравья (1 USDT):**\n\n"
            f"1️⃣ Перейди в свой кошелек: @CryptoBot\n"
            f"2️⃣ Создай **Текстовый чек (Crypto Check)** на сумму **1 USDT**\n"
            f"3️⃣ Отправь созданный чек администратору: @{ADMIN_USERNAME}\n\n"
            f"⚠️ В поле 'Комментарий' к чеку обязательно укажи свой ID: `{user_id}`\n\n"
            f"После проверки администратор мгновенно начислит муравья на твою ферму!"
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(text="Открыть @CryptoBot", url="https://t.me/CryptoBot"))
        bot.send_message(call.message.chat.id, text_pay, parse_mode="Markdown", reply_markup=kb)
            
    elif call.data == "collect_profit":
        if user['profit'] > 0:
            collected = user['profit']
            user['profit'] = 0.0
            user['last_update'] = time.time()
            save_user(user_id, user)
            bot.answer_callback_query(call.id, f"💰 Снято {collected:.6f} USDT прибыли!", show_alert=True)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🐜 **Муравьиная Ферма**\n\n📦 Твои муравьи: {user['ants']} шт.\n🔒 Депозит: {user['deposit']:.2f} USDT\n💰 Прибыль: {user['profit']:.6f} USDT",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Еще нет прибыли.", show_alert=True)

    elif call.data == "sell_ant":
        if user['ants'] > 0:
            user['ants'] -= 1
            user['deposit'] -= 1.0
            user['profit'] += 1.0
            user['last_update'] = time.time()
            save_user(user_id, user)
            bot.answer_callback_query(call.id, "🚪 Муравей успешно продан! 1 USDT возвращен.", show_alert=True)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🐜 **Муравьиная Ферма**\n\n📦 Твои муравьи: {user['ants']} шт.\n🔒 Депозит: {user['deposit']:.2f} USDT\n💰 Прибыль: {user['profit']:.6f} USDT",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет муравьев!", show_alert=True)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    web_thread = threading.Thread(target=run_web_server, args=(port,), daemon=True)
    web_thread.start()
    
    print("Бот запущен успешно!")
    bot.infinity_polling()
