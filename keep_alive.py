import os
import sys
import time
import json

from playwright.sync_api import sync_playwright


# ============================================================
# 环境变量
# ============================================================

BAS_URL = os.getenv(
    "BAS_URL",
    "https://9a18409etrial.us10cf.trial.applicationstudio.cloud.sap"
).rstrip("/")

BAS_USERNAME = os.getenv("BAS_USERNAME")
BAS_PASSWORD = os.getenv("BAS_PASSWORD")

DEVSPACE_NAME = os.getenv(
    "BAS_DEVSPACE",
    "yesdo"
)

DEVSPACE_ID = os.getenv(
    "BAS_DEVSPACE_ID",
    "ws-a2zlg"
)


# ============================================================
# 日志
# ============================================================

def log(message):
    print(f"[BAS] {message}", flush=True)


# ============================================================
# 检查环境变量
# ============================================================

def check_environment():

    missing = []

    if not BAS_URL:
        missing.append("BAS_URL")

    if not BAS_USERNAME:
        missing.append("BAS_USERNAME")

    if not BAS_PASSWORD:
        missing.append("BAS_PASSWORD")

    if not DEVSPACE_ID:
        missing.append("BAS_DEVSPACE_ID")

    if missing:

        log(
            "缺少 GitHub Secrets："
            + ", ".join(missing)
        )

        sys.exit(1)


# ============================================================
# 找用户名输入框
# ============================================================

def find_username_input(page):

    selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="username"]',
        'input[autocomplete="username"]',
        'input[placeholder*="Email"]',
        'input[placeholder*="email"]',
        'input[placeholder*="User"]',
        'input[placeholder*="user"]'
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1000
            ):

                return locator

        except Exception:
            pass

    return None


# ============================================================
# 找密码输入框
# ============================================================

def find_password_input(page):

    selectors = [
        'input[type="password"]',
        'input[name="password"]',
        'input[autocomplete="current-password"]'
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1000
            ):

                return locator

        except Exception:
            pass

    return None


# ============================================================
# 点击 Continue / Sign In
# ============================================================

def click_continue(page):

    selectors = [
        'button:has-text("Continue")',
        'button:has-text("Sign In")',
        'button:has-text("Sign in")',
        'button:has-text("Log On")',
        'button[type="submit"]',
        'input[type="submit"]'
    ]

    for selector in selectors:

        try:

            button = page.locator(
                selector
            ).first

            if button.is_visible(
                timeout=1000
            ):

                button.click()

                return True

        except Exception:
            pass

    try:

        page.keyboard.press("Enter")

        return True

    except Exception:

        return False


# ============================================================
# SAP 登录
# ============================================================

def login(page):

    log(
        "打开 SAP Business Application Studio..."
    )

    page.goto(
        BAS_URL + "/index.html",
        wait_until="domcontentloaded",
        timeout=120000
    )

    log(
        f"初始页面：{page.url}"
    )

    page.wait_for_timeout(5000)

    log(
        f"当前页面：{page.url}"
    )

    # --------------------------------------------------------
    # 用户名
    # --------------------------------------------------------

    username_input = find_username_input(
        page
    )

    if username_input:

        log(
            "发现 SAP 用户名输入框。"
        )

        username_input.fill(
            BAS_USERNAME
        )

        log(
            "用户名已经填写。"
        )

        click_continue(
            page
        )

        page.wait_for_timeout(
            3000
        )

    # --------------------------------------------------------
    # 密码
    # --------------------------------------------------------

    password_input = find_password_input(
        page
    )

    if password_input:

        log(
            "发现 SAP 密码输入框。"
        )

        password_input.fill(
            BAS_PASSWORD
        )

        log(
            "密码已经填写。"
        )

        click_continue(
            page
        )

    # --------------------------------------------------------
    # 等待登录完成
    # --------------------------------------------------------

    log(
        "等待 SAP 完成登录..."
    )

    for i in range(30):

        page.wait_for_timeout(
            2000
        )

        current_url = page.url

        log(
            f"登录等待 {i + 1}/30：{current_url}"
        )

        if (
            "applicationstudio.cloud.sap"
            in current_url
            and
            "accounts.sap.com"
            not in current_url
        ):

            log(
                "SAP 登录成功。"
            )

            return True

    log(
        "SAP 登录失败。"
    )

    try:

        page.screenshot(
            path="sap_login_failed.png",
            full_page=True
        )

    except Exception:
        pass

    return False


