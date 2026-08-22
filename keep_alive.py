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

START_SCRIPT = os.getenv(
    "START_SCRIPT",
    "/home/user/my-node/start.sh"
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

    if missing:

        log(
            "缺少 GitHub Secrets："
            + ", ".join(missing)
        )

        sys.exit(1)


# ============================================================
# 查找用户名
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
# 查找密码
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

        click_continue(
            page
        )

        page.wait_for_timeout(
            3000
        )

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

        click_continue(
            page
        )

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

        if str(workspace_id) == str(
            DEVSPACE_ID
        ):

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
# 获取状态
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
# 获取 Workspace URL
# ============================================================

def get_workspace_url(workspace):

    runtime = workspace.get(
        "runtime",
        {}
    )

    return (
        runtime
        .get("url", {})
        .get("theia")
    )


# ============================================================
# 打开 Workspace
# ============================================================

def navigate_workspace(
    page,
    workspace
):

    workspace_url = get_workspace_url(
        workspace
    )

    if not workspace_url:

        log(
            "Workspace URL 不存在。"
        )

        return False

    log(
        f"Workspace URL：{workspace_url}"
    )

    try:

        page.goto(
            workspace_url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        log(
            f"Workspace 页面：{page.url}"
        )

        return True

    except Exception as e:

        log(
            f"打开 Workspace 失败：{e}"
        )

        return False


# ============================================================
# 获取页面文本
# ============================================================

def get_page_text(page):

    try:

        return page.locator(
            "body"
        ).inner_text(
            timeout=3000
        )

    except Exception:

        return ""


# ============================================================
# 尝试启动节点
# ============================================================

def start_node_from_terminal(
    page,
    attempts=3
):

    command = (
        "bash "
        + START_SCRIPT
        + " ; "
        "echo __BAS_NODE_COMMAND_FINISHED__"
    )

    for attempt in range(
        1,
        attempts + 1
    ):

        log(
            "=========================================="
        )

        log(
            f"节点启动尝试 {attempt}/{attempts}"
        )

        try:

            # ------------------------------------------------
            # 尝试把焦点放到 IDE
            # ------------------------------------------------

            page.mouse.click(
                700,
                400
            )

            page.wait_for_timeout(
                1000
            )

            # ------------------------------------------------
            # 打开 Terminal
            # ------------------------------------------------

            log(
                "尝试打开 BAS Terminal..."
            )

            page.keyboard.press(
                "Control+Grave"
            )

            page.wait_for_timeout(
                3000
            )

            # ------------------------------------------------
            # 输入启动命令
            # ------------------------------------------------

            log(
                f"执行：bash {START_SCRIPT}"
            )

            page.keyboard.type(
                command,
                delay=5
            )

            page.keyboard.press(
                "Enter"
            )

            # ------------------------------------------------
            # 等待脚本
            # ------------------------------------------------

            log(
                "等待节点启动..."
            )

            for i in range(12):

                page.wait_for_timeout(
                    2500
                )

                text = get_page_text(
                    page
                )

                if (
                    "__BAS_NODE_START_SUCCESS__"
                    in text
                ):

                    log(
                        "=========================================="
                    )

                    log(
                        "检测到节点启动成功标记！"
                    )

                    return True

                if (
                    "__BAS_NODE_COMMAND_FINISHED__"
                    in text
                ):

                    log(
                        "start.sh 已执行完成，"
                        "但暂未检测到成功标记。"
                    )

                if i in [
                    3,
                    7,
                    11
                ]:

                    log(
                        f"节点启动等待："
                        f"{i + 1}/12"
                    )

            log(
                "本次 Terminal 启动未检测到成功标记。"
            )

        except Exception as e:

            log(
                f"Terminal 启动失败：{e}"
            )

        # ----------------------------------------------------
        # 下一次尝试前等待
        # ----------------------------------------------------

        if attempt < attempts:

            log(
                "等待 5 秒后重试..."
            )

            page.wait_for_timeout(
                5000
            )

    log(
        "=========================================="
    )

    log(
        "无法确认 start.sh 已成功执行。"
    )

    return False


# ============================================================
# 打开 Workspace 并启动节点
# ============================================================

def open_workspace(
    page,
    workspace
):

    log(
        "打开 Dev Space Workspace..."
    )

    if not navigate_workspace(
        page,
        workspace
    ):

        return False

    # --------------------------------------------------------
    # 等待 IDE 完整加载
    # --------------------------------------------------------

    log(
        "等待 IDE 完整加载 20 秒..."
    )

    page.wait_for_timeout(
        20000
    )

    log(
        f"当前 Workspace 页面：{page.url}"
    )

    # --------------------------------------------------------
    # 启动节点
    # --------------------------------------------------------

    success = start_node_from_terminal(
        page,
        attempts=3
    )

    if success:

        log(
            "Workspace 已成功访问，节点启动成功。"
        )

        return True

    log(
        "Workspace 已打开，但无法确认节点启动成功。"
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
            # 查询 Workspace
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
            # 启动 Dev Space
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
            # 最终确认状态
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
            # 打开 Workspace + 启动节点
            # =================================================

            node_success = open_workspace(
                page,
                workspace
            )

            if not node_success:

                log(
                    "Dev Space 虽然 RUNNING，"
                    "但节点没有被确认成功启动。"
                )

                sys.exit(1)

            # =================================================
            # 最终成功
            # =================================================

            log(
                "=========================================="
            )

            log(
                " KEEP ALIVE 执行成功"
            )

            log(
                f" Dev Space : {DEVSPACE_NAME}"
            )

            log(
                " BAS       : RUNNING"
            )

            log(
                " Node      : STARTED"
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
