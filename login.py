from flask import Flask, request, render_template_string
import os

app = Flask(__name__)

# HTML 模板 (包含 Telegram Deep Link 按鈕)
# 注意: tg://resolve... 的 start 參數帶入了使用者的 IP
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NCNU Network Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; text-align: center; padding: 50px; }
        .btn { 
            background-color: #0088cc; color: white; padding: 15px 30px; 
            text-decoration: none; border-radius: 5px; font-size: 18px; display: inline-block;
        }
        .step { margin: 20px 0; color: #555; }
    </style>
</head>
<body>
    <h1>歡迎使用 NCNU 資管網路</h1>
    <div class="step">
        <p>您的 IP 位址是: <strong>{{ user_ip }}</strong></p>
        <p>請點擊下方按鈕進行 Telegram 驗證</p>
        <p style="color: red; font-size: 0.9em;">(請先切換至 4G/5G 網路以開啟 Telegram)</p>
    </div>
    
    <a href="https://t.me/lsa_login_test_bot?start={{ ip_param }}" target="_blank" class="btn">
        🔵 啟動 Telegram 驗證
    </a>
</body>
</html>
"""

@app.route("/", defaults={'path': ''})
@app.route("/<path:path>")  # 捕捉所有路徑 (Catch-all)
def login(path):
    # 從 Nginx 傳過來的 Header 取得真實 IP
    user_ip = request.headers.get('X-Real-IP', request.remote_addr)
    
    # 將 IP 格式化 (例如 192.168.56.101 -> 192_168_56_101)
    ip_param = user_ip.replace('.', '_')
    
    return render_template_string(HTML_TEMPLATE, user_ip=user_ip, ip_param=ip_param)

if __name__ == "__main__":
    # 這裡跑在 5000 Port，只聽本機介面 (因為 Nginx 會轉發過來)
    app.run(host="127.0.0.1", port=5000)