# ============================================================
# 获取 JWT
# ============================================================

def get_jwt(context):

    log(
        "获取 SAP BAS JWT..."
    )

    response = context.request.get(
        BAS_URL + "/jwt",
        timeout=60000
    )

    log(
        f"JWT HTTP 状态码：{response.status}"
    )

    if response.status != 200:

        log(
            response.text()[:3000]
        )

        return None

    try:

        data = response.json()

    except Exception:

        text = response.text().strip()

        if text:
            return text

        return None

    if isinstance(data, dict):

        if data.get("value"):
            return data["value"]

        if data.get("token"):
            return data["token"]

        if data.get("jwt"):
            return data["jwt"]

    if isinstance(data, str):

        return data

    return None


# ============================================================
# 查询 Workspace
# ============================================================

def get_workspace(context, jwt):

    url = (
        BAS_URL
        + "/ws-manager/api/v1/workspace?all=true"
    )

    log(
        "查询 Dev Space..."
    )

    response = context.request.get(
        url,
        headers={
            "X-Approuter-Authorization":
                f"Bearer {jwt}"
        },
        timeout=60000
    )

    log(
        f"Workspace API 状态码：{response.status}"
    )

    if response.status != 200:

        log(
            response.text()[:5000]
        )

        return None

    try:

        data = response.json()

    except Exception as e:

        log(
            f"JSON 解析失败：{e}"
        )

        return None

    if not isinstance(data, list):

        log(
            "Workspace API 返回格式异常。"
        )

        return None

    log(
        f"API 返回 Workspace 数量：{len(data)}"
    )

    # ========================================================
    # 查找目标 Dev Space
    # ========================================================

    for workspace in data:

        if not isinstance(
            workspace,
            dict
        ):
            continue

        config = workspace.get(
            "config",
            {}
        )

        labels = config.get(
            "labels",
            {}
        )

        workspace_id = config.get(
            "id"
        )

        username = config.get(
            "username"
        )

        display_name = labels.get(
            "ws-manager.devx.sap.com/displayname"
        )

        log(
            "------------------------------------------"
        )

        log(
            f"Workspace ID : {workspace_id}"
        )

        log(
            f"Display Name : {display_name}"
        )

        log(
            f"Username     : {username}"
        )

        if str(workspace_id) == str(DEVSPACE_ID):

            log(
                "找到目标 Dev Space！"
            )

            return workspace

        if (
            display_name
            and
            str(display_name)
            == str(DEVSPACE_NAME)
        ):

            log(
                "通过名称找到目标 Dev Space！"
            )

            return workspace

    log(
        "没有找到目标 Dev Space。"
    )

    return None


# ============================================================
# 获取 Dev Space 状态
# ============================================================

def get_status(workspace):

    if not workspace:
        return "UNKNOWN"

    runtime = workspace.get(
        "runtime",
        {}
    )

    status = runtime.get(
        "status"
    )

    if status:

        status = str(
            status
        ).upper()

        log(
            f"Runtime 状态：{status}"
        )

        return status

    config = workspace.get(
        "config",
        {}
    )

    suspended = config.get(
        "suspended"
    )

    if suspended is True:
        return "STOPPED"

    if suspended is False:
        return "RUNNING"

    return "UNKNOWN"


# ============================================================
# 启动 Dev Space
# ============================================================

def start_workspace(
    context,
    jwt,
    workspace
):

    config = workspace.get(
        "config",
        {}
    )

    labels = config.get(
        "labels",
        {}
    )

    workspace_id = config.get(
        "id"
    )

    username = config.get(
        "username"
    )

    display_name = labels.get(
        "ws-manager.devx.sap.com/displayname"
    )

    if not workspace_id:

        log(
            "无法启动：缺少 Workspace ID。"
        )

        return False

    if not username:

        log(
            "无法启动：缺少 Workspace username。"
        )

        return False

    if not display_name:

        display_name = DEVSPACE_NAME

    url = (
        BAS_URL
        + "/ws-manager/api/v1/workspace/"
        + workspace_id
        + "?all=false&username="
        + username
    )

    log(
        "=========================================="
    )

    log(
        "启动 Dev Space..."
    )

    payload = {
        "suspended": False,
        "WorkspaceDisplayName": display_name
    }

    response = context.request.put(
        url,
        headers={
            "X-Approuter-Authorization":
                f"Bearer {jwt}",
            "Content-Type":
                "application/json"
        },
        data=json.dumps(
            payload
        ),
        timeout=60000
    )

    log(
        f"启动 API 状态码：{response.status}"
    )

    if response.status not in [
        200,
        201,
        202
    ]:

        log(
            "Dev Space 启动失败："
        )

        log(
            response.text()[:5000]
        )

        return False

    log(
        "Dev Space 启动请求成功！"
    )

    return True


