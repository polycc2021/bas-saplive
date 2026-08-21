import os
import sys
import smtplib
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
SMTP_PASS = os.environ.get("SMTP_PASS")
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
                
                print("已提交登录信息，等待页面重定向...")
                page.wait_for_timeout(10000)

            print("✅ 登录成功，等待 Dev Space 列表渲染...")
            
            # 兼容 UI5 框架的加载过程
            page.wait_for_timeout(15000)

            # 通配定位：精准搜寻带 Start 属性或三角 Play 图标的 UI5 组件/按钮
            start_locator = page.locator(
                "[title*='Start'], [aria-label*='Start'], "
                "ui5-button[icon*='play'], ui5-icon[name*='play'], "
                "*[data-aria-label*='Start']"
            )

            # 校验是否已在 RUNNING 状态
            is_running = page.locator("text=RUNNING, [title*='Stop'], [aria-label*='Stop']").count() > 0

            if start_locator.count() > 0 and start_locator.first.is_visible():
                print("▶️ 精准找到启动按钮/大三角图标，正在点击开启 Dev Space...")
                start_locator.first.click()
                print("已成功点击！等待 15 秒确认启动...")
                page.wait_for_timeout(15000)
                print("🎉 保活与开机指令已成功提交！")
            elif is_running:
                print("✅ 检测到 Dev Space 已经处于 RUNNING 状态，无需点击开机。")
                page.wait_for_timeout(5000)
            else:
                # 备用方案：尝试直接按 title 属性点击
                try:
                    print("⚠️ 尝试使用备用方法点击 Start 图标...")
                    page.get_by_title("Start", exact=False).first.click()
                    print("🎉 备用点击成功！")
                except Exception:
                    raise Exception("无法定位到三角启动图标 (Start)，请检查 failure.png 截图确定页面状态。")

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
