"""
GLaDOS 签到风控挑战（Challenge-Response）协议实现模块

参考 2026-11 官方控制台最新防作弊交互协议:
1. 在提交签到前，客户端需先从 `/api/user/checkin/challenge` 获取一次性 nonce 与 ttl。
2. 客户端需等待至少 2.5 秒（前端人机观察延迟）。
3. 客户端计算 SHA-256(nonce + ".glados-observe-v1") 作为证明 (proof)。
4. 签到 POST 请求需携带 token, nonce 和 proof，否则会被判定为低信誉自动化请求，导致只给 1 积分（保底）。
"""

import hashlib
import math
import time
from typing import Dict, Optional, Tuple, Any
import requests

CHALLENGE_PATH = "/api/user/checkin/challenge"
CHECKIN_CHALLENGE_DELAY = 2.5
OBSERVE_SALT = ".glados-observe-v1"


def obtain_checkin_payload(
    session: requests.Session,
    domain: str,
    headers: dict,
    delay: float = CHECKIN_CHALLENGE_DELAY
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    请求签到 challenge 并生成包含 proof 的签到 payload。

    :param session: requests.Session 实例
    :param domain: 主域名 (例如 glados.cloud)
    :param headers: 请求头 (包含 Cookie、User-Agent 等)
    :param delay: 延迟等待秒数 (默认 2.5 秒)
    :return: (payload 字典, 错误信息描述)。若成功，错误描述为 None；若失败，payload 为 None。
    """
    challenge_url = f"https://{domain}{CHALLENGE_PATH}"
    try:
        resp = session.get(challenge_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return None, f"获取签到 Challenge 请求失败: {e}"

    if not isinstance(data, dict):
        return None, "Challenge 响应格式非合法 JSON 对象"

    code = data.get("code")
    nonce = data.get("nonce")
    ttl = data.get("ttl", 300000)

    # 校验服务端返回的 challenge 规范
    if (
        code != 0
        or not isinstance(nonce, str)
        or not (0 < len(nonce) <= 4096)
        or type(ttl) not in (int, float)
        or (type(ttl) is float and not math.isfinite(ttl))
        or ttl <= delay * 1000
    ):
        msg = data.get("message", "无详细信息")
        return None, f"未获取到有效签到 Challenge (Code: {code}, Msg: {msg})"

    received_at = time.monotonic()

    # 计算 SHA-256 证明
    proof = hashlib.sha256((nonce + OBSERVE_SALT).encode("utf-8")).hexdigest()

    # 人机观察延时等待（官方要求至少 2.5 秒）
    time.sleep(delay)

    # 检查等待后是否已超过 TTL 有效期
    elapsed_ms = (time.monotonic() - received_at) * 1000
    if elapsed_ms >= ttl:
        return None, f"签到 Challenge 已过期 (耗时 {elapsed_ms:.1f}ms >= TTL {ttl}ms)"

    payload = {
        "token": domain,
        "nonce": nonce,
        "proof": proof,
    }
    return payload, None
