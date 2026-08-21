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

            # 1. 登录处理
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

            # 2. 显式强力等待 Dev Space 核心标志加载完成
            print("✅ 等待 Dev Spaces 管理列表完全渲染...")
            page.wait_for_selector("text=Create Dev Space", timeout=60000)
            page.wait_for_timeout(5000) # 缓冲 5 秒让状态图标渲染完

            # 3. 检查是否已经是 RUNNING 状态
            if page.locator("text=RUNNING").is_visible():
                print("✅ 检测到 Dev Space 处于 RUNNING (运行中) 状态，无需重复开启。")
                page.wait_for_timeout(3000)
                return

            # 4. 精准寻找并点击 Dev Space 右侧的大三角启动图标
            print("🔍 正在定位 Dev Space 启动图标...")
            
            start_clicked = False

            # 策略 A：按 title / aria-label 属性匹配 Start 按钮
            start_btn = page.locator("[title*='Start' i], [aria-label*='Start' i]").first
            if start_btn.is_visible():
                print("▶️ [策略 A] 成功定位到 Start 属性图标，发送点击指令...")
                start_btn.click(force=True)
                start_clicked = True

            # 策略 B：定位 STOPPED 状态单元格所在的整行，强行点击右侧按钮/图标
            if not start_clicked and page.locator("text=STOPPED").is_visible():
                print("▶️ [策略 B] 锁定 STOPPED 卡片整行，点击操作区启动按钮...")
                row = page.locator("text=STOPPED").locator("xpath=ancestor::*[contains(@class, 'row') or contains(@class, 'card') or contains(@class, 'item') or self::div][2]")
                action_btn = row.locator("button, ui5-button, [role='button'], svg").first
                action_btn.click(force=True)
                start_clicked = True

            # 策略 C：备用原生 JS 深度遍历点击
            if not start_clicked:
                print("▶️ [策略 C] 执行 Shadow DOM 深度扫描点击...")
                start_clicked = page.evaluate("""() => {
                    function findPlay(root) {
                        if (!root) return false;
                        const elems = root.querySelectorAll('*');
                        for (let el of elems) {
                            const t = (el.getAttribute('title') || '').toLowerCase();
                            const a = (el.getAttribute('aria-label') || '').toLowerCase();
                            if (t.includes('start') || a.includes('start')) {
                                el.click();
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                                return true;
                            }
                            if (el.shadowRoot && findPlay(el.shadowRoot)) return true;
                        }
                        return false;
                    }
                    return findPlay(document);
                }""")

            if start_clicked:
                print("🎉 成功向 SAP 发送启动指令！等待 15 秒确认开机流程...")
                page.wait_for_timeout(15000)
                print("🎉 保活与开机任务顺利完成！")
            else:
                raise Exception("页面已加载，但未能成功点击 Dev Space 启动图标。")

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
