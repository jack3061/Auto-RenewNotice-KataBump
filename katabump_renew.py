#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

DASHBOARD_URL = "https://dashboard.katabump.com"
TZ = timezone(timedelta(hours=8))

def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

KATA_EMAIL    = env("KATA_EMAIL")
KATA_PASSWORD = env("KATA_PASSWORD")
TG_BOT_TOKEN  = env("TG_BOT_TOKEN")
TG_CHAT_ID    = env("TG_CHAT_ID")
SERVER_ID     = env("KATA_SERVER_ID") or env("KATABUMP_SERVER_ID") or "199993"
EXECUTOR_NAME = env("EXECUTOR_NAME", "unknown")

def log(msg: str):
    print(f'[{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)

def tg_send(text: str) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("Telegram 未配置（TG_BOT_TOKEN/TG_CHAT_ID），跳过通知")
        return False

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    try:
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
    except Exception as e:
        log(f"Telegram 请求异常: {e}")
        return False

def parse_expiry(html: str) -> Optional[str]:
    if not html:
        return None

    # 优先：在 “Expiry” 附近找日期
    low = html.lower()
    idx = low.find("expiry")
    if idx != -1:
        chunk = html[max(0, idx - 400): idx + 800]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", chunk)
        if m:
            return m.group(1)

    # 兜底：全页找第一个 YYYY-MM-DD
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
    session.get(f"{DASHBOARD_URL}/auth/login", timeout=30)
    r = session.post(
        f"{DASHBOARD_URL}/auth/login",
        data={"email": KATA_EMAIL, "password": KATA_PASSWORD, "remember": "true"},
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": DASHBOARD_URL,
            "Referer": f"{DASHBOARD_URL}/auth/login",
        },
        timeout=30,
        allow_redirects=True,
    )
    if "/auth/login" in r.url:
        raise RuntimeError("登录失败：检查 KATA_EMAIL / KATA_PASSWORD")

def main():
    log(f"Python: {sys.version.split()[0]}")
    if not KATA_EMAIL or not KATA_PASSWORD:
        log("缺少环境变量：KATA_EMAIL / KATA_PASSWORD")
        sys.exit(1)

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    try:
        log(f"KataBump 到期检查 | SERVER_ID={SERVER_ID}")
        kata_login(s)

        server_url = f"{DASHBOARD_URL}/servers/edit?id={SERVER_ID}"
        r = s.get(server_url, timeout=30, allow_redirects=True)
        if "/servers/edit" not in r.url:
            raise RuntimeError(f"访问服务器页面失败，被重定向到：{r.url}")

        expiry = parse_expiry(r.text)
        if not expiry:
            raise RuntimeError("未解析到 Expiry（页面结构可能变了）")

        days = days_until(expiry)
        if days is None:
            raise RuntimeError(f"到期日无法计算：{expiry}")

        log(f"到期日：{expiry} | 剩余：{days} 天")

        if days > 7:
            log("剩余 > 7 天，不通知")
            return

        msg = (
            f"[KataBump] {'已过期' if days < 0 else '到期提醒'}\n"
            f"Server: {SERVER_ID}\n"
            f"Expiry: {expiry}\n"
            f"Days: {days}\n"
            f"Executor: {EXECUTOR_NAME}\n"
            f"Link: {server_url}"
        )
        tg_send(msg)

    except Exception as e:
        log(f"脚本错误：{e}")
        tg_send(
            f"[KataBump] Error\n"
            f"Server: {SERVER_ID}\n"
            f"Executor: {EXECUTOR_NAME}\n"
            f"Error: {e}"
        )
        raise

if __name__ == "__main__":
    main()
