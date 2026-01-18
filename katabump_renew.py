#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import html as _html
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

DASHBOARD_URL = "https://dashboard.katabump.com"
DASHBOARD_LOGIN_URL = f"{DASHBOARD_URL}/auth/login"
TZ = timezone(timedelta(hours=8))

def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

def log(msg: str):
    print(f'[{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)

def mask(s: str) -> str:
    """Generic mask for secrets"""
    if not s:
        return "EMPTY"
    if len(s) <= 8:
        return f"len={len(s)}:{s!r}"
    return f"len={len(s)}:{s[:4]}...{s[-4:]}"

def mask_server_id(s: str, head: int = 4, tail: int = 4) -> str:
    """Server ID 脱敏显示：abcd…wxyz"""
    if not s:
        return "EMPTY"
    if len(s) <= head + tail + 1:
        return f"len={len(s)}"
    return f"{s[:head]}…{s[-tail:]}"

def mask_email(email: str) -> str:
    """邮箱脱敏：lib***@outlook.com"""
    email = (email or "").strip()
    if not email or "@" not in email:
        return "EMPTY"
    user, domain = email.split("@", 1)
    if len(user) <= 3:
        user_mask = user[:1] + "***" if user else "***"
    else:
        user_mask = user[:3] + "***"
    return f"{user_mask}@{domain}"

def h(s: object) -> str:
    """HTML-escape for Telegram parse_mode=HTML"""
    return _html.escape("" if s is None else str(s), quote=True)

KATA_EMAIL    = env("KATA_EMAIL")
KATA_PASSWORD = env("KATA_PASSWORD")
SERVER_ID     = env("KATA_SERVER_ID") or env("KATABUMP_SERVER_ID")
TG_BOT_TOKEN  = env("TG_BOT_TOKEN")
TG_CHAT_ID    = env("TG_CHAT_ID")
EXECUTOR_NAME = env("EXECUTOR_NAME", "GitHub Actions")

NOTIFY_DAYS = int(env("KATA_NOTIFY_DAYS", "7"))

RENEW_GUIDE = (
    "Renew 操作指南：\n"
    "1. 登录 Dashboard\n"
    "2. 点击菜单栏 Your Servers\n"
    "3. 找到服务器点击 See\n"
    "4. 进入 General 页面\n"
    "5. 点击蓝色的 Renew 按钮"
)

def tg_send_html(html_text: str) -> bool:
    """
    Send Telegram message with parse_mode=HTML to support clickable text link.
    NOTE: html_text must be properly escaped except allowed tags (<a>, <b>, etc.)
    """
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("Telegram 未配置（TG_BOT_TOKEN/TG_CHAT_ID 为空）")
        return False

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    r = requests.post(url, json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.status_code != 200 or not data.get("ok"):
        log(f"Telegram 发送失败: HTTP {r.status_code}, resp={data}")
        return False

    log("Telegram 已发送")
    return True

def get_csrf_token(html: str) -> Optional[str]:
    # 常见 Laravel: <input type="hidden" name="_token" value="...">
    m = re.search(r'name="_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None

def parse_expiry(html: str) -> Optional[str]:
    if not html:
        return None

    low = html.lower()
    idx = low.find("expiry")
    if idx != -1:
        chunk = html[max(0, idx - 500): idx + 1200]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", chunk)
        if m:
            return m.group(1)

    m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    return m.group(1) if m else None

def days_until(date_str: str) -> Optional[int]:
    try:
        exp = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(TZ).date()
        return (exp - today).days
    except Exception:
        return None

def kata_login(session: requests.Session):
    login_url = f"{DASHBOARD_URL}/auth/login"
    r0 = session.get(login_url, timeout=30)
    token = get_csrf_token(r0.text)

    data = {"email": KATA_EMAIL, "password": KATA_PASSWORD, "remember": "true"}
    if token:
        data["_token"] = token

    r = session.post(
        login_url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": DASHBOARD_URL,
            "Referer": login_url,
        },
        timeout=30,
        allow_redirects=True,
    )

    if "/auth/login" in r.url:
        raise RuntimeError("登录失败：检查 KATA_EMAIL / KATA_PASSWORD（或需要额外验证）")

def build_notice_html(server_display: str, expiry: str, days: int) -> str:
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    email_display = mask_email(KATA_EMAIL)
    login_link = f'<a href="{h(DASHBOARD_LOGIN_URL)}">点击此处登录</a>'

    # 标题/强提醒
    if days < 0:
        title = "Katabump 续期提醒（已过期）"
        urgency = "<b><u>重点提示：已过期，请立即 Renew。</u></b>"
    elif days <= 1:
        title = "Katabump 续期提醒"
        # “24h尽快renew”要求：在 days=1/0 时强调
        urgency = "<b><u>重点提示：马上到期（24h内），请尽快 Renew。</u></b>"
    else:
        title = "Katabump 续期提醒"
        urgency = ""

    # 参考截图风格：清爽键值 + 换行 + 重要提示 + 登录 + 指南
    lines = [
        f"<b>{h(title)}</b>",
        "",
        f"时间: <code>{h(now_str)}</code>",
        f"账号: <code>{h(email_display)}</code>",
        f"Server: <code>{h(server_display)}</code>",
        f"到期日: <code>{h(expiry)}</code>",
        f"剩余: <code>{h(days)} 天</code>",
        f"执行器: <code>{h(EXECUTOR_NAME)}</code>",
    ]

    if urgency:
        lines += ["", urgency]

    lines += [
        "",
        f"{login_link}",
        "",
        f"<pre>{h(RENEW_GUIDE)}</pre>",
    ]
    return "\n".join(lines)

def build_error_html(server_display: str, err: Exception) -> str:
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    email_display = mask_email(KATA_EMAIL)
    login_link = f'<a href="{h(DASHBOARD_LOGIN_URL)}">点击此处登录</a>'

    return "\n".join([
        "<b>Katabump 续期提醒（脚本错误）</b>",
        "",
        f"时间: <code>{h(now_str)}</code>",
        f"账号: <code>{h(email_display)}</code>",
        f"Server: <code>{h(server_display)}</code>",
        f"执行器: <code>{h(EXECUTOR_NAME)}</code>",
        f"错误: <code>{h(err)}</code>",
        "",
        f"{login_link}",
        "",
        f"<pre>{h(RENEW_GUIDE)}</pre>",
    ])

def main():
    if not KATA_EMAIL or not KATA_PASSWORD:
        raise RuntimeError("缺少环境变量：KATA_EMAIL / KATA_PASSWORD（请在 Actions env 注入 secrets）")
    if not SERVER_ID:
        raise RuntimeError("缺少环境变量：KATA_SERVER_ID（请在 Actions env 注入 secrets）")

    server_display = mask_server_id(SERVER_ID)

    log(f"Python: {sys.version.split()[0]}")
    log(f"SERVER_ID={server_display!r}  NOTIFY_DAYS={NOTIFY_DAYS}")
    log(f"TG_BOT_TOKEN={mask(TG_BOT_TOKEN)}")
    log(f"TG_CHAT_ID={mask(TG_CHAT_ID)}")

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    # 抓取用真实 SERVER_ID，但通知不暴露
    server_url = f"{DASHBOARD_URL}/servers/edit?id={SERVER_ID}"

    try:
        log("登录中...")
        kata_login(s)
        log("登录成功")

        log(f"访问服务器页: {server_url}")
        page = s.get(server_url, timeout=30, allow_redirects=True)
        if "/servers/edit" not in page.url:
            raise RuntimeError(f"访问服务器页面失败，被重定向到：{page.url}")

        expiry = parse_expiry(page.text)
        if not expiry:
            raise RuntimeError("未解析到 Expiry（页面结构可能变化）")

        days = days_until(expiry)
        if days is None:
            raise RuntimeError(f"到期日无法计算：{expiry}")

        log(f"到期日：{expiry} | 剩余：{days} 天")

        if days > NOTIFY_DAYS:
            log(f"剩余 > {NOTIFY_DAYS} 天，不通知")
            return

        msg_html = build_notice_html(server_display=server_display, expiry=expiry, days=days)

        if not tg_send_html(msg_html):
            raise RuntimeError("需要通知但 Telegram 发送失败（检查 chat_id/权限/网络/Secrets 注入）")

    except Exception as e:
        log(f"脚本错误：{e}")
        tg_send_html(build_error_html(server_display=server_display, err=e))
        raise

if __name__ == "__main__":
    main()
