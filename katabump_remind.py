#!/usr/bin/env python3
import os
import json
import re
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
    # 简单邮箱脱敏：abcde@xx.com -> abc***@xx.com
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


def http_get(url: str, cookie: str | None = None) -> str:
    """
    纯标准库 GET。若页面需要登录，可选传 cookie（不强制）。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie

    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_expiry_date(html: str) -> str:
    """
    从页面中解析 Expiry 的日期字符串：YYYY-MM-DD
    依据你提供的结构：
      <div class="... label ">Expiry</div>
      <div class="...">2026-01-18</div>
    """
    m = re.search(
        r'>\s*Expiry\s*</div>\s*<div[^>]*>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        raise ValueError("Could not find Expiry date in HTML (maybe not logged in / page changed).")
    return m.group(1)


def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    # ✅ 不改你原始变量名
    email = os.environ.get("KATABUMP_ACCOUNT_EMAIL", "lib***@outlook.com")
    renew_url = os.environ.get("KATABUMP_RENEW_URL", "https://dashboard.katabump.com/dashboard")
    tz_name = os.environ.get("TIMEZONE", "Asia/Taipei")  # 你也可以继续用原来的默认

    # 可选：如果 dashboard 需要登录才能看到 Expiry，你可以额外在 Secrets 里加一个 KATABUMP_COOKIE
    # 不加也不影响运行，只是可能解析不到 Expiry（会发“检查失败”通知）
    cookie = os.environ.get("KATABUMP_COOKIE")

    # 时区对象
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    ts = now_str(tz_name)
    email_masked = mask_email(email)

    try:
        html = http_get(renew_url, cookie=cookie)
        expiry_str = parse_expiry_date(html)  # "2026-01-18"
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = datetime.now(tz).date()
        days_left = (expiry_date - today).days
    except Exception as e:
        # 抓不到 Expiry：直接通知你“检查失败”，避免你以为没到期
        msg = f"""❌ <b>Katabump 到期检查失败</b>

📅 时间: {ts}
👤 账号: {email_masked}

原因: <code>{type(e).__name__}: {str(e)}</code>

可能原因：
- 该页面需要登录才能看到 Expiry（GitHub Actions 没有登录态）
- 页面结构变了导致解析不到

🔗 <a href="{renew_url}">打开 Dashboard</a>
"""
        send_telegram(bot_token, chat_id, msg)
        return

    # ✅ 只在“到期前一天”通知（稳健：按 date 差值）
    if days_left != 1:
        print(f"[SKIP] expiry={expiry_str}, today={today}, days_left={days_left}")
        return

    msg = f"""🚨 <b>Katabump 续期提醒（到期前 1 天）</b>

📅 时间: {ts}
👤 账号: {email_masked}

⏳ Expiry: <b>{expiry_str}</b>
✅ 仅在到期前一天提醒（当前剩余 <b>{days_left}</b> 天）

📝 Renew 操作指南:
1. 登录 Dashboard
2. 点击菜单栏 Your Servers
3. 找到服务器点击 See
4. 进入 General 页面
5. 点击蓝色的 Renew 按钮

🔗 <a href="{renew_url}">点击此处直接跳转</a>
"""
    send_telegram(bot_token, chat_id, msg)


if __name__ == "__main__":
    main()
