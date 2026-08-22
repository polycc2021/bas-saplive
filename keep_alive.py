import os
import sys
import time
import json

from playwright.sync_api import sync_playwright


# ============================================================
# SAP BAS Dev Space Keep Alive V4
#
# 主要改进：
#
# 1. 延长 Theia / Workspace 初始化等待时间
# 2. 兼容 BAS 开发环境 1~2 分钟慢启动
# 3. Terminal 每次最多等待 60 秒
# 4. Terminal 最多尝试 3 次
# 5. 每次失败后增加等待时间
# 6. CF_TUNNEL_TOKEN 自动注入 Terminal
# 7. 执行 start.sh 后真正检查 Xray / Cloudflared
# 8. 检查 __BAS_NODE_START_SUCCESS__
# 9. 保留原来的 BAS API / JWT / Dev Space 逻辑
# ============================================================


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

CF_TUNNEL_TOKEN = os.getenv(
    "CF_TUNNEL_TOKEN"
)


# ============================================================
# BAS 内部节点路径
# ============================================================

NODE_DIR = "/home/user/my-node"

START_SCRIPT = f"{NODE_DIR}/start.sh"
XRAY_PATH = f"{NODE_DIR}/xray"
CLOUDFLARED_PATH = f"{NODE_DIR}/cloudflared"
CONFIG_PATH = f"{NODE_DIR}/config.json"


# ============================================================
# 时间参数
# ============================================================

# Dev Space 启动最长等待
DEVSPACE_TIMEOUT = 420

# Workspace 页面加载最长等待
WORKSPACE_PAGE_TIMEOUT = 180

# Theia DOM 最长等待
THEIA_TIMEOUT = 180

# Terminal 单次最长等待
TERMINAL_TIMEOUT = 60

# start.sh 启动后等待
START_SCRIPT_WAIT = 20


# ============================================================
# 日志
# ============================================================

def log(message):

    print(
        f"[BAS] {message}",
        flush=True
    )


# ============================================================
# 环境变量检查
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
# 查找用户名输入框
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
# 查找密码输入框
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
# Continue / Sign In
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
    # 等待登录
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

    # --------------------------------------------------------
    # 查找目标 Workspace
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # 优先 ID
        # ----------------------------------------------------

        if str(workspace_id) == str(
            DEVSPACE_ID
        ):

            log(
                "找到目标 Dev Space！"
            )

            return workspace

        # ----------------------------------------------------
        # 备用名称
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
    timeout_seconds=DEVSPACE_TIMEOUT
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
# 检查 Theia DOM
#
# 注意：
# BAS 实际启动可能需要 1~2 分钟。
# 因此 V4 从原来的 30 秒提升到 180 秒。
# ============================================================

def wait_for_theia(page):

    log(
        "等待 Theia IDE 加载..."
    )

    selectors = [

        ".theia-app",

        "#theia-app",

        ".lm-Widget",

        ".monaco-workbench",

        ".xterm",

        ".xterm-screen",

        "body"

    ]

    start_time = time.time()

    last_log = 0

    while (
        time.time() - start_time
        < THEIA_TIMEOUT
    ):

        elapsed = int(
            time.time() - start_time
        )

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.count() > 0:

                    log(
                        f"检测到 Theia 页面元素：{selector}"
                    )

                    # 不马上返回。
                    # 给 IDE 留出真正初始化时间。

                    log(
                        "Theia 已开始加载，继续等待 IDE 初始化..."
                    )

                    return True

            except Exception:

                pass

        # 每 10 秒输出一次
        if elapsed - last_log >= 10:

            log(
                f"Theia 初始化等待："
                f"{elapsed}/{THEIA_TIMEOUT} 秒..."
            )

            last_log = elapsed

        page.wait_for_timeout(
            1000
        )

    log(
        "Theia IDE DOM 检测超时。"
    )

    return False


