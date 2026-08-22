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

# ------------------------------------------------------------
# Cloudflare Tunnel Token
# GitHub Secrets 中建议配置：
#
# CF_TUNNEL_TOKEN
# ------------------------------------------------------------

CF_TUNNEL_TOKEN = os.getenv(
    "CF_TUNNEL_TOKEN"
)


# ============================================================
# 日志
# ============================================================

def log(message):

    print(
        f"[BAS] {message}",
        flush=True
    )


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

    if not CF_TUNNEL_TOKEN:
        missing.append("CF_TUNNEL_TOKEN")

    if missing:

        log(
            "缺少 GitHub Secrets："
            + ", ".join(missing)
        )

        sys.exit(1)

    log(
        "环境变量检查通过。"
    )


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

        page.keyboard.press(
            "Enter"
        )

        return True

    except Exception:

        return False


# ============================================================
# SAP 登录
# ============================================================

def login(page):

    log(
        "=========================================="
    )

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

    page.wait_for_timeout(
        5000
    )

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

    else:

        log(
            "当前页面没有发现用户名输入框。"
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

    else:

        log(
            "当前页面没有发现密码输入框。"
        )


    # --------------------------------------------------------
    # 等待登录完成
    # --------------------------------------------------------

    log(
        "等待 SAP 完成登录..."
    )

    for i in range(40):

        page.wait_for_timeout(
            2000
        )

        current_url = page.url

        log(
            f"登录等待 {i + 1}/40：{current_url}"
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

        log(
            "已保存：sap_login_failed.png"
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

    try:

        response = context.request.get(
            BAS_URL + "/jwt",
            timeout=60000
        )

    except Exception as e:

        log(
            f"JWT 请求失败：{e}"
        )

        return None

    log(
        f"JWT HTTP 状态码：{response.status}"
    )

    if response.status != 200:

        try:

            log(
                response.text()[:3000]
            )

        except Exception:
            pass

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

    try:

        response = context.request.get(
            url,
            headers={
                "X-Approuter-Authorization":
                    f"Bearer {jwt}"
            },
            timeout=60000
        )

    except Exception as e:

        log(
            f"Workspace API 请求失败：{e}"
        )

        return None

    log(
        f"Workspace API 状态码：{response.status}"
    )

    if response.status != 200:

        try:

            log(
                response.text()[:5000]
            )

        except Exception:
            pass

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

        # 不输出敏感信息
        log(
            f"Workspace ID : {workspace_id}"
        )

        log(
            f"Display Name : {display_name}"
        )

        log(
            f"Username     : {username}"
        )

        # ----------------------------------------------------
        # 优先使用 ID
        # ----------------------------------------------------

        if str(workspace_id) == str(
            DEVSPACE_ID
        ):

            log(
                "找到目标 Dev Space！"
            )

            return workspace

        # ----------------------------------------------------
        # ID 不匹配时使用名称
        # ----------------------------------------------------

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

        "WorkspaceDisplayName":
            display_name

    }

    try:

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

    except Exception as e:

        log(
            f"启动 API 请求失败：{e}"
        )

        return False

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

        try:

            log(
                response.text()[:5000]
            )

        except Exception:
            pass

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
    timeout_seconds=420
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
# 检查 Theia 是否基本加载
# ============================================================

def wait_for_theia(page):

    log(
        "等待 Theia IDE 加载..."
    )

    # --------------------------------------------------------
    # 不依赖具体菜单文字
    # 只判断页面是否开始出现 Theia 的 DOM
    # --------------------------------------------------------

    selectors = [

        ".theia-app",

        "#theia-app",

        ".lm-Widget",

        ".monaco-workbench",

        ".xterm"

    ]

    for i in range(30):

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.count() > 0:

                    log(
                        f"检测到 Theia 页面元素：{selector}"
                    )

                    page.wait_for_timeout(
                        3000
                    )

                    return True

            except Exception:
                pass

        page.wait_for_timeout(
            1000
        )

        log(
            f"Theia 加载检测 {i + 1}/30..."
        )

    log(
        "Theia IDE 加载检测超时，继续尝试。"
    )

    return False


# ============================================================
# 检测 Terminal
# ============================================================

def terminal_exists(page):

    try:

        terminal = page.locator(
            ".xterm"
        ).first

        if terminal.is_visible(
            timeout=1500
        ):

            log(
                "检测到 xterm Terminal。"
            )

            return True

    except Exception:
        pass

    return False


# ============================================================
# 方法一：键盘快捷键打开 Terminal
# ============================================================

def open_terminal_by_shortcut(page):

    log(
        "尝试使用键盘快捷键打开 Terminal..."
    )

    try:

        # ----------------------------------------------------
        # 点击 IDE 主区域，让页面获得焦点
        # ----------------------------------------------------

        try:

            page.mouse.click(
                700,
                400
            )

        except Exception:
            pass

        page.wait_for_timeout(
            1000
        )

        # ----------------------------------------------------
        # Ctrl + Shift + `
        # ----------------------------------------------------

        page.keyboard.press(
            "Control+Shift+`"
        )

        log(
            "已发送 Ctrl+Shift+`。"
        )

        # ----------------------------------------------------
        # 等待 Terminal
        # ----------------------------------------------------

        for i in range(15):

            page.wait_for_timeout(
                1000
            )

            if terminal_exists(page):

                log(
                    "通过键盘快捷键成功打开 Terminal！"
                )

                return True

            log(
                f"等待 Terminal {i + 1}/15..."
            )

    except Exception as e:

        log(
            f"键盘快捷键打开 Terminal 异常：{e}"
        )

    return False


# ============================================================
# 方法二：Command Palette
# ============================================================

def open_terminal_by_command_palette(page):

    log(
        "尝试通过 Command Palette 打开 Terminal..."
    )

    try:

        try:

            page.mouse.click(
                700,
                400
            )

        except Exception:
            pass

        page.wait_for_timeout(
            500
        )

        # ----------------------------------------------------
        # Ctrl + Shift + P
        # ----------------------------------------------------

        page.keyboard.press(
            "Control+Shift+P"
        )

        page.wait_for_timeout(
            1500
        )

        log(
            "Command Palette 已尝试打开。"
        )

        # ----------------------------------------------------
        # 输入命令
        # ----------------------------------------------------

        page.keyboard.type(
            "Terminal: Create New Terminal",
            delay=20
        )

        page.wait_for_timeout(
            1000
        )

        page.keyboard.press(
            "Enter"
        )

        log(
            "已执行 Terminal: Create New Terminal。"
        )

        # ----------------------------------------------------
        # 等待 Terminal
        # ----------------------------------------------------

        for i in range(15):

            page.wait_for_timeout(
                1000
            )

            if terminal_exists(page):

                log(
                    "通过 Command Palette 成功打开 Terminal！"
                )

                return True

            log(
                f"等待 Terminal {i + 1}/15..."
            )

    except Exception as e:

        log(
            f"Command Palette 打开 Terminal 异常：{e}"
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
        "开始打开 BAS Terminal..."
    )

    # --------------------------------------------------------
    # 方法 0：Terminal 已经存在
    # --------------------------------------------------------

    if terminal_exists(page):

        log(
            "Terminal 已经存在，无需重复打开。"
        )

        return True

    # --------------------------------------------------------
    # 方法 1：键盘快捷键
    # --------------------------------------------------------

    if open_terminal_by_shortcut(page):

        return True

    # --------------------------------------------------------
    # 方法 2：Command Palette
    # --------------------------------------------------------

    if open_terminal_by_command_palette(page):

        return True

    # --------------------------------------------------------
    # 最终失败
    # --------------------------------------------------------

    log(
        "所有 Terminal 打开方法均失败。"
    )

    try:

        page.screenshot(
            path="terminal_open_failed.png",
            full_page=True
        )

        log(
            "已保存截图：terminal_open_failed.png"
        )

    except Exception:
        pass

    return False


# ============================================================
# Terminal 输入
# ============================================================

def terminal_type(page, text):

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

    # --------------------------------------------------------
    # 不使用 fill()
    # xterm.js 使用键盘输入更加可靠
    # --------------------------------------------------------

    page.keyboard.type(
        text,
        delay=5
    )

    return True


# ============================================================
# 注入 Cloudflare Token
# ============================================================

def inject_cloudflare_token(page):

    log(
        "=========================================="
    )

    log(
        "准备向 BAS Terminal 注入 Cloudflare Token..."
    )

    if not CF_TUNNEL_TOKEN:

        log(
            "CF_TUNNEL_TOKEN 不存在。"
        )

        return False

    try:

        # ----------------------------------------------------
        # 使用单引号保护 Token
        # ----------------------------------------------------

        safe_token = (
            CF_TUNNEL_TOKEN
            .replace(
                "'",
                "'\"'\"'"
            )
        )

        command = (
            "export CF_TUNNEL_TOKEN='"
            + safe_token
            + "'"
        )

        if not terminal_type(
            page,
            command
        ):

            return False

        page.keyboard.press(
            "Enter"
        )

        page.wait_for_timeout(
            1000
        )

        log(
            "Cloudflare Token 已注入当前 Terminal 环境。"
        )

        return True

    except Exception as e:

        log(
            f"注入 Cloudflare Token 失败：{e}"
        )

        return False


# ============================================================
# 执行 start.sh
# ============================================================

def run_start_script(page):

    log(
        "=========================================="
    )

    log(
        "准备执行 start.sh..."
    )

    try:

        if not terminal_exists(page):

            log(
                "当前没有 Terminal。"
            )

            return False

        command = (
            "bash /home/user/my-node/start.sh"
        )

        log(
            "执行：bash /home/user/my-node/start.sh"
        )

        if not terminal_type(
            page,
            command
        ):

            return False

        page.keyboard.press(
            "Enter"
        )

        log(
            "start.sh 已发送执行。"
        )

        # ----------------------------------------------------
        # 等待启动
        # ----------------------------------------------------

        page.wait_for_timeout(
            12000
        )

        return True

    except Exception as e:

        log(
            f"执行 start.sh 失败：{e}"
        )

        return False


# ============================================================
# 检查节点进程
# ============================================================

def verify_node(page):

    log(
        "=========================================="
    )

    log(
        "验证 Xray / Cloudflared 进程..."
    )

    try:

        if not terminal_exists(page):

            log(
                "没有 Terminal，无法检查节点。"
            )

            return False

        check_command = (
            "echo NODE_CHECK; "
            "echo '--- XRAY ---'; "
            "pgrep -af '/home/user/my-node/xray' || true; "
            "echo '--- CLOUDFLARED ---'; "
            "pgrep -af '/home/user/my-node/cloudflared' || true"
        )

        if not terminal_type(
            page,
            check_command
        ):

            return False

        page.keyboard.press(
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
# 打开 Workspace
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
        "=========================================="
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

        wait_for_theia(
            page
        )

        # ----------------------------------------------------
        # 给 BAS 额外初始化时间
        # ----------------------------------------------------

        log(
            "额外等待 IDE 完整初始化 15 秒..."
        )

        page.wait_for_timeout(
            15000
        )

        log(
            f"当前 Workspace 页面：{page.url}"
        )

        # ====================================================
        # 节点启动
        # ====================================================

        for attempt in range(
            1,
            4
        ):

            log(
                "=========================================="
            )

            log(
                f"节点启动尝试 {attempt}/3"
            )

            # ------------------------------------------------
            # 打开 Terminal
            # ------------------------------------------------

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
            # 注入 CF Token
            # ------------------------------------------------

            token_ok = inject_cloudflare_token(
                page
            )

            if not token_ok:

                log(
                    "Cloudflare Token 注入失败。"
                )

                if attempt < 3:

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

        # ----------------------------------------------------
        # 3 次失败
        # ----------------------------------------------------

        log(
            "=========================================="
        )

        log(
            "3 次节点启动尝试均未成功。"
        )

        try:

            page.screenshot(
                path="terminal_failed.png",
                full_page=True
            )

            log(
                "已保存截图：terminal_failed.png"
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

            log(
                "已保存截图：workspace_error.png"
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
        " SAP BAS Dev Space Keep Alive V3"
    )

    log(
        "=========================================="
    )

    # ========================================================
    # 环境检查
    # ========================================================

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

    log(
        "CF Tunnel    : 已配置"
    )

    # ========================================================
    # Playwright
    # ========================================================

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(

            viewport={
                "width": 1366,
                "height": 768
            },

            # ------------------------------------------------
            # 保持 BAS Cookie / Session
            # ------------------------------------------------

            ignore_https_errors=False
        )

        page = context.new_page()

        try:

            # =================================================
            # 1. 登录
            # =================================================

            if not login(page):

                log(
                    "登录失败，任务结束。"
                )

                sys.exit(1)

            # =================================================
            # 2. JWT
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
            # 3. 获取 Workspace
            # =================================================

            workspace = get_workspace(
                context,
                jwt
            )

            if not workspace:

                log(
                    "没有找到目标 Dev Space。"
                )

                sys.exit(1)

            # =================================================
            # 4. 获取状态
            # =================================================

            status = get_status(
                workspace
            )

            log(
                f"{DEVSPACE_NAME} 当前状态：{status}"
            )

            # =================================================
            # 5. 如果停止 → 启动
            # =================================================

            if status in [
                "STOPPED",
                "SUSPENDED"
            ]:

                log(
                    "检测到 Dev Space 已停止。"
                )

                success = start_workspace(
                    context,
                    jwt,
                    workspace
                )

                if not success:

                    log(
                        "Dev Space 启动请求失败。"
                    )

                    sys.exit(1)

                workspace = wait_until_running(
                    context,
                    jwt
                )

                if not workspace:

                    sys.exit(1)

            # =================================================
            # 6. 正在启动
            # =================================================

            elif status in [
                "STARTING",
                "CREATING",
                "PROVISIONING"
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
            # 7. 已经 RUNNING
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

                # ------------------------------------------------
                # 再查询一次
                # ------------------------------------------------

                time.sleep(5)

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
                    f"重新查询后的状态：{status}"
                )

                if status not in [
                    "RUNNING",
                    "STARTED"
                ]:

                    log(
                        "Dev Space 当前无法继续。"
                    )

                    sys.exit(1)

            # =================================================
            # 8. 最终确认 Dev Space
            # =================================================

            workspace = get_workspace(
                context,
                jwt
            )

            if not workspace:

                log(
                    "最终查询 Dev Space 失败。"
                )

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
            # 9. 打开 Workspace
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
            # 10. 完成
            # =================================================

            log(
                "=========================================="
            )

            log(
                " Keep Alive V3 执行成功"
            )

            log(
                f" Dev Space : {DEVSPACE_NAME}"
            )

            log(
                " 状态      : RUNNING"
            )

            log(
                " Theia     : 已打开"
            )

            log(
                " Terminal  : 已打开"
            )

            log(
                " start.sh  : 已执行"
            )

            log(
                " Xray      : 已启动检查"
            )

            log(
                " Cloudflared: 已启动检查"
            )

            log(
                "=========================================="
            )

        except Exception as e:

            log(
                "=========================================="
            )

            log(
                "程序发生异常："
            )

            log(
                str(e)
            )

            log(
                "=========================================="
            )

            try:

                page.screenshot(
                    path="bas_error.png",
                    full_page=True
                )

                log(
                    "已保存：bas_error.png"
                )

            except Exception:
                pass

            sys.exit(1)

        finally:

            try:

                context.close()

            except Exception:
                pass

            try:

                browser.close()

            except Exception:
                pass


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    main()
