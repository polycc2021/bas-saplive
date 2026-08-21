import os
import sys
import time
import json

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# 配置
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
# 环境检查
# ============================================================

def check_environment():

    missing = []

    if not BAS_USERNAME:
        missing.append("BAS_USERNAME")

    if not BAS_PASSWORD:
        missing.append("BAS_PASSWORD")

    if not BAS_URL:
        missing.append("BAS_URL")

    if missing:
        log(
            "缺少 GitHub Secrets："
            + ", ".join(missing)
        )
        sys.exit(1)

    log(f"BAS URL      : {BAS_URL}")
    log(f"Dev Space    : {DEVSPACE_NAME}")
    log(f"Dev Space ID : {DEVSPACE_ID}")


# ============================================================
# 判断当前是否为 SAP 登录页面
# ============================================================

def is_sap_login_page(page):

    url = page.url.lower()

    if "accounts.sap.com" in url:
        return True

    if "login" in url and "sap" in url:
        return True

    try:

        if page.locator(
            'input[type="email"]'
        ).count() > 0:
            return True

        if page.locator(
            'input[name="email"]'
        ).count() > 0:
            return True

        if page.locator(
            'input[type="password"]'
        ).count() > 0:
            return True

    except Exception:
        pass

    return False


# ============================================================
# 找用户名输入框
# ============================================================

def find_username_input(page):

    selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="username"]',
        'input[name="user"]',
        'input[autocomplete="username"]',
        'input[placeholder*="Email"]',
        'input[placeholder*="email"]',
        'input[placeholder*="User"]',
        'input[placeholder*="user"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1500
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
        'input[autocomplete="current-password"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            ).first

            if locator.is_visible(
                timeout=1500
            ):

                return locator

        except Exception:
            pass

    return None


# ============================================================
# 点击 Continue
# ============================================================

def click_continue(page):

    selectors = [
        'button:has-text("Continue")',
        'input[type="submit"]',
        'button[type="submit"]',
        'button:has-text("Log On")',
        'button:has-text("Sign In")',
        'button:has-text("Sign in")',
    ]

    for selector in selectors:

        try:

            button = page.locator(
                selector
            ).first

            if button.is_visible(
                timeout=1500
            ):

                log(
                    "点击登录页面 Continue/Sign In..."
                )

                button.click()

                return True

        except Exception:
            pass

    # 最后尝试 Enter
    try:

        page.keyboard.press("Enter")

        return True

    except Exception:
        return False


# ============================================================
# SAP 登录
# ============================================================

