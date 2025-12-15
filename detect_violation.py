import sqlite3
import time
import subprocess
import os

# --- 設定區 ---
PIHOLE_DB_PATH = "/etc/pihole/pihole-FTL.db"  # Pi-hole 資料庫 (唯讀)
CLASS_DB_PATH = "class_status.db"             # 學生狀態資料庫 (讀寫)
CHECK_INTERVAL = 10
INTERFACE = "enp0s8" 

BLACKLIST_VIDEO = ["googlevideo.com", "nflxvideo.net", "netflix.com"]
BLACKLIST_GAME = ["steamcommunity.com", "steampowered.com", "riotgames.com"]
THRESHOLD = 5

# --- 1. 初始化學生狀態資料庫 (自動建立) ---
def init_class_db():
    conn = sqlite3.connect(CLASS_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            student_id TEXT,
            name TEXT,
            ip TEXT UNIQUE,
            mac TEXT,
            status TEXT DEFAULT 'LOGIN',      -- LOGIN, NORMAL, PUNISHED
            violation_count INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --- 2. 狀態更新函式 (寫入 Class DB) ---
def mark_punished(ip):
    """將學生標記為 'PUNISHED' (紅燈)"""
    conn = sqlite3.connect(CLASS_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE students SET status='PUNISHED' WHERE ip=?", (ip,))
    conn.commit()
    conn.close()

def get_punished_ips():
    """查詢目前誰正在被罰 (避免重複執行懲罰指令)"""
    conn = sqlite3.connect(CLASS_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ip FROM students WHERE status='PUNISHED'")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows] # 回傳 ['192.168.56.1', ...]

# --- 3. 讀取 Pi-hole 資料 (唯讀) ---
def get_recent_queries():
    """從 Pi-hole 資料庫抓取最近 60 秒的查詢紀錄"""
    try:
        conn = sqlite3.connect(PIHOLE_DB_PATH)
        cursor = conn.cursor()
        ts = int(time.time()) - 60
        query = f"SELECT client, domain FROM queries WHERE timestamp > {ts}"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"讀取 Pi-hole DB 錯誤: {e}")
        return []

# --- 4. 執行處罰 ---
def punish_user(ip, type):
    print(f"🚨 抓到了！IP {ip} 正在 {type}！執行處罰...")
    
    if type == "VIDEO":
        os.system(f"sudo ./slow_down.sh {ip} {INTERFACE}")
    elif type == "GAME":
        os.system(f"sudo ./block_game.sh {ip}")
    
    # 寫入資料庫，標記為已懲罰
    mark_punished(ip)

# --- 主程式 ---
def main():
    init_class_db()
    print("👀 違規偵測啟動中 (嚴格模式：只抓不放)...")

    while True:
        try:
            logs = get_recent_queries()
            current_stats = {}

            # 統計目前的違規
            for client_ip, domain in logs:
                if client_ip not in current_stats:
                    current_stats[client_ip] = 0
                
                for keyword in BLACKLIST_VIDEO + BLACKLIST_GAME:
                    if keyword in domain:
                        current_stats[client_ip] += 1

            # 抓違規 (判罰)
            for ip, count in current_stats.items():
                if count >= THRESHOLD:
                    # 檢查他是不是已經在被罰名單中
                    # 如果已經在名單內，就跳過 (避免每10秒重複執行一次 slow_down.sh)
                    punished_list = get_punished_ips()
                    if ip not in punished_list:
                        print(f"IP {ip} 違規次數: {count}")
                        punish_user(ip, "VIDEO")

            # [已刪除] 自動解除邏輯 (Restore Logic)

        except Exception as e:
            print(f"發生錯誤: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("請使用 sudo 執行此程式！")
        exit(1)
    main()
