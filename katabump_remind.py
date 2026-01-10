#!/usr/bin/env python3
import os
import json
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

def now_str(tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

def mask_email(email: str) -> str:
    # 简单邮箱脱敏：abcde@xx.com -> ab***@xx.com
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "***"
    else:
        masked = name[:3] + "***"
    return f"{masked}@{domain}"

def send_telegram(bot_token: str, chat_id: str, text_html: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        r = json.loads(body)
        if not r.get("ok"):
            raise RuntimeError(f"Telegram API error: {body}")

def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    email = os.environ.get("KATABUMP_ACCOUNT_EMAIL", "lib***@outlook.com")
    renew_url = os.environ.get("KATABUMP_RENEW_URL", "https://dashboard.katabump.com/dashboard")
    tz_name = os.environ.get("TIMEZONE", "America/Los_Angeles")  # 你可改成 Asia/Shanghai

    ts = now_str(tz_name)
    email_masked = mask_email(email)

    # 用 HTML 生成可点击链接（Telegram 支持 HTML parse_mode）:contentReference[oaicite:1]{index=1}
    msg = f"""🚨 <b>Katabump 续期提醒</b>

📅 时间: {ts}
👤 账号: {email_masked}

⚠️ 状态提示:
服务器周期已过 3 天，请务必在 24 小时内操作续期。

📝 Renew 操作指南:
1. 登录 Dashboard
2. 点击菜单栏 Your Servers
3. 找到服务器点击 See
4. 进入 General 页面
5. 点击蓝色的 Renew 按钮

🔗 <a href="{renew_url}">点击此处直接跳转登录</a>
"""
    send_telegram(bot_token, chat_id, msg)

if __name__ == "__main__":
    main()