def login(page):

    log("打开 SAP Business Application Studio...")

    page.goto(
        BAS_URL + "/index.html",
        wait_until="domcontentloaded",
        timeout=120000
    )

    log(
        f"初始页面：{page.url}"
    )

    # --------------------------------------------------------
    # 等待 SAP 重定向
    # --------------------------------------------------------

    page.wait_for_timeout(5000)

    log(
        f"当前页面：{page.url}"
    )

    # --------------------------------------------------------
    # 如果没有进入 SAP 登录页
    # --------------------------------------------------------

    if not is_sap_login_page(page):

        log(
            "当前页面看起来不是 SAP 登录页面。"
        )

    # --------------------------------------------------------
    # 第一阶段：用户名
    # --------------------------------------------------------

    username_input = find_username_input(
        page
    )

    if username_input:

        log(
            "发现 SAP 用户名输入框。"
        )

        try:

            username_input.fill(
                BAS_USERNAME
            )

        except Exception as e:

            log(
                f"填写用户名失败：{e}"
            )

            sys.exit(1)

        log(
            "用户名已经填写。"
        )

        click_continue(page)

        # 等待进入密码页面
        page.wait_for_timeout(4000)

    else:

        log(
            "当前没有找到用户名输入框。"
        )

    # --------------------------------------------------------
    # 第二阶段：密码
    # --------------------------------------------------------

    password_input = find_password_input(
        page
    )

    if password_input:

        log(
            "发现 SAP 密码输入框。"
        )

        try:

            password_input.fill(
                BAS_PASSWORD
            )

        except Exception as e:

            log(
                f"填写密码失败：{e}"
            )

            sys.exit(1)

        log(
            "密码已经填写。"
        )

        click_continue(page)

    else:

        # 有可能 SAP 登录页面同时显示用户名和密码
        log(
            "没有找到密码输入框。"
        )

    # --------------------------------------------------------
    # 等待 SAP 完成登录
    # --------------------------------------------------------

    log(
        "等待 SAP 完成登录..."
    )

    for i in range(30):

        page.wait_for_timeout(2000)

        current_url = page.url

        log(
            f"登录等待 {i + 1}/30：{current_url}"
        )

        # 回到了 BAS
        if (
            "applicationstudio.cloud.sap"
            in current_url
            and "accounts.sap.com"
            not in current_url
        ):

            log(
                "SAP 登录成功。"
            )

            return True

        # 登录过程中可能出现 MFA
        if (
            "accounts.sap.com"
            in current_url
        ):

            password = find_password_input(
                page
            )

            if password:

                try:

                    if password.input_value() == "":
                        password.fill(
                            BAS_PASSWORD
                        )

                        click_continue(
                            page
                        )

                except Exception:
                    pass

    # --------------------------------------------------------
    # 登录失败
    # --------------------------------------------------------

    log(
        "=========================================="
    )

    log(
        "SAP 登录没有完成！"
    )

    log(
        f"最终页面：{page.url}"
    )

    log(
        "请检查 GitHub Actions 的截图。"
    )

    try:

        page.screenshot(
            path="sap_login_failed.png",
            full_page=True
        )

        log(
            "已保存 sap_login_failed.png"
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
            "JWT 获取失败。"
        )

        try:

            log(
                response.text()[:3000]
            )

        except Exception:
            pass

        return None

    # SAP BAS /jwt 通常直接返回 JSON
    try:

        data = response.json()

    except Exception:

        text = response.text().strip()

        if text:

            return text

        return None

    if isinstance(data, dict):

        jwt = data.get("value")

        if jwt:
            return jwt

        jwt = data.get("token")

        if jwt:
            return jwt

    if isinstance(data, str):

        return data

    log(
        "JWT 返回格式无法识别："
    )

    log(
        json.dumps(
            data,
            indent=2
        )[:3000]
    )

    return None


# ============================================================
# 查询 Workspace
# ============================================================

def get_workspace(context, jwt):

    url = (
        BAS_URL
        + "/ws-manager/api/v1/workspace"
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
            response.text()[:3000]
        )

        return None

    try:

        data = response.json()

    except Exception:

        log(
            "Workspace API 返回不是 JSON。"
        )

        return None

    # --------------------------------------------------------
    # 处理不同 API 返回格式
    # --------------------------------------------------------

    workspaces = data

    if isinstance(data, dict):

        for key in [
            "workspaces",
            "workspace",
            "items",
            "data"
        ]:

            if key in data:

                workspaces = data[key]

                break

    if not isinstance(
        workspaces,
        list
    ):

        log(
            "无法识别 Workspace 返回结构："
        )

        log(
            json.dumps(
                data,
                indent=2
            )[:5000]
        )

        return None

    # --------------------------------------------------------
    # 找 yesdo
    # --------------------------------------------------------

    for workspace in workspaces:

        labels = workspace.get(
            "labels",
            {}
        )

        config = workspace.get(
            "config",
            {}
        )

        name = (
            labels.get("displayname")
            or labels.get("displayName")
            or workspace.get("displayname")
            or workspace.get("name")
        )

        workspace_id = (
            config.get("id")
            or workspace.get("id")
        )

        if (
            name == DEVSPACE_NAME
            or workspace_id == DEVSPACE_ID
        ):

            log(
                f"找到 Dev Space：{name}"
            )

            return workspace

    log(
        f"没有找到 Dev Space：{DEVSPACE_NAME}"
    )

    return None


# ============================================================
# 获取状态
# ============================================================

