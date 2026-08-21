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
                print("已提交登录信息...")
                page.wait_for_timeout(10000)

            print("✅ 登录动作已完成，等待 Dev Space 管理页完全加载...")
            page.wait_for_timeout(15000)

            # 打印控制台诊断信息
            print(f"📍 当前页面真实 URL: {page.url}")
            print(f"📄 当前页面 Title: {page.title()}")

            # 自动清理可能的弹窗遮挡
            close_btns = page.locator("button:has-text('Accept'), button:has-text('OK'), button:has-text('Dismiss'), button:has-text('Close')")
            if close_btns.count() > 0 and close_btns.first.is_visible():
                print("🧹 检测到弹窗，尝试自动关闭...")
                close_btns.first.click()
                page.wait_for_timeout(2000)

            # 1. 检查是否处于 RUNNING 状态
            is_running = page.locator("text=RUNNING").count() > 0 or page.evaluate("() => (document.body.innerText || '').includes('RUNNING')")
            if is_running:
                print("✅ 检测到 Dev Space 处于 RUNNING (运行中) 状态，无需点击。")
                page.wait_for_timeout(3000)
                return

            # 2. 定位策略 A：直接锁定 STOPPED 所在的行，点击该行右侧的启动图标
            print("🔍 尝试定位包含 STOPPED 状态的 Dev Space 行...")
            stopped_element = page.locator("text=STOPPED").first
            if stopped_element.is_visible():
                print("🎯 成功精准找到 STOPPED 状态标识！尝试提取所在的整行列表项...")
                row = stopped_element.locator("xpath=ancestor::*[contains(@class, 'row') or contains(@class, 'item') or self::tr or self::div][1]")
                start_in_row = row.locator("[title*='Start' i], [aria-label*='Start' i], ui5-button, button, svg").first
                if start_in_row.is_visible():
                    print("▶️ 在 STOPPED 行内定位到大三角启动按钮，强行触发点击！")
                    start_in_row.click(force=True)
                    page.wait_for_timeout(15000)
                    print("🎉 启动指令已成功发送！")
                    return

            # 3. 定位策略 B：全局模糊多属性强行点击
            print("🔍 执行全局多属性穿透搜索...")
            candidates = page.locator("[title*='Start' i], [aria-label*='Start' i], [icon*='play' i], ui5-button[icon='play']")
            count = candidates.count()
            print(f"📊 找到 {count} 个候选启动按钮")

            if count > 0:
                for i in range(count):
                    item = candidates.nth(i)
                    if item.is_visible():
                        print(f"▶️ 正在强行点击第 {i+1} 个候选启动按钮...")
                        item.click(force=True)
                        page.wait_for_timeout(15000)
                        print("🎉 启动指令已成功发送！")
                        return

            # 4. 定位策略 C：原生 JS 穿透点击
            print("🔍 执行原生 JS 深度节点扫描...")
            click_success = page.evaluate("""() => {
                function clickStart(root) {
                    if (!root) return false;
                    const all = root.querySelectorAll('*');
                    for (let el of all) {
                        const title = (el.getAttribute('title') || '').toLowerCase();
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const icon = (el.getAttribute('icon') || '').toLowerCase();
                        
                        if (title.includes('start') || aria.includes('start') || icon.includes('play')) {
                            el.click();
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            return true;
                        }
                        if (el.shadowRoot && clickStart(el.shadowRoot)) return true;
                    }
                    return false;
                }
                return clickStart(document);
            }""")

            if click_success:
                print("▶️ 原生 JS 成功触发出启动按钮点击！")
                page.wait_for_timeout(15000)
                print("🎉 启动指令已成功发送！")
                return

            # 若上述全部失效，在控制台打印当前页面文本，直接展示真实原因
            body_text = page.evaluate("() => (document.body.innerText || '').slice(0, 400)")
            print(f"⚠️ 页面前 400 字文本内容预览:\n{body_text}")
            raise Exception("未找到 STOPPED 状态或 Start 按钮，请查看上方日志打印的页面预览。")

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
