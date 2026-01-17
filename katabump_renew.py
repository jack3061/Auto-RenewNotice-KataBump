#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import requests
from datetime import datetime, timezone, timedelta

# 配置
DASHBOARD_URL = 'https://dashboard.katabump.com'
KATA_EMAIL = os.environ.get('KATA_EMAIL', '')
KATA_PASSWORD = os.environ.get('KATA_PASSWORD', '')
SERVER_ID = os.environ.get('KATA_SERVER_ID', '199993')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID', '')
EXECUTOR_NAME = os.environ.get('EXECUTOR_NAME', 'https://ql.api.sld.tw')

# 提醒阈值
ALERT_DAYS = 1


def log(msg):
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{t}] {msg}')


def send_telegram(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log('⚠️ 未配置 Telegram，跳过通知')
        log(f'   TG_BOT_TOKEN: {"已设置" if TG_BOT_TOKEN else "未设置"}')
        log(f'   TG_CHAT_ID: {"已设置" if TG_CHAT_ID else "未设置"}')
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
    patterns = [
        r'>\s*Expiry\s*</div>\s*<div[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</div>',
        r'Expiry\s*</div>\s*<div[^>]*>(\d{4}-\d{2}-\d{2})',
        r'Expiry[\s\S]{0,100}?(\d{4}-\d{2}-\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    
    try:
        log('🔐 登录中...')
        session.get(f'{DASHBOARD_URL}/auth/login', timeout=30)
        login_resp = session.post(
            f'{DASHBOARD_URL}/auth/login',
            data={'email': KATA_EMAIL, 'password': KATA_PASSWORD, 'remember': 'true'},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
            allow_redirects=True
        )
        
        if '/auth/login' in login_resp.url:
            raise Exception('登录失败')
        log('✅ 登录成功')
        
        server_page = session.get(f'{DASHBOARD_URL}/servers/edit?id={SERVER_ID}', timeout=30)
        
        if '/servers/edit' not in server_page.url:
            raise Exception('无法访问服务器页面')
        
        expiry = get_expiry(server_page.text)
        if not expiry:
            raise Exception('无法获取到期时间')
        
        days = days_until(expiry)
        log(f'📅 到期: {expiry} (剩余 {days} 天)')
        
        if days is None:
            log('⚠️ 无法计算天数')
        elif days < 0:
            send_telegram(
                f'🚨 KataBump 已过期！\n\n'
                f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                f'📅 到期: {expiry}\n'
                f'⏰ 已过期: {abs(days)} 天\n'
                f'💻 执行器: {EXECUTOR_NAME}\n\n'
                f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">立即续订</a>'
            )
        elif days <= ALERT_DAYS:
            send_telegram(
                f'⚠️ KataBump 即将到期！\n\n'
                f'🖥 服务器: <code>{SERVER_ID}</code>\n'
                f'📅 到期: {expiry}\n'
                f'⏰ 剩余: {days} 天\n'
                f'💻 执行器: {EXECUTOR_NAME}\n\n'
                f'👉 <a href="{DASHBOARD_URL}/servers/edit?id={SERVER_ID}">立即续订</a>'
            )
        else:
            log(f'✅ 剩余 {days} 天，无需提醒')
    
    except Exception as e:
        log(f'❌ 错误: {e}')
        send_telegram(f'❌ KataBump 出错\n\n🖥 服务器: <code>{SERVER_ID}</code>\n❗ {e}')
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
