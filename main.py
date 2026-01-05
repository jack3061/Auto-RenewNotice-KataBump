# 文件名: main.py
from DrissionPage import ChromiumPage, ChromiumOptions
import time
import requests
import os

# 从 GitHub Secrets 读取敏感信息
USERNAME = os.environ.get("KB_USER")
PASSWORD = os.environ.get("KB_PASS")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

def send_telegram(msg):
    if not TG_BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg})
        print("Telegram 通知发送成功")
    except:
        pass

def main():
    print(">>> 初始化环境...")
    co = ChromiumOptions()
    
    # 核心设置：
    # 在 GitHub Actions + Xvfb 环境下，我们不需要开启 headless
    # 伪装成有界面的普通浏览器
    co.set_headless(False) 
    
    # Linux 环境下的必要参数，防止权限报错
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')

    # 启动浏览器
    page = ChromiumPage(co)

    try:
        print(">>> 访问目标网站...")
        page.get('https://dashboard.katabump.com/')

        # 1. 登录逻辑
        if "login" in page.url or page.ele('text:Login'):
            print("正在登录...")
            page.ele('@name=email').input(USERNAME)
            page.ele('@name=password').input(PASSWORD)
            page.ele('tag:button@@type=submit').click()
            time.sleep(5) # 等待跳转

        # 2. 点击列表 Renew
        print("寻找列表 Renew 按钮...")
        # 寻找包含 Renew 文本的按钮
        list_renew_btn = page.ele('tag:button@@text():Renew')
        if list_renew_btn:
            list_renew_btn.click()
            print("已点击列表 Renew，等待弹窗...")
        else:
            raise Exception("未找到列表 Renew 按钮")

        # 3. 处理弹窗 Cloudflare (核心)
        print("等待 Cloudflare 弹窗加载...")
        # 等待你截图里的那行字出现
        page.wait.ele('text:This will extend the life of your server', timeout=15)
        
        # 寻找 iframe
        iframe = page.get_frame('@src^https://challenges.cloudflare.com')
        if iframe:
            print("检测到 Cloudflare，尝试点击...")
            time.sleep(2)
            iframe.ele('tag:body').click()
            print("点击完成，等待验证生效...")
            time.sleep(5)
        else:
            print("未检测到 CF iframe，可能无感通过。")

        # 4. 点击最终确认
        print("寻找确认按钮...")
        # 获取所有 Renew 按钮，取最后一个（弹窗里的那个）
        all_btns = page.eles('tag:button@@text():Renew')
        if all_btns:
            all_btns[-1].click()
            print("✅ 最终确认按钮已点击！")
            
            # 简单验证成功
            time.sleep(3)
            # 截图作为证据 (Actions 运行完可以在 Artifacts 里下载看到)
            page.get_screenshot('success.jpg')
            send_telegram(f"✅ GitHub Actions: Renew 任务执行成功！\n账号: {USERNAME}")
        else:
            raise Exception("未找到弹窗内的确认按钮")

    except Exception as e:
        err = f"❌ 任务失败: {str(e)}"
        print(err)
        page.get_screenshot('error.jpg')
        send_telegram(err)
        # 让 GitHub Actions 显示为失败
        exit(1)
        
    finally:
        page.quit()

if __name__ == '__main__':
    main()