# ============================================================
# 等待 Dev Space RUNNING
# ============================================================

def wait_until_running(
    context,
    jwt,
    timeout_seconds=360
):

    log(
        "等待 Dev Space 启动..."
    )

    start_time = time.time()

    while (
        time.time() - start_time
        < timeout_seconds
    ):

        workspace = get_workspace(
            context,
            jwt
        )

        if not workspace:

            time.sleep(10)

            continue

        status = get_status(
            workspace
        )

        log(
            f"当前 Dev Space 状态：{status}"
        )

        if status in [
            "RUNNING",
            "STARTED"
        ]:

            log(
                "Dev Space 已经 RUNNING！"
            )

            return workspace

        if status in [
            "ERROR",
            "FAILED"
        ]:

            log(
                "Dev Space 启动进入错误状态。"
            )

            return None

        time.sleep(10)

    log(
        "等待 Dev Space RUNNING 超时。"
    )

    return None


# ============================================================
# 通过 Theia 菜单打开 Terminal
# ============================================================

def click_menu_item_by_text(page, text):

    log(
        f"尝试通过页面菜单寻找：{text}"
    )

    try:

        result = page.evaluate(
            """
            (targetText) => {

                function findAndClick(root) {

                    if (!root) {
                        return false;
                    }

                    const elements =
                        root.querySelectorAll("*");

                    for (const el of elements) {

                        const text =
                            (el.innerText || "")
                            .trim();

                        const aria =
                            (el.getAttribute("aria-label") || "")
                            .trim();

                        const title =
                            (el.getAttribute("title") || "")
                            .trim();

                        if (
                            text === targetText ||
                            aria === targetText ||
                            title === targetText
                        ) {

                            const rect =
                                el.getBoundingClientRect();

                            if (
                                rect.width > 0 &&
                                rect.height > 0
                            ) {

                                el.click();

                                return true;
                            }
                        }

                        if (
                            el.shadowRoot &&
                            findAndClick(el.shadowRoot)
                        ) {

                            return true;
                        }
                    }

                    return false;
                }

                return findAndClick(document);
            }
            """,
            text
        )

        return bool(result)

    except Exception as e:

        log(
            f"寻找菜单 {text} 时发生异常：{e}"
        )

        return False


# ============================================================
# 打开 Terminal
# ============================================================

def open_terminal(page):

    log(
        "=========================================="
    )

    log(
        "开始通过 Theia 菜单打开 Terminal..."
    )

    # --------------------------------------------------------
    # 方法一：点击 Terminal 顶部菜单
    # --------------------------------------------------------

    if not click_menu_item_by_text(
        page,
        "Terminal"
    ):

        log(
            "没有找到 Terminal 菜单。"
        )

        return False

    log(
        "Terminal 菜单已点击。"
    )

    page.wait_for_timeout(
        1500
    )

    # --------------------------------------------------------
    # 点击 New Terminal
    # --------------------------------------------------------

    new_terminal_names = [
        "New Terminal",
        "New Terminal...",
        "New Terminal (Ctrl+Shift+`)"
    ]

    clicked = False

    for name in new_terminal_names:

        if click_menu_item_by_text(
            page,
            name
        ):

            clicked = True

            log(
                f"已点击：{name}"
            )

            break

    if not clicked:

        log(
            "没有找到 New Terminal 菜单项。"
        )

        try:

            page.screenshot(
                path="terminal_menu_failed.png",
                full_page=True
            )

        except Exception:
            pass

        return False

    # --------------------------------------------------------
    # 等待 Terminal 初始化
    # --------------------------------------------------------

    log(
        "等待 Terminal 初始化..."
    )

    for i in range(20):

        page.wait_for_timeout(
            1000
        )

        try:

            terminal = page.locator(
                ".xterm"
            ).first

            if terminal.is_visible(
                timeout=500
            ):

                log(
                    "检测到 xterm Terminal。"
                )

                return True

        except Exception:
            pass

    log(
        "等待 Terminal 超时。"
    )

    return False


