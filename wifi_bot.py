import telebot
import sqlite3
import os
import subprocess
import time

# --- 設定區 ---
# ⚠️ 請將這裡換成你從 @BotFather 拿到的 Token
API_TOKEN = '8402078101:AAH0NboR53xOwz4LYTMj_Q_PYrypcHq5oQQ'

DB_PATH = "class_status.db"
INTERFACE = "enp0s8"  # 用來查 MAC Address 用的

bot = telebot.TeleBot(API_TOKEN)

# --- 狀態紀錄 (記憶體中) ---
# 用來記錄每個 User 目前對話進行到哪一步
# 格式: { chat_id: "WAITING_FOR_STUDENT_ID" }
user_states = {}

# 用來暫存 User 的資料，等到全部問完再一次寫入資料庫
# 格式: { chat_id: { "ip": "...", "student_id": "..." } }
user_data = {}

# 定義狀態常數
STATE_WAITING_ID = "WAITING_FOR_STUDENT_ID"
STATE_WAITING_NAME = "WAITING_FOR_NAME"

# --- 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 建立學生資料表 (包含 Telegram ID, 學號, 姓名, IP, MAC)
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    telegram_id INTEGER PRIMARY KEY,
                    student_id TEXT,
                    name TEXT,
                    ip TEXT,
                    mac TEXT,
                    status TEXT DEFAULT 'LOGIN',
                    violation_count INTEGER DEFAULT 0,
                    last_seen TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# --- 輔助函式: 抓 MAC Address ---
def get_mac_address(ip):
    try:
        # 使用 arp -n 指令查表
        cmd = f"arp -n {ip} | grep {ip} | awk '{{print $3}}'"
        mac = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        if not mac or len(mac) < 10:
            return "UNKNOWN"
        return mac
    except:
        return "UNKNOWN"

# --- 1. 處理 /start 指令 (入口) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    text = message.text  # 例如: "/start 192_168_56_101"
    
    # 解析參數 (IP)
    try:
        # 把 "/start " 切掉，只留參數
        params = text.split()[1] 
        user_ip = params.replace("_", ".") # 把 192_168... 變回 192.168...
    except IndexError:
        bot.reply_to(message, "⚠️ 請不要直接搜尋機器人，請透過 Wi-Fi 登入頁面的按鈕開啟。")
        return

    print(f"收到登入請求: IP={user_ip}, ChatID={chat_id}")

    # 檢查是否已經註冊過 (舊生)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, student_id FROM students WHERE telegram_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()

    if row:
        # --- 舊生：直接登入 ---
        name = row[0]
        bot.reply_to(message, f"歡迎回來，{name}！\n系統正在為您開通網路...")
        
        # 更新 IP 和 MAC
        mac = get_mac_address(user_ip)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE students SET ip=?, mac=?, status='LOGIN', last_seen=CURRENT_TIMESTAMP WHERE telegram_id=?", (user_ip, mac, chat_id))
        conn.commit()
        conn.close()
        
        # 執行開網
        os.system(f"sudo ./login.sh {user_ip}")
        bot.send_message(chat_id, "✅ 網路已開通！您可以切回 Wi-Fi 上網了。")
        
    else:
        # --- 新生：開始註冊流程 ---
        # 1. 暫存 IP
        user_data[chat_id] = {"ip": user_ip}
        # 2. 設定狀態：等待輸入學號
        user_states[chat_id] = STATE_WAITING_ID
        
        bot.reply_to(message, "👋 您好！這是您第一次登入。\n請輸入您的 **學號**：")

# --- 2. 處理文字訊息 (回答問題) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # 檢查這個人目前的狀態
    state = user_states.get(chat_id)

    if state == STATE_WAITING_ID:
        # --- 使用者輸入了學號 ---
        user_data[chat_id]["student_id"] = text
        
        # 切換狀態 -> 等待輸入姓名
        user_states[chat_id] = STATE_WAITING_NAME
        bot.reply_to(message, "收到。請接著輸入您的 **真實姓名**：")
        
    elif state == STATE_WAITING_NAME:
        # --- 使用者輸入了姓名 (流程結束) ---
        name = text
        student_id = user_data[chat_id]["student_id"]
        ip = user_data[chat_id]["ip"]
        mac = get_mac_address(ip) # 嘗試抓 MAC
        
        bot.reply_to(message, f"資料確認：\n學號：{student_id}\n姓名：{name}\n\n正在寫入資料庫並開通網路...")

        # 1. 寫入資料庫
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO students 
                     (telegram_id, student_id, name, ip, mac, status, last_seen) 
                     VALUES (?, ?, ?, ?, ?, 'LOGIN', CURRENT_TIMESTAMP)''', 
                     (chat_id, student_id, name, ip, mac))
        conn.commit()
        conn.close()

        # 2. 執行開網 Shell Script
        os.system(f"sudo ./login.sh {ip}")

        # 3. 清除狀態
        del user_states[chat_id]
        del user_data[chat_id]

        bot.send_message(chat_id, "✅ 註冊成功！網路已開通，請切回 Wi-Fi 使用。")
        
    else:
        # 沒有狀態，或者是亂聊天的
        bot.reply_to(message, "請點擊登入頁面的連結來開始使用。")

# --- 啟動 Bot ---
if __name__ == "__main__":
    init_db() # 初始化資料庫
    print("🤖 Telegram Bot 啟動中...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot 發生錯誤: {e}")
