import sqlite3
import time
import subprocess
import os

# --- 設定區 ---
DB_PATH = "/etc/pihole/pihole-FTL.db"  # Pi-hole 資料庫位置
CHECK_INTERVAL = 10  # 每 10 秒檢查一次
INTERFACE = "enp0s8" # 你的 Host-Only 網卡名稱 (請修改!)

# 關鍵字黑名單 (只要網址包含這些字就算違規)
# YouTube 影片通常來自 googlevideo.com
# Steam 遊戲通常連線 steamcommunity, valve 等
BLACKLIST_VIDEO = ["googlevideo.com", "nflxvideo.net", "netflix.com"]
BLACKLIST_GAME = ["steamcommunity.com", "steampowered.com", "riotgames.com"]

# 處罰閾值 (1分鐘內查詢超過幾次就算違規)
THRESHOLD = 5 

def get_recent_queries():
    """從 Pi-hole 資料庫抓取最近 60 秒的查詢紀錄"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # SQL 語法：找最近 60 秒 (timestamp > now - 60) 的紀錄
    # client: 誰查的 (IP)
    # domain: 查了什麼網址
    ts = int(time.time()) - 60
    query = f"""
        SELECT client, domain 
        FROM queries 
        WHERE timestamp > {ts}
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows

def punish_user(ip, type):
    """呼叫你的 Shell Script 進行處罰"""
    print(f"🚨 抓到了！IP {ip} 正在 {type}！執行處罰...")
    
    if type == "VIDEO":
        # 呼叫降速腳本
        cmd = f"sudo ./slow_down.sh {ip} {INTERFACE}"
        os.system(cmd)
        
    elif type == "GAME":
        # 呼叫斷網腳本 (注意：這是暫時阻斷，建議後端要有邏輯控制解鎖)
        cmd = f"sudo ./block_game.sh {ip}"
        os.system(cmd)

def main():
    print("👀 違規偵測啟動中 (監控 Pi-hole)...")
    
    while True:
        try:
            logs = get_recent_queries()
            
            # 統計每個 IP 的違規次數
            # 格式: { "192.168.56.1": {"VIDEO": 0, "GAME": 0} }
            stats = {} 
            
            for client_ip, domain in logs:
                if client_ip not in stats:
                    stats[client_ip] = {"VIDEO": 0, "GAME": 0}
                
                # 判斷是否看影片
                for keyword in BLACKLIST_VIDEO:
                    if keyword in domain:
                        stats[client_ip]["VIDEO"] += 1
                        
                # 判斷是否打遊戲
                for keyword in BLACKLIST_GAME:
                    if keyword in domain:
                        stats[client_ip]["GAME"] += 1
            
            # 檢查是否超過閾值
            for ip, counts in stats.items():
                if counts["VIDEO"] >= THRESHOLD:
                    print(f"IP {ip} 看影片次數: {counts['VIDEO']}")
                    punish_user(ip, "VIDEO")
                    
                if counts["GAME"] >= THRESHOLD:
                    print(f"IP {ip} 打遊戲次數: {counts['GAME']}")
                    punish_user(ip, "GAME")
                    
        except Exception as e:
            print(f"發生錯誤: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # 需要 sudo 權限才能讀取 Pi-hole DB 和執行 iptables
    if os.geteuid() != 0:
        print("請使用 sudo 執行此程式！")
        exit(1)
    main()
