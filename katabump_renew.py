#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import requests
from datetime import datetime, timezone, timedelta

# 配置
DASHBOARD_URL = 'https://dashboard.katabump.com'
SERVER_ID = os.environ.get('KATA_SERVER_ID', '199993')
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID', '')

# 执行器配置
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'https://ql.api.sld.tw')


def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')


def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log('⚠️ 未配置 Telegram，跳过通知')
        return False
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage',
            json={'chat_id': TG_CHAT_ID, 'text': message, 'parse_mode': 'HTML'},
            timeout=30
        )
        if resp.status_code == 200:
            log('✅ Telegram 通知已发送')
            return True
        else:
            log(f'❌ Telegram 发送失败: {resp.status_code}')
            return False
    except Exception as e:
        log(f'❌ Telegram 错误: {e}')
        return False


def get_expiry(html):
    match = re.search(r'Expiry[\s\S]*?(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
    return match.group(1) if match else None


def days_until(date_str):
    try:
        exp = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (exp - today).days
    except (ValueError, TypeError):
        return None


def run():
    log('🚀 KataBump 到期提醒')
    log(f'🖥 服务器 ID: {SERVER_ID}')
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    
    try:
        # ========== 登录 ==========
        log('🔐 登录中...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={
                'email': KATA_EMAIL,
                'password': KATA_PASSWORD,
                'remember': 'true'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': DASHBOARD_URL,
                'Referer': f'{DASHBOARD_URL}/auth/login',
            },
            timeout=30,
            allow_redirects=True
        )
        
        log(f'📍 登录后URL: {login_resp.url}')
        log(f'🍪 Cookies: {list(session.cookies.keys())}')
        
        if '/auth/login' in login_resp.url:
            raise Exception('登录失败，请检查账号密码')
        
        log('✅ 登录成功')
        
        # ========== 获取服务器信息 ==========
        server_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}', timeout=30)
        
        expiry = get_expiry(server_page.text)
        
        if not expiry:
            raise Exception('无法获取到期时间，页面结构可能已变更')
        
        days = days_until(expiry)
        
        if days is not None:
            log(f'📅 到期: {expiry} (剩余 {days} 天)')
        else:
            log(f'📅 到期: {expiry} (无法计算剩余天数)')
        
        # ========== 发送提醒 ==========
        if days is None:
            log('⚠️ 无法计算天数，跳过提醒')
        elif days < 0:
            send_telegram(
                f'🚨 KataBump 已过期！\n\n'
                f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                f'📅 到期: {expiry}\n'
                f'⏰ 已过期: {abs(days)} 天\n'
                f'💻 执行器: {EXECUTOR_NAME}\n\n'
                f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">立即处理</a>'
            )
        elif days <= 7:
            send_telegram(
                f'ℹ️ KataBump 到期提醒\n\n'
                f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                f'📅 到期: {expiry}\n'
                f'⏰ 剩余: {days} 天\n'
                f'💻 执行器: {EXECUTOR_NAME}\n\n'
                f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">查看详情</a>'
            )
        else:
            log(f'ℹ️ 距离到期还有 {days} 天，无需提醒')
    
    except Exception as e:
        log(f'❌ 错误: {e}')
        send_telegram(
            f'❌ KataBump 出错\n\n'
            f'🖥 服务器: <code>{SERVER_ID}</code>\n'
            f'❗ {e}\n'
            f'💻 执行器: {EXECUTOR_NAME}'
        )
        raise


def main():
    log('=' * 50)
    log('   KataBump 到期提醒脚本')
    log('=' * 50)
    
    if not KATA_EMAIL or not KATA_PASSWORD:
        log('❌ 请设置 KATA_EMAIL 和 KATA_PASSWORD')
        sys.exit(1)
    
    run()
    log('🏁 完成')


if __name__ == '__main__':
    main()
