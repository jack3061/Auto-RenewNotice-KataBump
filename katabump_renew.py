#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import requests
from datetime import datetime, timezone, timedelta, date

DASHBOARD_URL = "https://dashboard.katabump.com"

def env(name, default=""):
    return (os.environ.get(name) or default).strip()

KATA_EMAIL    = env("KATA_EMAIL")
KATA_PASSWORD = env("KATA_PASSWORD")
TG_BOT_TOKEN  = env("TG_BOT_TOKEN")
TG_CHAT_ID    = env("TG_CHAT_ID")

SERVER_ID = env("KATA_SERVER_ID") or env("KATABUMP_SERVER_ID") or "199993"
EXECUTOR_NAME = env("EXECUTOR_NAME", "unknown-executor")

TZ = timezone(timedelta(hours=8))


def log(msg: str):
    print(f'[{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


def tg_send(text: str) -> bool:
    """Plain text (no parse_mode) to avoid HTML entity/parse issues."""
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

        return True
    except Exception as e:
        log(f"Telegram 请求异常: {e}")
        return False


def parse_expiry(html: str) -> str | None:
    """Try to locate YYYY-MM-DD near 'Expiry'."""
    if not html:
        return None

    low = html.lower()
    idx = low.find("expiry")
    if idx != -1:
        chunk = html[max(0, idx - 300): idx + 600]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", chunk)
        if m:
            return m.group(1)

    m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    return m.group(1) if m else None


def days_until(yyyy_mm_dd: str) -> int | None:
    try:
        exp = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
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
        raise RuntimeError("登录失败：账号/密码错误或被拦截")
    return True


def main():
    if not KATA_EMAIL or not KATA_PASSWORD:
        log("请设置环境变量：KATA_EMAIL / KATA_PASSWORD")
        sys.exit(1)
    if not SERVER_ID:
        log("请设置环境变量：KATA_SERVER_ID（或 KATABUMP_SERVER_ID）")
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
            raise RuntimeError("未解析到 Expiry 日期（页面结构可能变化）")

        days = days_until(expiry)
        if days is None:
            raise RuntimeError(f"到期日解析失败：{expiry}")

        log(f"到期日：{expiry} | 剩余：{days} 天")

        # Only notify when <=7 days or expired
        if days > 7:
            log("距离到期 > 7 天，不通知")
            return

        status = "已过期" if days < 0 else "到期提醒"
        link = server_url
        msg = (
            f"[KataBump] {status}\n"
            f"Server: {SERVER_ID}\n"
            f"Expiry: {expiry}\n"
            f"Days: {days}\n"
            f"Executor: {EXECUTOR_NAME}\n"
            f"Link: {link}"
        )

        log("准备发送 Telegram 通知...")
        ok = tg_send(msg)
        log("Telegram 已发送" if ok else "Telegram 未发送（见上方错误）")

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
