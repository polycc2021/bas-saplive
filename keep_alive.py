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
    "https://9a18409etrial.us10.cf.trial.applicationstudio.cloud.sap"
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
# 环境检查
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
# 通用安全点击
# ============================================================

def safe_click(locator, description="元素"):

    try:

        if locator.count() == 0:
            return False

        element = locator.first

        if not element.is_visible(timeout=1500):
            return False

        log(f"找到 {description}。")

        try:

            element.click(
                timeout=5000
            )

        except Exception:

            # 如果普通 click 失败，尝试 force
            element.click(
                force=True,
                timeout=5000
            )

        return True

    except Exception as e:

        log(
            f"点击 {description} 失败：{e}"
        )

        return False


# ============================================================
# 找用户名
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
# 找密码
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
# 点击登录按钮
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
    # 等待登录
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

    save_screenshot(
        page,
        "sap_login_failed.png"
    )

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

        "WorkspaceDisplayName":
            display_name

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
# 等待 RUNNING
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
# 保存截图
# ============================================================

def save_screenshot(page, filename):

    try:

        page.screenshot(
            path=filename,
            full_page=True
        )

        log(
            f"已保存截图：{filename}"
        )

    except Exception as e:

        log(
            f"保存截图失败：{e}"
        )


# ============================================================
# 检查 Theia 是否加载完成
# ============================================================

def wait_for_theia(page):

    log(
        "等待 Theia IDE 加载..."
    )

    for i in range(30):

        page.wait_for_timeout(
            1000
        )

        try:

            body = page.locator(
                "body"
            )

            if body.is_visible(
                timeout=1000
            ):

                text = body.inner_text(
                    timeout=1000
                )

                if (
                    "File" in text
                    or
                    "Terminal" in text
                    or
                    "View" in text
                    or
                    "Help" in text
                ):

                    log(
                        f"Theia IDE 页面已加载，等待 {i + 1} 秒。"
                    )

                    return True

        except Exception:
            pass

    log(
        "Theia IDE 加载检测超时，继续尝试。"
    )

    return True


# ============================================================
# 通过 ARIA role 查找菜单
# ============================================================

def click_menu_role(page, name):

    log(
        f"尝试通过 ARIA 菜单寻找：{name}"
    )

    selectors = [

        f'[role="menuitem"][aria-label="{name}"]',

        f'[role="menuitem"][title="{name}"]',

        f'[role="menuitem"]:has-text("{name}")',

        f'[role="button"][aria-label="{name}"]',

        f'[role="button"][title="{name}"]'

    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            )

            if locator.count() == 0:
                continue

            if safe_click(
                locator,
                f"菜单 {name}"
            ):

                return True

        except Exception:
            pass

    return False


# ============================================================
# 打开 Terminal 菜单
# ============================================================

def open_terminal_from_menu(page):

    log(
        "尝试通过 Theia 标准菜单打开 Terminal..."
    )

    # --------------------------------------------------------
    # 方法 1：直接找 Terminal menuitem
    # --------------------------------------------------------

    if click_menu_role(
        page,
        "Terminal"
    ):

        page.wait_for_timeout(
            1000
        )

        return True

    # --------------------------------------------------------
    # 方法 2：找顶部菜单中的 Terminal
    # --------------------------------------------------------

    candidates = [

        page.get_by_text(
            "Terminal",
            exact=True
        ),

        page.locator(
            '[aria-label="Terminal"]'
        ),

        page.locator(
            '[title="Terminal"]'
        ),

        page.locator(
            '[data-command="terminal"]'
        )

    ]

    for locator in candidates:

        try:

            if safe_click(
                locator,
                "Terminal 菜单"
            ):

                page.wait_for_timeout(
                    1000
                )

                return True

        except Exception:
            pass

    return False


# ============================================================
# 点击 New Terminal
# ============================================================

def click_new_terminal(page):

    log(
        "寻找 New Terminal..."
    )

    names = [

        "New Terminal",

        "New Terminal...",

        "New Terminal (Ctrl+Shift+`)",

        "New Terminal (⌃⇧`)",

        "Create New Terminal"

    ]

    for name in names:

        try:

            locator = page.get_by_text(
                name,
                exact=True
            )

            if safe_click(
                locator,
                name
            ):

                return True

        except Exception:
            pass

        try:

            locator = page.locator(
                f'[aria-label="{name}"]'
            )

            if safe_click(
                locator,
                name
            ):

                return True

        except Exception:
            pass

    return False