# ============================================================
# 向 Terminal 输入命令
# ============================================================

def run_start_script(page):

    log(
        "准备执行 start.sh..."
    )

    try:

        terminal = page.locator(
            ".xterm"
        ).first

        if not terminal.is_visible(
            timeout=5000
        ):

            log(
                "没有找到可见 Terminal。"
            )

            return False

        # ----------------------------------------------------
        # xterm.js 实际输入区域
        # ----------------------------------------------------

        textarea = page.locator(
            ".xterm-helper-textarea"
        ).first

        if not textarea.is_visible(
            timeout=5000
        ):

            log(
                "没有找到 xterm 输入区域。"
            )

            return False

        textarea.click()

        page.wait_for_timeout(
            500
        )

        command = (
            "bash /home/user/my-node/start.sh"
        )

        log(
            f"向 Terminal 输入：{command}"
        )

        textarea.fill(
            command
        )

        textarea.press(
            "Enter"
        )

        log(
            "start.sh 已执行。"
        )

        # ----------------------------------------------------
        # 等待 Xray / Cloudflared 启动
        # ----------------------------------------------------

        page.wait_for_timeout(
            10000
        )

        return True

    except Exception as e:

        log(
            f"执行 start.sh 失败：{e}"
        )

        return False


# ============================================================
# 验证节点进程
# ============================================================

def verify_node(page):

    log(
        "=========================================="
    )

    log(
        "验证节点进程..."
    )

    try:

        textarea = page.locator(
            ".xterm-helper-textarea"
        ).first

        textarea.click()

        page.wait_for_timeout(
            500
        )

        # 使用命令把结果写入终端
        check_command = (
            "echo NODE_CHECK; "
            "pgrep -af xray || true; "
            "pgrep -af cloudflared || true"
        )

        textarea.fill(
            check_command
        )

        textarea.press(
            "Enter"
        )

        page.wait_for_timeout(
            5000
        )

        log(
            "节点进程检查命令已执行。"
        )

        return True

    except Exception as e:

        log(
            f"节点进程检查失败：{e}"
        )

        return False


# ============================================================
# 打开 Workspace 并启动节点
# ============================================================

