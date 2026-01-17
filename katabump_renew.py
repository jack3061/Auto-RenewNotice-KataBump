#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys, requests
from datetime import datetime, timezone, timedelta
from typing import Optional

DASHBOARD_URL = "https://dashboard.katabump.com"
TZ = timezone(timedelta(hours=8))

def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

def log(msg: str):
    print(f'[{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)

KATA_EMAIL    = env("KATA_EMAIL")
KATA_PASSWORD = env("KATA_PASSWORD")
SERVER_ID     = env("KATA_SERVER_ID") or env("KATABUMP_SERVER_ID")
TG_BOT_TOKEN  = env("TG_BOT_TOKEN")
TG_CHAT_ID    = env("TG_CHAT_ID")
EXECUTOR_NAME = env("EXECUTOR_NAME", "GitHub Actions")
NOTIFY_DAYS   = int(env("KATA_NOTIFY_DAYS", "7"))

def tg_send(text: str) -> None:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True}

    r = requests.post(url, json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.status_code != 200 or not data.get("ok"):
        raise RuntimeError(f"Telegram 发送失败: HTTP {r.status_code}, resp={data}")

def get_csrf(html: str) -> Optional[str]:
    m = re.search(r'name="_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None

def parse_expiry(html: str) -> Optional[str]:
    if not html:
        return None
    low = html.lower()
    idx = low.find("expiry")
    if idx != -1:
        chunk = html[max(0, idx-500): idx+1200]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", chunk)
        if m:
            return m.group(1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    return m.group(1) if m else None

def days_until(yyyy_mm_dd: str) -> Optional[int]:
    try:
        exp = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
        today = datetime.now(TZ).date()
        return (exp - today).days
    except Exception:
        return None

def kata_login(s: requests.Session) -> None:
    login_url = f"{DASHBOARD_URL}/auth/login"
    r0 = s.get(login_url, timeout=30)
    token = get_csrf(r0.text)

    data = {"email": KATA_EMAIL, "password": KATA_PASSWORD, "remember": "true"}
    if token:
        data["_token"] = token

    r = s.post(login_url, data=data, timeout=30, allow_redirects=True)
    if "/auth/login" in r.url:
        raise RuntimeError("登录失败：检查 KATA_EMAIL/KATA_PASSWORD")

def main():
    if not KATA_EMAIL or not KATA_PASSWORD:
        raise RuntimeError("缺少 KATA_EMAIL / KATA_PASSWORD（Actions env 未注入？）")
    if not SERVER_ID:
        raise RuntimeError("缺少 KATA_SERVER_ID（Actions env 未注入？）")

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"})

    server_url = f"{DASHBOARD_URL}/servers/edit?id={SERVER_ID}"

    kata_login(s)
    page = s.get(server_url, timeout=30, allow_redirects=True)
    if "/servers/edit" not in page.url:
        raise RuntimeError(f"访问服务器页失败，被重定向到：{page.url}")

    expiry = parse_expiry(page.text)
    if not expiry:
        raise RuntimeError("未解析到 Expiry（页面结构可能变了）")

    days = days_until(expiry)
    if days is None:
        raise RuntimeError(f"到期日无法计算：{expiry}")

    log(f"到期日: {expiry} | 剩余: {days} 天")

    if days > NOTIFY_DAYS:
        log(f"剩余 > {NOTIFY_DAYS} 天，不通知")
        return

    # 关键：需要通知时，如果 TG 没注入，直接失败
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        raise RuntimeError("需要通知但 TG_BOT_TOKEN/TG_CHAT_ID 为空（Actions secrets 未注入到 env）")

    msg = (
        f"[KataBump] {'已过期' if days < 0 else '到期提醒'}\n"
        f"Server: {SERVER_ID}\n"
        f"Expiry: {expiry}\n"
        f"Days: {days}\n"
        f"Executor: {EXECUTOR_NAME}\n"
        f"Link: {server_url}"
    )
    tg_send(msg)
    log("Telegram 已发送")

if __name__ == "__main__":
    main()