def get_status(workspace):

    if not workspace:
        return "UNKNOWN"

    for key in [
        "status",
        "state",
        "phase"
    ]:

        value = workspace.get(key)

        if value:
            return str(value).upper()

    config = workspace.get(
        "config",
        {}
    )

    for key in [
        "status",
        "state",
        "phase"
    ]:

        value = config.get(key)

        if value:
            return str(value).upper()

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

    labels = workspace.get(
        "labels",
        {}
    )

    workspace_id = (
        config.get("id")
        or workspace.get("id")
        or DEVSPACE_ID
    )

    display_name = (
        labels.get("displayname")
        or labels.get("displayName")
        or DEVSPACE_NAME
    )

    url = (
        BAS_URL
        + "/ws-manager/api/v1/workspace/"
        + workspace_id
        + "?all=false"
    )

    log(
        "发送 Dev Space 启动请求..."
    )

    log(
        f"Workspace ID：{workspace_id}"
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
        data=json.dumps(payload),
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
            "启动失败："
        )

        log(
            response.text()[:3000]
        )

        return False

    log(
        "启动请求已发送。"
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
            f"当前状态：{status}"
        )

        if status in [
            "RUNNING",
            "STARTED"
        ]:

            log(
                "Dev Space 已进入 RUNNING！"
            )

            return workspace

        if status in [
            "ERROR",
            "FAILED"
        ]:

            log(
                "Dev Space 启动失败。"
            )

            return None

        time.sleep(10)

    log(
        "等待 Dev Space 启动超时。"
    )

    return None


# ============================================================
# 访问 Workspace
# ============================================================

def open_workspace(
    page,
    workspace
):

    workspace_id = (
        workspace
        .get("config", {})
        .get("id")
        or DEVSPACE_ID
    )

    workspace_url = (
        BAS_URL
        + "/?workspace="
        + workspace_id
    )

    log(
        f"访问 Workspace：{workspace_url}"
    )

    try:

        page.goto(
            workspace_url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(
            10000
        )

        log(
            f"Workspace 当前页面：{page.url}"
        )

        # 再刷新一次
        page.reload(
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(
            5000
        )

        log(
            "Workspace 活动完成。"
        )

        return True

    except Exception as e:

        log(
            f"访问 Workspace 失败：{e}"
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

            # ------------------------------------------------
            # 1. 登录
            # ------------------------------------------------

            login_ok = login(
                page
            )

            if not login_ok:

                log(
                    "登录失败，停止后续操作。"
                )

                sys.exit(1)

            # ------------------------------------------------
            # 2. JWT
            # ------------------------------------------------

            jwt = get_jwt(
                context
            )

            if not jwt:

                log(
                    "JWT 获取失败。"
                )

                sys.exit(1)

            log(
                "JWT 获取成功。"
            )

            # ------------------------------------------------
            # 3. 查询 Dev Space
            # ------------------------------------------------

            workspace = get_workspace(
                context,
                jwt
            )

            if not workspace:

                sys.exit(1)

            # ------------------------------------------------
            # 4. 获取状态
            # ------------------------------------------------

            status = get_status(
                workspace
            )

            log(
                f"{DEVSPACE_NAME} 当前状态：{status}"
            )

            # ------------------------------------------------
            # 5. STOPPED
            # ------------------------------------------------

            if status in [
                "STOPPED",
                "SUSPENDED"
            ]:

                log(
                    "检测到 Dev Space 已停止。"
                )

                if not start_workspace(
                    context,
                    jwt,
                    workspace
                ):

                    sys.exit(1)

                workspace = wait_until_running(
                    context,
                    jwt
                )

                if not workspace:

                    sys.exit(1)

            # ------------------------------------------------
            # 6. STARTING
            # ------------------------------------------------

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

            # ------------------------------------------------
            # 7. RUNNING
            # ------------------------------------------------

            elif status in [
                "RUNNING",
                "STARTED"
            ]:

                log(
                    "Dev Space 已经 RUNNING。"
                )

            else:

                log(
                    f"未知状态：{status}"
                )

            # ------------------------------------------------
            # 8. 最终确认
            # ------------------------------------------------

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
                f"最终状态：{final_status}"
            )

            if final_status not in [
                "RUNNING",
                "STARTED"
            ]:

                log(
                    "Dev Space 最终没有处于 RUNNING。"
                )

                sys.exit(1)

            # ------------------------------------------------
            # 9. 访问 Workspace
            # ------------------------------------------------

            open_workspace(
                page,
                workspace
            )

            log(
                "=========================================="
            )

            log(
                " Keep Alive 执行成功"
            )

            log(
                f" Dev Space：{DEVSPACE_NAME}"
            )

            log(
                " 状态：RUNNING"
            )

            log(
                " Workspace：已访问"
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
