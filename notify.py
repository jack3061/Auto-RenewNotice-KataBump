import requests
import os

# 从 GitHub Secrets 获取配置
TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID = os.environ["TG_CHAT_ID"]

def send_alert():
    # 消息内容：提醒您去手动点一下
    text = (
        "⚠️ **Katabump 续期提醒**\n\n"
        "📅 已经过去 3 天了，服务器即将到期！\n"
        "👉 请立即登录 Renew：\n"
        "https://dashboard.katabump.com/"
    )
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
        print("✅ 通知已发送")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_alert()
