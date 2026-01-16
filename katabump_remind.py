import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from zoneinfo import ZoneInfo

# 获取当前时间字符串
def now_str(tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

# 发送 Telegram 消息
def send_telegram(bot_token: str, chat_id: str, text_html: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(url, data=payload)
    response.raise_for_status()
    r = response.json()
    if not r.get("ok"):
        raise RuntimeError(f"Telegram API error: {response.text}")

# 从网页中抓取 Expiry
def get_expiry_date(login_url: str, dashboard_url: str, email: str, password: str) -> datetime:
    session = requests.Session()

    # 登录步骤（根据实际需要设置登录参数）
    login_payload = {
        'email': email,
        'password': password
    }
    login_response = session.post(login_url, data=login_payload)
    login_response.raise_for_status()  # 确保登录成功

    # 获取 dashboard 页面
    dashboard_response = session.get(dashboard_url)
    dashboard_response.raise_for_status()

    # 解析 HTML
    soup = BeautifulSoup(dashboard_response.text, 'html.parser')
    expiry_text = soup.find('div', text='Expiry').find_next('div').get_text(strip=True)
    expiry_date = datetime.strptime(expiry_text, "%Y-%m-%d").date()

    return expiry_date

# 判断是否到期前一天
def is_one_day_before_expire(expiry_date: date, tz: ZoneInfo) -> bool:
    today = datetime.now(tz).date()
    return (expiry_date - today).days == 1

# 主逻辑
def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    login_url = "https://dashboard.katabump.com/login"
    dashboard_url = "https://dashboard.katabump.com/dashboard"
    email = os.environ["KATABUMP_EMAIL"]
    password = os.environ["KATABUMP_PASSWORD"]
    tz_name = os.environ.get("TIMEZONE", "America/Los_Angeles")

    # 获取当前时区信息
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    ts = now_str(tz_name)

    # 获取 Expiry 日期
    try:
        expiry_date = get_expiry_date(login_url, dashboard_url, email, password)
    except Exception as e:
        msg = f"""❌ <b>Katabump 到期检查失败</b>

📅 时间: {ts}
👤 账号: {email}

原因: <code>{type(e).__name__}: {str(e)}</code>

🔗 <a href="{dashboard_url}">点击此处打开 Dashboard</a>
"""
        send_telegram(bot_token, chat_id, msg)
        return

    # 判断是否是到期前一天
    if is_one_day_before_expire(expiry_date, tz):
        msg = f"""🚨 <b>Katabump 续期提醒（到期前 1 天）</b>

📅 时间: {ts}
👤 账号: {email}

⏳ 到期日: <b>{expiry_date}</b>
✅ 符合官方规则：仅到期前一天可 Renew

🔗 <a href="{dashboard_url}">点击此处直接跳转登录</a>
"""
        send_telegram(bot_token, chat_id, msg)

if __name__ == "__main__":
    main()