def open_workspace(
    page,
    workspace
):

    runtime = workspace.get(
        "runtime",
        {}
    )

    workspace_url = (
        runtime
        .get("url", {})
        .get("theia")
    )

    log(
        "打开 Dev Space Workspace..."
    )

    log(
        f"Workspace URL：{workspace_url}"
    )

    try:

        if not workspace_url:

            log(
                "Workspace URL 不存在。"
            )

            return False

        page.goto(
            workspace_url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        log(
            f"Workspace 页面：{page.url}"
        )

        # ----------------------------------------------------
        # 等待 Theia
        # ----------------------------------------------------

        log(
            "等待 IDE 完整加载 20 秒..."
        )

        page.wait_for_timeout(
            20000
        )

        log(
            f"当前 Workspace 页面：{page.url}"
        )

        # ----------------------------------------------------
        # 第一次尝试打开 Terminal
        # ----------------------------------------------------

        for attempt in range(1, 4):

            log(
                "=========================================="
            )

            log(
                f"节点启动尝试 {attempt}/3"
            )

            terminal_ok = open_terminal(
                page
            )

            if not terminal_ok:

                log(
                    "Terminal 打开失败。"
                )

                if attempt < 3:

                    log(
                        "等待 5 秒后重试..."
                    )

                    page.wait_for_timeout(
                        5000
                    )

                continue

            # ------------------------------------------------
            # 执行 start.sh
            # ------------------------------------------------

            start_ok = run_start_script(
                page
            )

            if not start_ok:

                log(
                    "start.sh 执行失败。"
                )

                if attempt < 3:

                    log(
                        "等待 5 秒后重试..."
                    )

                    page.wait_for_timeout(
                        5000
                    )

                continue

            # ------------------------------------------------
            # 验证
            # ------------------------------------------------

            verify_node(
                page
            )

            log(
                "=========================================="
            )

            log(
                "start.sh 已执行。"
            )

            log(
                "节点启动流程完成。"
            )

            return True

        log(
            "=========================================="
        )

        log(
            "3 次尝试均未成功打开 Terminal。"
        )

        try:

            page.screenshot(
                path="terminal_failed.png",
                full_page=True
            )

        except Exception:
            pass

        return False

    except Exception as e:

        log(
            f"打开 Workspace 失败：{e}"
        )

        try:

            page.screenshot(
                path="workspace_error.png",
                full_page=True
            )

        except Exception:
            pass

        return False


# ============================================================
# 主程序
# ============================================================

def main():

    log(
        "=========================================="
    )

    log(
        " SAP BAS Dev Space Keep Alive"
    )

    log(
        "=========================================="
    )

    check_environment()

    log(
        f"BAS URL      : {BAS_URL}"
    )

    log(
        f"Dev Space    : {DEVSPACE_NAME}"
    )

    log(
        f"Dev Space ID : {DEVSPACE_ID}"
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1366,
                "height": 768
            }
        )

        page = context.new_page()

        try:

            # =================================================
            # 登录
            # =================================================

            if not login(page):

                log(
                    "登录失败，任务结束。"
                )

                sys.exit(1)

            # =================================================
            # JWT
            # =================================================

            jwt = get_jwt(
                context
            )

            if not jwt:

                log(
                    "获取 JWT 失败。"
                )

                sys.exit(1)

            log(
                "JWT 获取成功。"
            )

            # =================================================
            # 获取 Workspace
            # =================================================

            workspace = get_workspace(
                context,
                jwt
            )

            if not workspace:

                sys.exit(1)

            status = get_status(
                workspace
            )

            log(
                f"{DEVSPACE_NAME} 当前状态：{status}"
            )

            # =================================================
            # 如果停止 → 启动
            # =================================================

            if status == "STOPPED":

                log(
                    "检测到 Dev Space 已停止。"
                )

                success = start_workspace(
                    context,
                    jwt,
                    workspace
                )

                if not success:

                    sys.exit(1)

                workspace = wait_until_running(
                    context,
                    jwt
                )

                if not workspace:

                    sys.exit(1)

            # =================================================
            # 如果正在启动
            # =================================================

            elif status in [
                "STARTING",
                "CREATING"
            ]:

                log(
                    "Dev Space 正在启动。"
                )

                workspace = wait_until_running(
                    context,
                    jwt
                )

                if not workspace:

                    sys.exit(1)

            # =================================================
            # 已经 RUNNING
            # =================================================

            elif status in [
                "RUNNING",
                "STARTED"
            ]:

                log(
                    "Dev Space 已经处于 RUNNING。"
                )

            else:

                log(
                    f"未知 Dev Space 状态：{status}"
                )

            # =================================================
            # 最终确认
            # =================================================

            workspace = get_workspace(
                context,
                jwt
            )

            if not workspace:

                sys.exit(1)

            final_status = get_status(
                workspace
            )

            log(
                f"最终 Dev Space 状态：{final_status}"
            )

            if final_status not in [
                "RUNNING",
                "STARTED"
            ]:

                log(
                    "Dev Space 最终没有进入 RUNNING。"
                )

                sys.exit(1)

            # =================================================
            # 打开 Workspace + Terminal + start.sh
            # =================================================

            success = open_workspace(
                page,
                workspace
            )

            if not success:

                log(
                    "Workspace 已打开，但节点启动失败。"
                )

                sys.exit(1)

            # =================================================
            # 完成
            # =================================================

            log(
                "=========================================="
            )

            log(
                " Keep Alive 执行成功"
            )

            log(
                f" Dev Space : {DEVSPACE_NAME}"
            )

            log(
                " 状态      : RUNNING"
            )

            log(
                " Terminal   : 已通过 Theia 菜单打开"
            )

            log(
                " start.sh   : 已执行"
            )

            log(
                "=========================================="
            )

        except Exception as e:

            log(
                "程序发生异常："
            )

            log(
                str(e)
            )

            try:

                page.screenshot(
                    path="bas_error.png",
                    full_page=True
                )

            except Exception:
                pass

            sys.exit(1)

        finally:

            context.close()
            browser.close()


if __name__ == "__main__":
    main()