# ============================================================
# Command Palette
#
# 注意：
# 不使用 F1 / Ctrl+Shift+P 快捷键。
# 直接通过页面菜单寻找 Command Palette。
# ============================================================

def open_command_palette(page):

    log(
        "尝试通过 Theia 菜单打开 Command Palette..."
    )

    # --------------------------------------------------------
    # 先寻找 View
    # --------------------------------------------------------

    view_names = [

        "View",

        "View Menu"

    ]

    view_clicked = False

    for name in view_names:

        try:

            locator = page.get_by_text(
                name,
                exact=True
            )

            if safe_click(
                locator,
                name
            ):

                view_clicked = True

                page.wait_for_timeout(
                    500
                )

                break

        except Exception:
            pass

    if not view_clicked:

        for name in view_names:

            try:

                locator = page.locator(
                    f'[aria-label="{name}"]'
                )

                if safe_click(
                    locator,
                    name
                ):

                    view_clicked = True

                    page.wait_for_timeout(
                        500
                    )

                    break

            except Exception:
                pass

    if not view_clicked:

        log(
            "没有找到 View 菜单。"
        )

        return False

    # --------------------------------------------------------
    # 找 Command Palette
    # --------------------------------------------------------

    command_names = [

        "Command Palette...",

        "Command Palette",

        "View: Command Palette"

    ]

    for name in command_names:

        try:

            locator = page.get_by_text(
                name,
                exact=True
            )

            if safe_click(
                locator,
                name
            ):

                page.wait_for_timeout(
                    1000
                )

                return True

        except Exception:
            pass

        try:

            locator = page.locator(
                f'[aria-label="{name}"]'
            )

            if safe_click(
                locator,
                name
            ):

                page.wait_for_timeout(
                    1000
                )

                return True

        except Exception:
            pass

    log(
        "没有找到 Command Palette。"
    )

    return False


# ============================================================
# 通过 Command Palette 找 Terminal
# ============================================================

def terminal_from_command_palette(page):

    if not open_command_palette(page):

        return False

    log(
        "Command Palette 已打开。"
    )

    # --------------------------------------------------------
    # 查找 Command Palette 输入框
    # --------------------------------------------------------

    selectors = [

        'input[placeholder*="command" i]',

        'input[placeholder*="type" i]',

        '.quick-input-widget input',

        '.quick-input-box input',

        '[role="dialog"] input',

        '[role="combobox"]'

    ]

    input_box = None

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1000
            ):

                input_box = locator

                break

        except Exception:
            pass

    if not input_box:

        log(
            "Command Palette 输入框没有找到。"
        )

        save_screenshot(
            page,
            "command_palette_failed.png"
        )

        return False

    # --------------------------------------------------------
    # 输入 Terminal 搜索
    # --------------------------------------------------------

    try:

        input_box.fill(
            "Terminal"
        )

        page.wait_for_timeout(
            1500
        )

    except Exception as e:

        log(
            f"Command Palette 输入失败：{e}"
        )

        return False

    # --------------------------------------------------------
    # 查找命令
    # --------------------------------------------------------

    command_names = [

        "Terminal: Create New Terminal",

        "Create New Terminal",

        "New Terminal",

        "Terminal: Focus on Terminal View",

        "View: Toggle Integrated Terminal"

    ]

    for name in command_names:

        try:

            locator = page.get_by_text(
                name,
                exact=True
            )

            if safe_click(
                locator,
                f"命令 {name}"
            ):

                page.wait_for_timeout(
                    1500
                )

                return True

        except Exception:
            pass

    # --------------------------------------------------------
    # 如果没有精确匹配，寻找包含 Terminal 的命令
    # --------------------------------------------------------

    try:

        items = page.locator(
            '[role="option"]'
        )

        count = items.count()

        for i in range(
            min(count, 20)
        ):

            item = items.nth(i)

            try:

                if not item.is_visible(
                    timeout=300
                ):
                    continue

                text = item.inner_text(
                    timeout=500
                ).strip()

                if (
                    "Terminal" in text
                    and
                    (
                        "New" in text
                        or
                        "Create" in text
                        or
                        "Toggle" in text
                    )
                ):

                    log(
                        f"找到 Terminal 命令：{text}"
                    )

                    item.click()

                    page.wait_for_timeout(
                        1500
                    )

                    return True

            except Exception:
                pass

    except Exception:
        pass

    log(
        "Command Palette 中没有找到可用 Terminal 命令。"
    )

    save_screenshot(
        page,
        "terminal_command_not_found.png"
    )

    return False


