import os
import sys
import smtplib
import time
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

BAS_URL = os.environ.get("BAS_URL")
SAP_EMAIL = os.environ.get("SAP_EMAIL")
SAP_PASSWORD = os.environ.get("SAP_PASSWORD")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = os.environ.get("SMTP_PORT", "465")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SAP_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

def notify(subject: str, message: str):
    """触发通知推送"""
    print(f"📢 触发通知 -> 主题: {subject}")
    if TG_BOT_TOKEN and TG_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            payload = urllib.parse.urlencode({
                "chat_id": TG_CHAT_ID,
                "text": f"⚠️ *{subject}*\n\n{message}",
                "parse_mode": "Markdown"
            }).encode("utf-8")
            req = urllib.request.Request(tg_url, data=payload)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print("✅ Telegram 警报已发送！")
        except Exception as e:
            print(f"❌ Telegram 发送失败: {e}")

    if SMTP_SERVER and SMTP_USER and SMTP_PASS and TO_EMAIL:
        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = TO_EMAIL
            port = int(SMTP_PORT)
            server = smtplib.SMTP_SSL(SMTP_SERVER, port, timeout=10) if port == 465 else smtplib.SMTP(SMTP_SERVER, port, timeout=10)
            if port != 465:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [TO_EMAIL], msg.as_string())
            server.quit()
            print("✅ 邮件警报已发送！")
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")

if not all([BAS_URL, SAP_EMAIL, SAP_PASSWORD]):
    err = "错误：缺少必要环境变量 (BAS_URL, SAP_EMAIL 或 SAP_PASSWORD)"
    print(err)
    notify("SAP BAS 保活配置异常", err)
    sys.exit(1)

# 穿透 Shadow DOM 与 UI5 组件的通用 JS 点击脚本
JS_CLICK_SCRIPT = """
() => {
    function deepScan(root) {
        if (!root) return false;
        const elements = root.querySelectorAll('*');
        for (let el of elements) {
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const title = (el.getAttribute('title') || '').toLowerCase();
            const icon = (el.getAttribute('icon') || '').toLowerCase();
            const name = (el.getAttribute('name') || '').toLowerCase();
            const id = (el.id || '').toLowerCase();

            // 匹配包含 start 或 play 的启动图标/按钮
            if (aria.includes('start') || title.includes('start') || 
                icon.includes('play') || name.includes('play') || id.includes('start')) {
                
                // 双重触发原生点击事件
                el.click();
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                return true;
            }

            // 递归穿透 Shadow DOM
            if (el.shadowRoot) {
                if (deepScan(el.shadowRoot)) return true;
            }
        }
        return false;
    }
    return deepScan(document);
}
"""

JS_CHECK_RUNNING = """
() => {
    return (document.body.innerText || '').includes('RUNNING');
}
"""

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()

        try:
            print(f"正在访问 BAS: {BAS_URL}")
            page.goto(BAS_URL, wait_until="domcontentloaded", timeout=60000)

            # 检测是否进入 SAP 登录界面
            if "accounts.sap.com" in page.url or "idp" in page.url or page.locator("input[name='j_username']").is_visible():
                print("🔑 检测到登录界面，开始自动输入凭据...")
                
                user_input = page.locator("input[name='j_username'], #j_username, input[type='email']").first
                user_input.fill(SAP_EMAIL)
                
                continue_btn = page.locator("button:has-text('Continue'), #displayNameSubmit")
                if continue_btn.is_visible():
                    continue_btn.click()
                    page.wait_for_timeout(2000)

                pass_input = page.locator("input[name='j_password'], #j_password, input[type='password']").first
                pass_input.fill(SAP_PASSWORD)

                submit_btn = page.locator("#logOnFormSubmit, button[type='submit'], button:has-text('Log On')").first
                submit_btn.click()
                
                print("已提交登录信息，等待页面完全加载...")
                page.wait_for_timeout(10000)

            print("✅ 登录成功，开始全框架 (iframe) 轮询扫描 Dev Space 状态...")
            
            clicked = False
            is_running = False

            # 最长等待 30 秒，每 3 秒遍历所有 iframe 扫描一次
            for attempt in range(10):
                time.sleep(3)
                frames = page.frames
                print(f"🔄 第 {attempt + 1} 次扫描，当前包含 {len(frames)} 个页面框架...")

                # 1. 检查是否已经是 RUNNING 状态
                for frame in frames:
                    try:
                        if frame.evaluate(JS_CHECK_RUNNING):
                            is_running = True
                            break
                    except Exception:
                        pass

                if is_running:
                    print("✅ 检测到 Dev Space 已经处于 RUNNING 状态，无需点击。")
                    page.wait_for_timeout(3000)
                    return

                # 2. 尝试在所有 iframe 里寻找大三角启动图标
                for frame in frames:
                    try:
                        if frame.evaluate(JS_CLICK_SCRIPT):
                            clicked = True
                            break
                    except Exception:
                        pass

                if clicked:
                    print("▶️ 成功在框架中找到并点击大三角启动图标！")
                    print("等待 15 秒等待系统响应...")
                    page.wait_for_timeout(15000)
                    print("🎉 启动指令已成功提交！")
                    return

            if not clicked and not is_running:
                raise Exception("轮询 30 秒未找到 Start 启动图标，可能页面未加载完成或停留在错误界面。")

        except Exception as e:
            err_body = f"保活过程异常:\n{str(e)}"
            print(f"❌ {err_body}")
            page.screenshot(path="failure.png")
            notify("❌ SAP BAS 保活脚本未成功开启 Dev Space", err_body)
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
