from DrissionPage import ChromiumPage, ChromiumOptions
import time
import requests
import os

# --- 环境变量 ---
USERNAME = os.environ.get("KB_USER")
PASSWORD = os.environ.get("KB_PASS")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

def send_telegram(msg):
    if not TG_BOT_TOKEN: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": msg},
            timeout=10
        )
        print(f"📡 TG通知已发送: {msg}")
    except Exception as e:
        print(f"⚠️ TG发送失败: {e}")

def solve_cloudflare(page):
    """
    深度处理 Cloudflare Turnstile
    返回: True (成功) / False (失败)
    """
    print("🛡️ 开始处理 Cloudflare 验证...")
    
    # 尝试多次寻找 iframe
    for i in range(5):
        # Cloudflare iframe 特征
        iframe = page.get_frame('@src^https://challenges.cloudflare.com')
        
        if iframe:
            print("   👉 捕获到验证 iframe")
            try:
                # 尝试定位点击区域 (通常是 body 或者 checkbox wrapper)
                # 技巧：直接点击 iframe 中心偏左的位置，避开边缘
                body = iframe.ele('tag:body')
                if body:
                    # 模拟鼠标移动过去
                    body.hover()
                    time.sleep(0.5)
                    # 点击！
                    body.click()
                    print("   🖱️ 已模拟鼠标点击验证框")
                    
                    # --- 关键修正：等待验证通过 ---
                    # 点击后，通常验证框会变，或者 iframe 会消失，或者 Renew 按钮变色
                    # 这里我们给足 8 秒缓冲，这是通过率最高的“笨办法”
                    # 如果能检测到 checkbox 变成 checked 状态更好，但 CF 结构经常变
                    print("   ⏳ 等待 Cloudflare 验证结果 (8秒)...")
                    time.sleep(8)
                    return True
            except Exception as e:
                print(f"   ⚠️ 点击异常: {e}")
        
        time.sleep(2)
        print(f"   Searching for CF iframe... ({i+1}/5)")
    
    # 如果循环结束还没找到 iframe，可能根本没弹验证，或者已经通过了
    print("   ℹ️ 未检测到验证框，假设已通过或无感验证")
    return True

def main():
    print("🚀 启动自动化 Renew 任务 (DrissionPage V2)...")
    
    co = ChromiumOptions()
    # 必须为 False，配合 Xvfb 使用，欺骗性最强
    co.set_headless(False)
    # 针对 Linux/Docker 环境的必要参数
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    # 保持窗口最大化，防止按钮被遮挡
    co.set_argument('--start-maximized')
    
    page = ChromiumPage(co)
    # 设置全局超时，防止卡死
    page.timeout = 20

    try:
        # 1. 访问与登录
        print("🌐 访问 Dashboard...")
        page.get('https://dashboard.katabump.com/')
        
        if "login" in page.url or page.ele('text:Login'):
            print("🔑 检测到未登录，执行登录...")
            page.ele('@name=email').input(USERNAME)
            page.ele('@name=password').input(PASSWORD)
            # 点击登录
            page.ele('tag:button@@type=submit').click()
            
            # 登录后可能直接弹 CF，先处理一次
            solve_cloudflare(page)
            # 等待 Dashboard 加载
            page.wait.url_change('login', timeout=10)

        # 2. 寻找列表中的 Renew 按钮
        print("🔍 寻找服务器列表 Renew 按钮...")
        # 等待页面元素加载
        page.wait.ele('tag:button@@text():Renew', timeout=15)
        
        # 获取所有 Renew 按钮
        renew_btns = page.eles('tag:button@@text():Renew')
        if not renew_btns:
            raise Exception("未找到任何 Renew 按钮")
            
        # 点击列表里的第一个 Renew (通常列表里的是第一个)
        # 注意：如果有多个服务器，可能需要更精确的选择器
        renew_btns[0].click()
        print("✅ 已点击列表 Renew，等待弹窗...")

        # 3. 弹窗处理 (核心)
        print("📦 等待弹窗加载...")
        # 等待弹窗内特定文字出现
        page.wait.ele('text:This will extend', timeout=10)
        
        # !!! 调用强化版验证处理 !!!
        solve_cloudflare(page)

        # 4. 点击最终确认 (蓝色按钮)
        print("🎯 准备点击最终确认...")
        
        # 再次获取所有 Renew 按钮
        # 此时页面上应该有两个 Renew 按钮：一个是背景列表里的，一个是弹窗里的
        # 弹窗里的通常在 DOM 结构的最后面
        all_btns = page.eles('tag:button@@text():Renew')
        
        if all_btns:
            final_btn = all_btns[-1] # 取最后一个
            
            # 检查按钮是否可点击
            # 有时候 CF 没过，按钮可能是 disabled 状态
            if final_btn.states.is_enabled:
                final_btn.click()
                print("✅ 最终 Renew 按钮已点击！")
                
                # 5. 结果验证
                time.sleep(5)
                # 截图取证
                page.get_screenshot('final_result.jpg')
                
                # 简单判断：如果弹窗里的文字不见了，或者出现 Success
                if not page.ele('text:This will extend'):
                     send_telegram(f"🎉 成功: {USERNAME} 服务器已续期！")
                else:
                     send_telegram("⚠️ 警告: 点击了续期，但弹窗似乎未关闭，请检查截图。")
            else:
                raise Exception("最终 Renew 按钮不可点击 (可能是 CF 验证未通过)")
        else:
            raise Exception("未找到弹窗内的确认按钮")

    except Exception as e:
        err_msg = f"❌ 任务崩溃: {str(e)}"
        print(err_msg)
        page.get_screenshot('error_crash.jpg')
        send_telegram(err_msg)
        exit(1) # 退出码 1，通知 GitHub Action 失败
        
    finally:
        page.quit()

if __name__ == '__main__':
    main()
