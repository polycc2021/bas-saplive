import os
import sys
import time
import json
import requests

from playwright.sync_api import sync_playwright


# ============================================================
# 基本配置
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

HEADLESS = True


# ============================================================
# 日志
# ============================================================

def log(text):
    print(f"[BAS] {text}", flush=True)


# ============================================================
# 检查环境变量
# ============================================================

def check_environment():

    if not BAS_USERNAME:
        log("ERROR: BAS_USERNAME 没有设置")
        sys.exit(1)

    if not BAS_PASSWORD:
        log("ERROR: BAS_PASSWORD 没有设置")
        sys.exit(1)

    log(f"BAS URL       : {BAS_URL}")
    log(f"Dev Space     : {DEVSPACE_NAME}")
    log(f"Dev Space ID  : {DEVSPACE_ID}")


# ============================================================
# 登录 BAS
# ============================================================

def login(page):

    log("打开 SAP Business Application Studio...")

    page.goto(
        BAS_URL + "/index.html",
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(5000)

    log(f"当前页面：{page.url}")

    # 如果已经进入 BAS
    if "workspace-manager" in page.url:
        log("已经登录 BAS。")
        return

    # --------------------------------------------------------
    # 尝试用户名密码登录
    # --------------------------------------------------------

    try:

        username_box = page.get_by_label(
            "Email or User Name"
        )

        if username_box.count() > 0:

            log("发现 SAP 登录页面。")

            username_box.fill(
                BAS_USERNAME
            )

            password_box = page.get_by_label(
                "Password"
            )

            password_box.fill(
                BAS_PASSWORD
            )

            log("提交 SAP 登录...")

            continue_button = page.get_by_text(
                "Continue",
                exact=True
            )

            if continue_button.count() > 0:
                continue_button.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(8000)

    except Exception as e:

        log(f"登录页面处理异常：{e}")

    log(f"登录后页面：{page.url}")

    # 给 SAP 登录/跳转一些时间
    page.wait_for_timeout(5000)


# ============================================================
# 获取 JWT
# ============================================================

def get_jwt(context):

    log("获取 SAP BAS JWT...")

    response = context.request.get(
        BAS_URL + "/jwt",
        timeout=60000
    )

    log(
        f"JWT HTTP 状态码：{response.status}"
    )

    if response.status != 200:

        log(
            "无法获取 JWT。"
        )

        log(
            response.text()[:1000]
        )

        return None

    data = response.json()

    # SAP 返回通常是 {"value":"..."}
    if isinstance(data, dict):

        jwt = data.get("value")

        if jwt:
            return jwt

    # 某些情况下可能直接返回字符串
    if isinstance(data, str):
        return data

    log("JWT 返回格式无法识别：")
    log(json.dumps(data, indent=2)[:2000])

    return None


# ============================================================
# 查询 Dev Space
# ============================================================

def get_workspace(context, jwt):

    url = (
        BAS_URL
        + "/ws-manager/api/v1/workspace"
        + "?all=true"
    )

    log("查询 Dev Space 状态...")

    response = context.request.get(
        url,
        headers={
            "X-Approuter-Authorization":
                f"Bearer {jwt}"
        },
        timeout=60000
    )

    log(
        f"Workspace API HTTP 状态码：{response.status}"
    )

    if response.status != 200:

        log(
            response.text()[:2000]
        )

        return None

    data = response.json()

    # --------------------------------------------------------
    # API 返回列表
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

    if not isinstance(workspaces, list):

        log("无法识别 Workspace API 返回结构。")

        log(
            json.dumps(
                data,
                indent=2
            )[:5000]
        )

        return None

    # --------------------------------------------------------
    # 查找 yesdo
    # --------------------------------------------------------

    for workspace in workspaces:

        try:

            labels = workspace.get(
                "labels",
                {}
            )

            config = workspace.get(
                "config",
                {}
            )

            display_name = (
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
                display_name == DEVSPACE_NAME
                or workspace_id == DEVSPACE_ID
            ):

                return workspace

        except Exception:
            continue

    log(
        f"没有找到 Dev Space：{DEVSPACE_NAME}"
    )

    return None


# ============================================================
# 提取状态
# ============================================================

def get_status(workspace):

    if not workspace:
        return "UNKNOWN"

    # 尝试不同字段
    for key in [
        "status",
        "state",
        "phase"
    ]:

        value = workspace.get(key)

        if value:
            return str(value).upper()

    # 有些返回结构可能把状态放在 config
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

    log("准备启动 Dev Space...")
    log(f"Workspace ID：{workspace_id}")

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
        f"启动 API HTTP 状态码：{response.status}"
    )

    if response.status not in [200, 201, 202]:

        log(
            "启动 Dev Space 失败："
        )

        log(
            response.text()[:3000]
        )

        return False

    log("启动请求已经发送。")

    return True