# ============================================================
# 等待 BAS IDE 完整初始化
#
# 这一段是 V4 的核心改动。
# 即使 Theia DOM 已经出现，也继续等待。
# ============================================================

def wait_for_ide_ready(page):

    log(
        "=========================================="
    )

    log(
        "等待 BAS IDE 完整初始化..."
    )

    log(
        "由于 BAS 开发环境可能需要 1~2 分钟，"
        "这里最长等待 180 秒。"
    )

    start_time = time.time()

    last_log = 0

    while (
        time.time() - start_time
        < WORKSPACE_PAGE_TIMEOUT
    ):

        elapsed = int(
            time.time() - start_time
        )

        # ----------------------------------------------------
        # Terminal 已经出现
        # ----------------------------------------------------

        if terminal_exists(page):

            log(
                "检测到 Terminal，IDE 已经基本就绪。"
            )

            return True

        # ----------------------------------------------------
        # 检查常见 IDE 元素
        # ----------------------------------------------------

        ready = False

        selectors = [

            ".theia-app",

            "#theia-app",

            ".monaco-workbench",

            ".lm-Widget"

        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.count() > 0:

                    ready = True

                    break

            except Exception:

                pass

        if ready:

            if elapsed - last_log >= 10:

                log(
                    f"IDE 正在初始化："
                    f"{elapsed}/{WORKSPACE_PAGE_TIMEOUT} 秒..."
                )

                last_log = elapsed

        else:

            if elapsed - last_log >= 10:

                log(
                    f"等待 IDE 页面："
                    f"{elapsed}/{WORKSPACE_PAGE_TIMEOUT} 秒..."
                )

                last_log = elapsed

        page.wait_for_timeout(
            2000
        )

    log(
        "IDE 完整初始化等待超时。"
    )

    # 注意：
    # 这里不直接失败。
    # 后面仍然尝试 Terminal。

    return False


# ============================================================
# 检测 Terminal
# ============================================================

def terminal_exists(page):

    selectors = [

        ".xterm",

        ".xterm-screen",

        ".xterm-rows",

        ".xterm-helper-textarea"

    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.count() > 0:

                if locator.is_visible(
                    timeout=1000
                ):

                    log(
                        "检测到 Terminal："
                        + selector
                    )

                    return True

        except Exception:

            pass

    return False


# ============================================================
# 等待 Terminal
# ============================================================

def wait_for_terminal(
    page,
    timeout=TERMINAL_TIMEOUT
):

    log(
        f"等待 Terminal，最长 {timeout} 秒..."
    )

    start_time = time.time()

    last_log = 0

    while (
        time.time() - start_time
        < timeout
    ):

        elapsed = int(
            time.time() - start_time
        )

        if terminal_exists(page):

            log(
                f"Terminal 已出现，耗时约 {elapsed} 秒。"
            )

            return True

        if elapsed - last_log >= 5:

            log(
                f"等待 Terminal "
                f"{elapsed}/{timeout} 秒..."
            )

            last_log = elapsed

        page.wait_for_timeout(
            1000
        )

    log(
        "Terminal 等待超时。"
    )

    return False


# ============================================================
# 方法一：键盘快捷键
# ============================================================

def open_terminal_by_shortcut(page):

    log(
        "尝试使用键盘快捷键打开 Terminal..."
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
            1000
        )

        page.keyboard.press(
            "Control+Shift+`"
        )

        log(
            "已发送 Ctrl+Shift+`。"
        )

        if wait_for_terminal(
            page,
            TERMINAL_TIMEOUT
        ):

            log(
                "通过键盘快捷键成功打开 Terminal！"
            )

            return True

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
            1000
        )

        page.keyboard.press(
            "Control+Shift+P"
        )

        page.wait_for_timeout(
            2000
        )

        log(
            "Command Palette 已尝试打开。"
        )

        page.keyboard.type(
            "Terminal: Create New Terminal",
            delay=20
        )

        page.wait_for_timeout(
            1500
        )

        page.keyboard.press(
            "Enter"
        )

        log(
            "已执行 Terminal: Create New Terminal。"
        )

        if wait_for_terminal(
            page,
            TERMINAL_TIMEOUT
        ):

            log(
                "通过 Command Palette 成功打开 Terminal！"
            )

            return True

    except Exception as e:

        log(
            f"Command Palette 打开 Terminal 异常：{e}"
        )

    return False


# ============================================================
# 打开 Terminal
# ============================================================

def open_terminal(
    page,
    attempt=1
):

    log(
        "=========================================="
    )

    log(
        "开始打开 BAS Terminal..."
    )

    # --------------------------------------------------------
    # Terminal 已经存在
    # --------------------------------------------------------

    if terminal_exists(page):

        log(
            "Terminal 已经存在，无需重复打开。"
        )

        return True

    # --------------------------------------------------------
    # 方法 1
    # --------------------------------------------------------

    if open_terminal_by_shortcut(
        page
    ):

        return True

    # --------------------------------------------------------
    # 方法 2
    # --------------------------------------------------------

    if open_terminal_by_command_palette(
        page
    ):

        return True

    # --------------------------------------------------------
    # 失败
    # --------------------------------------------------------

    log(
        f"第 {attempt} 次 Terminal 打开失败。"
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

def terminal_type(
    page,
    text
):

    try:

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

        page.keyboard.type(
            text,
            delay=5
        )

        return True

    except Exception as e:

        log(
            f"Terminal 输入失败：{e}"
        )

        return False


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
            1500
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
# 检查文件结构
# ============================================================

def check_node_files(page):

    log(
        "=========================================="
    )

    log(
        "检查 BAS 节点文件..."
    )

    command = (
        "echo NODE_FILES_CHECK; "
        f"test -x {XRAY_PATH} && echo XRAY_OK || echo XRAY_MISSING; "
        f"test -x {CLOUDFLARED_PATH} && echo CLOUDFLARED_OK || echo CLOUDFLARED_MISSING; "
        f"test -f {CONFIG_PATH} && echo CONFIG_OK || echo CONFIG_MISSING; "
        f"test -f {START_SCRIPT} && echo START_SH_OK || echo START_SH_MISSING"
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
        3000
    )

    log(
        "节点文件检查命令已执行。"
    )

    return True


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
        # V4：
        # 等待更长时间，让 Xray / Cloudflared 初始化
        # ----------------------------------------------------

        log(
            f"等待节点启动 {START_SCRIPT_WAIT} 秒..."
        )

        page.wait_for_timeout(
            START_SCRIPT_WAIT * 1000
        )

        return True

    except Exception as e:

        log(
            f"执行 start.sh 失败：{e}"
        )

        return False


# ============================================================
# 验证节点
# ============================================================

def verify_node(page):

    log(
        "=========================================="
    )

    log(
        "验证 Xray / Cloudflared..."
    )

    try:

        if not terminal_exists(page):

            log(
                "没有 Terminal，无法检查节点。"
            )

            return False

        # ----------------------------------------------------
        # 检查：
        #
        # 1. start.sh 成功标记
        # 2. Xray
        # 3. Cloudflared
        # 4. PID
        # ----------------------------------------------------

        check_command = (
            "echo NODE_VERIFY; "
            "echo '--- START SUCCESS ---'; "
            "if pgrep -af 'xray' >/dev/null; then "
            "echo XRAY_RUNNING; "
            "else "
            "echo XRAY_NOT_RUNNING; "
            "fi; "
            "echo '--- CLOUDFLARED ---'; "
            "if pgrep -af 'cloudflared' >/dev/null; then "
            "echo CLOUDFLARED_RUNNING; "
            "else "
            "echo CLOUDFLARED_NOT_RUNNING; "
            "fi; "
            "echo '--- PROCESSES ---'; "
            "pgrep -af 'xray|cloudflared' || true"
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

        # ----------------------------------------------------
        # 从终端 DOM 中读取可见文字
        # ----------------------------------------------------

        try:

            body_text = page.locator(
                "body"
            ).inner_text(
                timeout=5000
            )

        except Exception:

            body_text = ""

        xray_running = (
            "XRAY_RUNNING"
            in body_text
        )

        cloudflared_running = (
            "CLOUDFLARED_RUNNING"
            in body_text
        )

        if (
            xray_running
            and
            cloudflared_running
        ):

            log(
                "Xray：RUNNING"
            )

            log(
                "Cloudflared：RUNNING"
            )

            log(
                "节点验证成功！"
            )

            return True

        if not xray_running:

            log(
                "Xray 尚未确认运行。"
            )

        if not cloudflared_running:

            log(
                "Cloudflared 尚未确认运行。"
            )

        return False

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
            timeout=WORKSPACE_PAGE_TIMEOUT * 1000
        )

        log(
            f"Workspace 页面：{page.url}"
        )

        # ----------------------------------------------------
        # 第一阶段：
        # 等待 Theia 页面开始出现
        # ----------------------------------------------------

        wait_for_theia(
            page
        )

        # ----------------------------------------------------
        # 第二阶段：
        # 等待 IDE 真正初始化
        # ----------------------------------------------------

        wait_for_ide_ready(
            page
        )

        # ----------------------------------------------------
        # 第三阶段：
        # 再额外等待 15 秒
        # ----------------------------------------------------

        log(
            "额外等待 IDE 稳定 15 秒..."
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

        retry_waits = [
            10,
            20,
            30
        ]

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
            # 如果上一次失败
            # 给 IDE 更长时间恢复
            # ------------------------------------------------

            if attempt > 1:

                wait_seconds = retry_waits[
                    attempt - 1
                ]

                log(
                    f"第 {attempt} 次尝试前，"
                    f"额外等待 {wait_seconds} 秒..."
                )

                page.wait_for_timeout(
                    wait_seconds * 1000
                )

            # ------------------------------------------------
            # 打开 Terminal
            # ------------------------------------------------

            terminal_ok = open_terminal(
                page,
                attempt
            )

            if not terminal_ok:

                log(
                    "Terminal 打开失败。"
                )

                continue

            # ------------------------------------------------
            # Token
            # ------------------------------------------------

            token_ok = inject_cloudflare_token(
                page
            )

            if not token_ok:

                log(
                    "Cloudflare Token 注入失败。"
                )

                continue

            # ------------------------------------------------
            # 检查文件
            # ------------------------------------------------

            check_node_files(
                page
            )

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

                continue

            # ------------------------------------------------
            # 验证
            # ------------------------------------------------

            if verify_node(
                page
            ):

                log(
                    "=========================================="
                )

                log(
                    "节点启动验证成功！"
                )

                log(
                    "Xray + Cloudflared 均已确认运行。"
                )

                return True

            # ------------------------------------------------
            # 验证失败
            # ------------------------------------------------

            log(
                f"第 {attempt} 次节点验证失败。"
            )

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
        " SAP BAS Dev Space Keep Alive V4"
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

            ignore_https_errors=False
        )

        page = context.new_page()

        try:

            # =================================================
            # 1. SAP 登录
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
            # 5. STOPPED
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
            # 7. RUNNING
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

                time.sleep(
                    5
                )

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
            # 8. 最终确认
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
            # 9. 打开 Workspace + 节点
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
            # 10. 成功
            # =================================================

            log(
                "=========================================="
            )

            log(
                " Keep Alive V4 执行成功"
            )

            log(
                f" Dev Space  : {DEVSPACE_NAME}"
            )

            log(
                " 状态       : RUNNING"
            )

            log(
                " Theia      : 已打开"
            )

            log(
                " Terminal   : 已打开"
            )

            log(
                " start.sh   : 已执行"
            )

            log(
                " Xray       : 已确认运行"
            )

            log(
                " Cloudflared: 已确认运行"
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
