import os
import time
import sqlite3
import logging
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telebot import TeleBot, types

# ВСТАВЬ СЮДА СВОЙ НОВЫЙ ТОКЕН ИЗ BOTFATHER
BOT_TOKEN = "8832332359:AAHUSy1UHHb6ySbX6nkdEVyfw1hSY3poxzU"
CRYPTO_TOKEN = "587645:AATJA9zUStPi0qxOHhLZ3N6y3fKtxv7CknZ"

bot = TeleBot(BOT_TOKEN)
DB_FILE = "tg_game_bot.db"
logging.basicConfig(level=logging.INFO)

# --- ВЕБ-СЕРВЕР ДЛЯ ОБМАНА RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Бот Муравьиная Ферма работает!".encode("utf-8"))
    def log_message(self, format, *args):
        return

def run_web_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"Веб-сервер заглушки запущен на порту {port}")
    server.serve_forever()
# -------------------------------------

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
    # 10% годовых
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
    keyboard.add(btn_buy, btn_collect, btn_sell)  # Добавили третью кнопку
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
        f"_Прибыль начисляется в реальном времени (10% годовых)!_"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user: return
    
    update_profit(user_id)
    user = get_user(user_id)
    
        if call.data == "buy_ant":
        # Используем официальный URL Crypto Pay API
        url = "https://pay.cryptobot.net/api/createInvoice"
        headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
        payload = {
            "asset": "USDT",
            "amount": "1.00",
            "description": f"Покупка 1 муравья для игрока {user_id}",
            "payload": str(user_id)
        }
        try:
            res = requests.post(url, json=payload, headers=headers).json()
            
            # Если API вернуло ошибку, запишем её в логи Render
            if not res.get("ok") or not res.get("result"):
                logging.error(f"Ошибка Crypto Pay API: {res}")
                bot.answer_callback_query(call.id, "Ошибка платежной системы.")
                return

            pay_url = res["result"]["pay_url"]
            invoice_id = res["result"]["invoice_id"]
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", url=pay_url))
            bot.send_message(call.message.chat.id, "Ссылка на оплату сгенерирована! После оплаты муравей зачислится в течение пары минут.", reply_markup=kb)
            
            threading.Thread(target=check_payment, args=(invoice_id, user_id, call.message.chat.id), daemon=True).start()
            
        except Exception as e:
            logging.error(f"Критическая ошибка при создании счета: {e}")
            bot.answer_callback_query(call.id, "Не удалось связаться с платежкой.")

            
    elif call.data == "collect_profit":
        if user['profit'] > 0:
            collected = user['profit']
            user['profit'] = 0.0
            user['last_update'] = time.time()
            save_user(user_id, user)
            bot.answer_callback_query(call.id, f"💰 Снято {collected:.6f} USDT прибыли!", show_alert=True)
            # Обновляем главное меню у игрока
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🐜 **Муравьиная Ферма**\n\n📦 Твои муравьи: {user['ants']} шт.\n🔒 Депозит: {user['deposit']:.2f} USDT\n💰 Прибыль: {user['profit']:.6f} USDT",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ Еще нет прибыли.", show_alert=True)

    # --- НОВАЯ ЛОГИКА ПРОДАЖИ МУРАВЬЯ ---
    elif call.data == "sell_ant":
        if user['ants'] > 0:
            user['ants'] -= 1
            user['deposit'] -= 1.0
            user['profit'] += 1.0  # Возвращаем 1$ на счет прибыли (доступный к выводу)
            user['last_update'] = time.time()
            save_user(user_id, user)
            
            bot.answer_callback_query(call.id, "🚪 Муравей успешно продан! 1 USDT возвращен на баланс.", show_alert=True)
            
            # Сразу обновляем сообщение на экране у пользователя
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🐜 **Муравьиная Ферма**\n\n📦 Твои муравьи: {user['ants']} шт.\n🔒 Депозит: {user['deposit']:.2f} USDT\n💰 Прибыль: {user['profit']:.6f} USDT",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет муравьев для продажи!", show_alert=True)

def check_payment(invoice_id, user_id, chat_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    url = f"https://pay.cryptobot.net/api/getInvoices?invoice_ids={invoice_id}"

    
    for _ in range(30):
        time.sleep(10)
        try:
            res = requests.get(url, headers=headers).json()
            if res.get("result") and res["result"]["items"]:
                status = res["result"]["items"][0]["status"]
                if status == "paid":
                    user = get_user(user_id)
                    user['ants'] += 1
                    user['deposit'] += 1.0
                    user['last_update'] = time.time()
                    save_user(user_id, user)
                    bot.send_message(chat_id, "🎉 Оплата получена! Вам зачислен 1 муравей. Напишите /start для обновления.")
                    break
                elif status not in ["active", "paid"]:
                    break
        except:
            pass

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    web_thread = threading.Thread(target=run_web_server, args=(port,), daemon=True)
    web_thread.start()
    
    print("Бот Муравьиная Ферма успешно запущен!")
    bot.infinity_polling()
