import os
import json
import random
import time
import requests
import datetime
from typing import Tuple, Optional

class GLaDOSChecker:
    DOMAIN = "glados.cloud"
    API_BASE = f"https://{DOMAIN}/api/user"
    CHECKIN_URL = f"{API_BASE}/checkin"
    STATUS_URL = f"{API_BASE}/status"

    # 默认 User-Agent（与登录浏览器保持一致）
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self._validate_env()
        self.email = os.environ["GLADOS_EMAIL"]
        self.cookie = os.environ["GLADOS_COOKIE"]
        self.bot_token = os.environ["TG_BOT_TOKEN"]
        self.chat_id = os.environ["TG_CHAT_ID"]

        # 获取自定义 User-Agent，确保与登录平台一致
        env_ua = os.environ.get("GLADOS_USER_AGENT", "").strip()
        self.user_agent = env_ua if env_ua else self.DEFAULT_UA

        self.current_balance = None
        self.checkin_code: Optional[int] = None
        self.session = requests.Session()

    def _validate_env(self):
        required = {"GLADOS_EMAIL", "GLADOS_COOKIE", "TG_BOT_TOKEN", "TG_CHAT_ID"}
        missing = required - set(os.environ)
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    @staticmethod
    def _current_time() -> str:
        return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    def _gen_headers(self, is_post: bool = False) -> dict:
        """
        按照真机抓包严格对齐请求头:
        1. Accept 严格对齐 axios: application/json, text/plain, */*
        2. Origin 严格使用 https://glados.cloud
        3. 不发送 Referer (页面设置了 no-referrer)
        4. User-Agent 保持一致
        """
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": self.cookie,
            "User-Agent": self.user_agent,
            "Origin": f"https://{self.DOMAIN}",
        }
        if is_post:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        return headers

    @staticmethod
    def _serialize_post_body(data: dict) -> bytes:
        """
        按浏览器 axios 行为序列化请求体:
        axios 使用 JSON.stringify，没有逗号/冒号后的空格（如 {"token":"glados.cloud"} 刚好 24 字节），
        避免 Python json.dumps 默认的空格引发自动化指纹差异。
        """
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _parse_response(self, response: requests.Response) -> dict:
        try:
            return response.json()
        except ValueError:
            return {"message": f"Invalid JSON: {response.text[:50]}"}

    @staticmethod
    def _calculate_expiry_date(data: dict) -> Optional[str]:
        system_date = data.get("data", {}).get("system_date")
        left_days = data.get("data", {}).get("leftDays")

        if not system_date or left_days is None:
            return None

        try:
            base_time = datetime.datetime.fromisoformat(system_date.replace("Z", "+00:00"))
            expiry_date = (base_time + datetime.timedelta(days=float(left_days))).date()
            return expiry_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    def check_status(self) -> Tuple[bool, str]:
        try:
            resp = self.session.get(
                self.STATUS_URL,
                headers=self._gen_headers(is_post=False),
                timeout=15
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            expiry_date = self._calculate_expiry_date(data)
            if expiry_date:
                return True, f"{expiry_date} 到期"
            days = float(data.get("data", {}).get("leftDays", 0))
            return True, f"到期未知，剩余 {int(days)} 天"
        except Exception as e:
            return False, f"状态查询失败: {str(e)} ❌"

    @staticmethod
    def _extract_current_balance(data: dict) -> Optional[str]:
        records = data.get("list", [])
        if not isinstance(records, list) or not records:
            return None

        latest_record = max(
            (item for item in records if isinstance(item, dict)),
            key=lambda item: item.get("time", 0),
            default=None
        )
        if not latest_record:
            return None

        balance = latest_record.get("balance")
        if balance is None:
            return None

        balance_str = str(balance)
        if "." in balance_str:
            balance_str = balance_str.rstrip("0").rstrip(".")
        return balance_str

    def perform_checkin(self) -> Tuple[bool, str]:
        try:
            body = self._serialize_post_body({"token": self.DOMAIN})
            resp = self.session.post(
                self.CHECKIN_URL,
                headers=self._gen_headers(is_post=True),
                data=body,
                timeout=15
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            success, result = self._handle_checkin_result(data)
            current_balance = self._extract_current_balance(data)
            self.current_balance = current_balance
            return success, result
        except Exception as e:
            self.checkin_code = -1
            return False, f"网络请求异常: {str(e)} ❌ (Code: -1)"

    def _handle_checkin_result(self, data: dict) -> Tuple[bool, str]:
        code = data.get("code")
        self.checkin_code = code
        msg = data.get("message", "")
        points = data.get("points")

        # 签到成功 (code 0)
        if code == 0 or "Got" in msg:
            pts = str(points) if points is not None else (msg.split("Got ")[1].split(" ")[0] if "Got " in msg else "若干")
            return True, f"获得 {pts} 积分 🎉"

        # 重复签到 (code 1)
        if code == 1 or "Please Try Tomorrow" in msg or "Return tomorrow" in msg:
            return True, "今日已签过，请明天再试 ⏳"

        # 触发反自动化校验 (code 4)
        if code == 4 or "Automated" in msg:
            reason = data.get("reason", "")
            login_device = data.get("loginDevice", "")
            detail_items = []
            if reason:
                detail_items.append(f"原因: {reason}")
            if login_device:
                detail_items.append(f"登录设备: {login_device}")
            detail_str = f" ({', '.join(detail_items)})" if detail_items else ""
            print(f"⚠️ 触发反自动化检测: {msg}{detail_str}")
            return False, f"反作弊拦截(设备平台不符){detail_str} ❌ (Code: 4)"

        # 认证失效 (code -2)
        if code == -2 or "没有权限" in msg or "No permission" in msg:
            return False, f"Cookie已失效或无权限: {msg} ❌ (Code: -2)"

        return False, f"未知响应: {msg} ❓ (Code: {code})"

    def send_notification(self, status: str, checkin_result: str):
        balance_text = self.current_balance if self.current_balance else "未知"

        # 根据响应码展示醒目的总结状态
        if self.checkin_code == 0:
            summary_status = "✅ 签到成功"
        elif self.checkin_code == 1:
            summary_status = "ℹ️ 今日已签到"
        elif self.checkin_code == 4:
            summary_status = "🚨 签到失败: 设备平台不匹配 (Code: 4)"
        elif self.checkin_code == -2:
            summary_status = "🚨 签到失败: Cookie 已失效 (Code: -2)"
        else:
            summary_status = "⚠️ 任务完成 (签到未成功)"

        message = (
            f"🕒 {self._current_time()}\n\n"
            f"🔔 {checkin_result}\n"
            f"📊 当前 {balance_text} 积分\n"
            f"🗓️ {status}\n\n"
            f"{summary_status}"
        )

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️ 通知发送失败: {str(e)}")

    def execute(self):
        print(f"🔍 开始处理账户: {self.email}")
        if os.environ.get("GLADOS_USER_AGENT"):
            print("ℹ️ 使用自定义 GLADOS_USER_AGENT")
        else:
            print("ℹ️ 未设置 GLADOS_USER_AGENT，使用默认 UA (若被检测请设置为当初登录浏览器的 navigator.userAgent)")

        time.sleep(random.uniform(1, 3))

        success, checkin_result = self.perform_checkin()
        _, status_result = self.check_status()

        self.send_notification(status_result, checkin_result)
        print("🏁 流程执行完毕")

if __name__ == "__main__":
    checker = GLaDOSChecker()
    checker.execute()