# ============================================================
# 等待 RUNNING
# ============================================================

def wait_until_running(
    context,
    jwt,
    timeout_seconds=300
):

    log("等待 Dev Space 进入 RUNNING...")

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
                "Dev Space 启动失败。"
            )

            return None

        time.sleep(10)

    log(
        "等待 Dev Space 启动超时。"
    )

    return None


# ============================================================
# 打开 Workspace
# ============================================================

def open_workspace(
    page,
    workspace
):

    log("准备访问 Workspace...")

    workspace_id = (
        workspace
        .get("config", {})
        .get("id")
        or DEVSPACE_ID
    )

    # BAS Workspace URL
    workspace_url = (
        BAS_URL
        + "/?workspace="
        + workspace_id
    )

    log(
        f"Workspace URL：{workspace_url}"
    )

    try:

        page.goto(
            workspace_url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(10000)

        log(
            f"Workspace 页面：{page.url}"
        )

        # 再访问一次当前页面
        # 产生实际 HTTP 活动
        page.reload(
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(5000)

        log(
            "Workspace 活动完成。"
        )

        return True

    except Exception as e:

        log(
            f"Workspace 访问异常：{e}"
        )

        return False


# ============================================================
# 主程序
# ============================================================

def main():

    log("==========================================")
    log(" SAP BAS Dev Space Keep Alive")
    log("==========================================")

    check_environment()

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

            # ------------------------------------------------
            # 1. 登录
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # 2. 获取 JWT
            # ------------------------------------------------

            jwt = get_jwt(context)

            if not jwt:

                log(
                    "获取 JWT 失败，任务结束。"
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
            # 4. 检查状态
            # ------------------------------------------------

            status = get_status(
                workspace
            )

            log(
                f"Dev Space {DEVSPACE_NAME} 当前状态：{status}"
            )

            # ------------------------------------------------
            # 5. STOPPED → 启动
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
            # 6. STARTING → 等待
            # ------------------------------------------------

            elif status in [
                "STARTING",
                "CREATING"
            ]:

                log(
                    "Dev Space 正在启动，继续等待..."
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
                    "Dev Space 已经处于 RUNNING。"
                )

            else:

                log(
                    f"检测到未知状态：{status}"
                )

            # ------------------------------------------------
            # 8. 再次确认
            # ------------------------------------------------

            workspace = get_workspace(
                context,
                jwt
            )

            if workspace:

                final_status = get_status(
                    workspace
                )

                log(
                    f"最终状态：{final_status}"
                )

                if final_status in [
                    "RUNNING",
                    "STARTED"
                ]:

                    # ----------------------------------------
                    # 9. 打开 Workspace
                    # ----------------------------------------

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
                        " Dev Space：RUNNING"
                    )

                    log(
                        " Workspace：已访问"
                    )

                    log(
                        "=========================================="
                    )

                else:

                    log(
                        "最终状态不是 RUNNING。"
                    )

                    sys.exit(1)

            else:

                sys.exit(1)

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
