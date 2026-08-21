import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BAS_URL = os.getenv(
    "BAS_URL",
    "https://9a18409etrial.us10cf.trial.applicationstudio.cloud.sap"
)

BAS_USERNAME = os.getenv("BAS_USERNAME")
BAS_PASSWORD = os.getenv("BAS_PASSWORD")

BAS_DEVSPACE = os.getenv("BAS_DEVSPACE", "yesdo")
BAS_PROFILE = os.getenv("BAS_PROFILE", "")

HEADLESS = True


def log(message):
    print(f"[BAS] {message}", flush=True)


def login(page):
    log("打开 SAP Business Application Studio...")

    page.goto(
        BAS_URL + "/index.html",
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(3000)

    # 如果已经登录，直接进入
    if "workspace-manager" in page.url:
        log("已经处于登录状态。")
        return

    # 检查是否出现登录页面
    if page.get_by_label("Email or User Name").count() == 0:

        # 如果有身份提供商选择页面
        if BAS_PROFILE:
            log(f"选择身份提供商：{BAS_PROFILE}")

            try:
                page.get_by_text(
                    BAS_PROFILE,
                    exact=False
                ).first.click(timeout=15000)
            except PlaywrightTimeoutError:
                log("没有找到指定身份提供商，继续尝试当前页面。")

        page.wait_for_timeout(2000)

    # 输入用户名
    if page.get_by_label("Email or User Name").count() > 0:

        log("输入 BAS 用户名...")

        page.get_by_label(
            "Email or User Name"
        ).fill(BAS_USERNAME)

        page.get_by_label(
            "Password"
        ).fill(BAS_PASSWORD)

        # Keep me signed in
        try:
            checkbox = page.get_by_text(
                "Keep me signed in",
                exact=False
            )

            if checkbox.count() > 0:
                checkbox.first.click()
        except Exception:
            pass

        page.wait_for_timeout(500)

        log("提交登录...")

        page.get_by_text(
            "Continue",
            exact=True
        ).click()

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(5000)

    log(f"登录完成，当前地址：{page.url}")


def open_workspace_manager(page):
    manager_url = BAS_URL + "/workspace-manager-ui/"

    log("打开 Dev Space Manager...")
    page.goto(
        manager_url,
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(5000)

    log(f"Dev Space Manager 地址：{page.url}")


def find_devspace(page):
    log(f"寻找 Dev Space：{BAS_DEVSPACE}")

    try:
        row = page.locator(
            f'div.dev-spaces-row:has-text("{BAS_DEVSPACE}")'
        ).first

        row.wait_for(
            state="visible",
            timeout=30000
        )

        log("找到目标 Dev Space。")
        return row

    except PlaywrightTimeoutError:
        log("找不到目标 Dev Space。")
        return None


def get_status(row):
    for status in ["RUNNING", "STARTING", "STOPPED", "STOPPING", "ERROR"]:

        try:
            element = row.locator(
                f'div.text-center a:has-text("{status}")'
            )

            if element.is_visible(timeout=2000):
                return status

        except Exception:
            pass

    return "UNKNOWN"


def start_devspace(page, row):
    status = get_status(row)

    log(f"当前 Dev Space 状态：{status}")

    if status == "RUNNING":
        log("Dev Space 已经是 RUNNING，无需启动。")
        return True

    if status == "STARTING":
        log("Dev Space 正在启动，等待...")
    elif status == "STOPPING":
        log("Dev Space 正在停止，等待...")
    elif status == "STOPPED":

        log("Dev Space 已停止，准备点击启动按钮...")

        try:
            button = row.locator(
                'button[id^="startButton"]'
            ).first

            button.wait_for(
                state="visible",
                timeout=15000
            )

            button.click()

            log("已经点击启动按钮。")

        except Exception as e:
            log(f"点击启动按钮失败：{e}")
            return False

    elif status == "ERROR":
        log("Dev Space 当前为 ERROR 状态，无法正常自动启动。")
        return False

    # 等待启动完成
    for i in range(60):

        time.sleep(5)

        status = get_status(row)

        log(
            f"等待 Dev Space 启动 "
            f"({i + 1}/60)，当前状态：{status}"
        )

        if status == "RUNNING":
            log("================================")
            log("Dev Space 已成功启动！")
            log("================================")
            return True

        if status == "ERROR":
            log("Dev Space 启动失败，状态变为 ERROR。")
            return False

    log("等待启动超时。")
    return False


def touch_workspace(page, row):
    """
    启动后打开 Dev Space。
    这样可以产生一次实际的 workspace 访问。
    """

    try:
        log("打开 Dev Space Workspace...")

        link = row.locator(
            f'a:has-text("{BAS_DEVSPACE}")'
        ).first

        if link.count() > 0:
            link.click()

            page.wait_for_timeout(15000)

            log("Workspace 已打开/访问。")

    except Exception as e:
        log(f"打开 Workspace 时出现提示：{e}")


def main():

    if not BAS_USERNAME:
        print("错误：没有设置 BAS_USERNAME")
        sys.exit(1)

    if not BAS_PASSWORD:
        print("错误：没有设置 BAS_PASSWORD")
        sys.exit(1)

    log("================================")
    log("SAP BAS Dev Space Keep Alive")
    log("================================")
    log(f"BAS：{BAS_URL}")
    log(f"Dev Space：{BAS_DEVSPACE}")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS
        )

        context = browser.new_context(
            viewport={
                "width": 1366,
                "height": 768
            }
        )

        page = context.new_page()

        try:

            login(page)

            open_workspace_manager(page)

            row = find_devspace(page)

            if row is None:
                sys.exit(1)

            success = start_devspace(
                page,
                row
            )

            if not success:
                sys.exit(1)

            # 刷新一次页面，确认状态
            page.wait_for_timeout(5000)
            page.reload(
                wait_until="domcontentloaded",
                timeout=120000
            )

            page.wait_for_timeout(5000)

            row = find_devspace(page)

            if row:
                final_status = get_status(row)
                log(f"最终状态：{final_status}")

                if final_status == "RUNNING":
                    touch_workspace(
                        page,
                        row
                    )

            log("任务完成。")

        except Exception as e:

            log("发生异常：")
            log(str(e))

            # 输出当前页面，方便 GitHub Actions 调试
            try:
                page.screenshot(
                    path="bas_error.png",
                    full_page=True
                )

                log("错误截图已保存为 bas_error.png")

            except Exception:
                pass

            sys.exit(1)

        finally:

            context.close()
            browser.close()


if __name__ == "__main__":
    main()