# ============================================================
# 检测 xterm
# ============================================================

def detect_terminal(page, timeout=20):

    log(
        "等待 Terminal 初始化..."
    )

    start = time.time()

    while (
        time.time() - start
        < timeout
    ):

        page.wait_for_timeout(
            1000
        )

        selectors = [

            ".xterm",

            ".xterm-screen",

            ".xterm-viewport",

            ".terminal",

            "[class*='terminal']"

        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=300
                ):

                    log(
                        f"检测到 Terminal：{selector}"
                    )

                    return True

            except Exception:
                pass

    log(
        "Terminal 初始化超时。"
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
    # 方法 1：标准菜单
    # --------------------------------------------------------

    if open_terminal_from_menu(page):

        log(
            "Terminal 菜单已打开。"
        )

        if click_new_terminal(page):

            log(
                "New Terminal 已点击。"
            )

            if detect_terminal(page):

                return True

    # --------------------------------------------------------
    # 方法 2：Command Palette
    # --------------------------------------------------------

    log(
        "标准菜单方式失败。"
    )

    log(
        "切换到 Command Palette..."
    )

    if terminal_from_command_palette(page):

        if detect_terminal(page):

            log(
                "通过 Command Palette 成功打开 Terminal。"
            )

            return True

    # --------------------------------------------------------
    # 最终失败
    # --------------------------------------------------------

    log(
        "所有 Terminal 打开方法均失败。"
    )

    save_screenshot(
        page,
        "terminal_open_failed.png"
    )

    return False


# ============================================================
# 获取 Terminal 输入框
# ============================================================

def get_terminal_input(page):

    selectors = [

        ".xterm-helper-textarea",

        ".xterm textarea",

        ".xterm-helper-textarea textarea"

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
# 执行 start.sh
# ============================================================

def run_start_script(page):

    log(
        "=========================================="
    )

    log(
        "准备执行 start.sh..."
    )

    textarea = get_terminal_input(
        page
    )

    if not textarea:

        log(
            "没有找到 xterm Terminal 输入区域。"
        )

        save_screenshot(
            page,
            "terminal_input_failed.png"
        )

        return False

    try:

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

        # ----------------------------------------------------
        # xterm textarea 不建议使用 fill
        #
        # xterm.js 的 textarea 是隐藏/特殊输入元素，
        # 使用 press sequentially 更接近真实键盘输入。
        # ----------------------------------------------------

        textarea.press_sequentially(
            command,
            delay=2
        )

        textarea.press(
            "Enter"
        )

        log(
            "start.sh 已发送到 Terminal。"
        )

        # ----------------------------------------------------
        # 等待启动
        # ----------------------------------------------------

        log(
            "等待 Xray + Cloudflared 启动..."
        )

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
# 读取 Terminal 当前内容
# ============================================================

def get_terminal_text(page):

    selectors = [

        ".xterm-screen",

        ".xterm"

    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1000
            ):

                text = locator.inner_text(
                    timeout=2000
                )

                if text:

                    return text

        except Exception:
            pass

    return ""


# ============================================================
# 验证节点
# ============================================================

def verify_node(page):

    log(
        "=========================================="
    )

    log(
        "验证节点进程..."
    )

    textarea = get_terminal_input(
        page
    )

    if not textarea:

        log(
            "没有找到 Terminal 输入区域。"
        )

        return False

    try:

        textarea.click()

        page.wait_for_timeout(
            500
        )

        check_command = (

            "echo NODE_CHECK; "

            "echo CF_TOKEN_CHECK; "

            "if [ -n \"$CF_TUNNEL_TOKEN\" ]; "
            "then echo CF_TUNNEL_TOKEN_OK; "
            "else echo CF_TUNNEL_TOKEN_MISSING; "
            "fi; "

            "echo XRAY_CHECK; "

            "pgrep -af '/home/user/my-node/xray' "
            "|| true; "

            "echo CLOUDFLARED_CHECK; "

            "pgrep -af '/home/user/my-node/cloudflared' "
            "|| true"

        )

        textarea.press_sequentially(
            check_command,
            delay=1
        )

        textarea.press(
            "Enter"
        )

        page.wait_for_timeout(
            5000
        )

        text = get_terminal_text(
            page
        )

        # ----------------------------------------------------
        # 输出诊断
        # ----------------------------------------------------

        if text:

            log(
                "Terminal 最近输出："
            )

            lines = text.splitlines()

            for line in lines[-30:]:

                if line.strip():

                    log(
                        "  "
                        + line
                    )

        # ----------------------------------------------------
        # 检查关键结果
        # ----------------------------------------------------

        if "CF_TUNNEL_TOKEN_MISSING" in text:

            log(
                "警告：BAS Dev Space 内没有 CF_TUNNEL_TOKEN。"
            )

            log(
                "start.sh 可能无法启动 Cloudflared。"
            )

        if (
            "NODE_CHECK" in text
            and
            (
                "xray" in text.lower()
                or
                "XRAY_CHECK" in text
            )
        ):

            log(
                "节点进程检查命令已经执行。"
            )

        return True

    except Exception as e:

        log(
            f"节点进程检查失败：{e}"
        )

        return False


# ============================================================
# 检查 start.sh 成功标记
# ============================================================

def check_start_success(page):

    log(
        "检查 start.sh 执行结果..."
    )

    page.wait_for_timeout(
        2000
    )

    text = get_terminal_text(
        page
    )

    if not text:

        log(
            "无法读取 Terminal 输出。"
        )

        return False

    if "__BAS_NODE_START_SUCCESS__" in text:

        log(
            "检测到 __BAS_NODE_START_SUCCESS__"
        )

        log(
            "start.sh 执行成功。"
        )

        return True

    if (
        "[OK] Xray + Cloudflared are running."
        in text
    ):

        log(
            "检测到 Xray + Cloudflared 正常运行。"
        )

        return True

    log(
        "没有检测到 start.sh 成功标记。"
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

        log(
            "额外等待 IDE 完整初始化 10 秒..."
        )

        page.wait_for_timeout(
            10000
        )

        log(
            f"当前 Workspace 页面：{page.url}"
        )

        # ====================================================
        # 最多 3 次完整尝试
        # ====================================================

        for attempt in range(1, 4):

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

                    page.wait_for_timeout(
                        5000
                    )

                continue

            # ------------------------------------------------
            # 等待并检查成功标记
            # ------------------------------------------------

            if check_start_success(page):

                verify_node(
                    page
                )

                log(
                    "=========================================="
                )

                log(
                    "节点启动流程完成。"
                )

                return True

            # ------------------------------------------------
            # 即使没有读取到成功标记，也进行进程检查
            # ------------------------------------------------

            verify_node(
                page
            )

            log(
                "没有读取到明确成功标记。"
            )

            if attempt < 3:

                log(
                    "等待 5 秒后再次检查..."
                )

                page.wait_for_timeout(
                    5000
                )

                continue

        # ====================================================
        # 三次失败
        # ====================================================

        log(
            "=========================================="
        )

        log(
            "3 次节点启动尝试均未确认成功。"
        )

        save_screenshot(
            page,
            "terminal_failed.png"
        )

        return False

    except Exception as e:

        log(
            f"打开 Workspace 失败：{e}"
        )

        save_screenshot(
            page,
            "workspace_error.png"
        )

        return False


# ============================================================
# 主程序
# ============================================================

def main():

    log(
        "=========================================="
    )

    log(
        " SAP BAS Dev Space Keep Alive V2"
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
            },

            # ------------------------------------------------
            # 保持桌面浏览器特征
            # ------------------------------------------------

            java_script_enabled=True

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
            # Workspace
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
            # STOPPED → 启动
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
            # STARTING
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
            # RUNNING
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
            # Workspace + Terminal + start.sh
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
                " Terminal   : 已打开"
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

            save_screenshot(
                page,
                "bas_error.png"
            )

            sys.exit(1)

        finally:

            context.close()

            browser.close()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    main()
