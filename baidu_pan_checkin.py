#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘自动签到脚本 (青龙面板版)
===================================
功能：
  1. 支持BDUSS Cookie认证（推荐，稳定可靠）
  2. 支持账号密码登录（自动获取BDUSS，可能触发验证码）
  3. 每日签到获取成长值
  4. 查询用户信息（等级、成长值、到期时间等）
  5. 支持多账号批量签到
  6. 青龙面板通知推送

环境变量：
  BDUSS         - BDUSS Cookie值，多账号用 & 或换行分隔（推荐）
  BAIDU_ACCOUNTS - 账号密码登录，格式: 手机号#密码，多账号用 & 分隔
  STOKEN        - STOKEN Cookie值（可选），多账号用 & 分隔

定时建议：
  0 8 * * *  (每天早上8点执行)
===================================
"""

import os
import sys
import time
import json
import re
import base64
import traceback
from datetime import datetime

try:
    import requests
except ImportError:
    print("缺少 requests 库，请执行: pip install requests")
    sys.exit(1)

# ==================== 常量配置 ====================

APP_ID = "250528"
CLIENT_TYPE = "0"
WEB_FLAG = "1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 百度网盘会员成长体系API
MEMBERSHIP_API = "https://pan.baidu.com/rest/2.0/membership/user"

# 百度通行证登录API
PASSPORT_GETAPI = "https://passport.baidu.com/v2/api/?getapi"
PASSPORT_PUBKEY = "https://passport.baidu.com/v2/getpublickey"
PASSPORT_LOGIN = "https://passport.baidu.com/v2/api/?login"

# ==================== 通知模块 ====================

def load_notify():
    """加载青龙面板通知模块"""
    try:
        from notify import send
        return send
    except ImportError:
        # 青龙面板外运行时的fallback
        def send(title, content):
            print(f"\n{'='*50}")
            print(f"  {title}")
            print(f"{'='*50}")
            print(content)
            print(f"{'='*50}\n")
        return send

notify_send = load_notify()

# ==================== 日志工具 ====================

def log(msg, level="INFO"):
    """带时间戳的日志输出"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def normalize_baidu_json(text):
    """
    将百度的非标准JSON（单引号混用）转换为标准JSON

    百度通行证API返回的数据混用单引号和双引号，
    例如: {"errno":'0',"pubkey":'-----BEGIN...'}
    此函数将单引号字符串转为双引号，使其可被json.loads解析
    """
    result = []
    i = 0
    in_dq = False  # 是否在双引号字符串内
    in_sq = False  # 是否在单引号字符串内
    while i < len(text):
        char = text[i]
        if not in_sq and not in_dq:
            if char == '"':
                in_dq = True
                result.append(char)
            elif char == "'":
                in_sq = True
                result.append('"')
            else:
                result.append(char)
        elif in_dq:
            if char == '\\' and i + 1 < len(text):
                result.append(char)
                result.append(text[i + 1])
                i += 2
                continue
            elif char == '"':
                in_dq = False
            result.append(char)
        elif in_sq:
            if char == '\\' and i + 1 < len(text):
                result.append(char)
                result.append(text[i + 1])
                i += 2
                continue
            elif char == "'":
                in_sq = False
                result.append('"')
            else:
                result.append(char)
        i += 1
    return ''.join(result)


def parse_baidu_response(resp):
    """
    解析百度API响应，兼容标准JSON和非标准JSON（单引号）

    Args:
        resp: requests.Response对象

    Returns:
        dict: 解析后的字典
    """
    text = resp.text
    # 尝试直接解析标准JSON
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        pass
    # 尝试解析JSONP: callback({...})
    jsonp_match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
    if jsonp_match:
        try:
            return json.loads(jsonp_match.group(1))
        except (json.JSONDecodeError, ValueError):
            try:
                return json.loads(normalize_baidu_json(jsonp_match.group(1)))
            except (json.JSONDecodeError, ValueError):
                pass
    # 尝试规范化后解析
    try:
        return json.loads(normalize_baidu_json(text))
    except (json.JSONDecodeError, ValueError):
        pass
    # 全部失败，返回空字典
    return {}

# ==================== 百度网盘签到核心类 ====================

class BaiduPanCheckin:
    """百度网盘签到类"""

    def __init__(self, bduss, stoken="", account_name=""):
        """
        初始化签到实例

        Args:
            bduss: BDUSS Cookie值
            stoken: STOKEN Cookie值（可选）
            account_name: 账号标识（用于日志）
        """
        self.bduss = bduss
        self.stoken = stoken
        self.account_name = account_name or self._mask_bduss(bduss)
        self.session = requests.Session()
        self.bdstoken = ""
        self.uid = ""

        # 构建Cookie
        cookie_str = f"BDUSS={bduss}"
        if stoken:
            cookie_str += f"; STOKEN={stoken}"

        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://pan.baidu.com/",
            "Cookie": cookie_str,
        })

    @staticmethod
    def _mask_bduss(bduss):
        """脱敏BDUSS用于日志显示"""
        if len(bduss) <= 8:
            return "***"
        return f"{bduss[:4]}...{bduss[-4:]}"

    def _build_params(self, method):
        """构建API通用参数"""
        return {
            "method": method,
            "clienttype": CLIENT_TYPE,
            "app_id": APP_ID,
            "web": WEB_FLAG,
        }

    def _request(self, method_name, http_method="GET", extra_params=None, data=None):
        """
        发送API请求

        Args:
            method_name: API方法名 (query_info / sign / task_list)
            http_method: HTTP方法
            extra_params: 额外参数
            data: POST数据

        Returns:
            dict: API响应JSON
        """
        params = self._build_params(method_name)
        if extra_params:
            params.update(extra_params)

        url = MEMBERSHIP_API

        try:
            if http_method.upper() == "GET":
                resp = self.session.get(url, params=params, timeout=15)
            else:
                resp = self.session.post(url, params=params, data=data, timeout=15)

            resp.raise_for_status()
            result = resp.json()
            return result

        except requests.exceptions.Timeout:
            log(f"[{self.account_name}] 请求超时: {method_name}", "ERROR")
            return {"errno": -1, "errmsg": "请求超时"}
        except requests.exceptions.ConnectionError:
            log(f"[{self.account_name}] 网络连接失败: {method_name}", "ERROR")
            return {"errno": -2, "errmsg": "网络连接失败"}
        except requests.exceptions.HTTPError as e:
            log(f"[{self.account_name}] HTTP错误: {e}", "ERROR")
            return {"errno": -3, "errmsg": f"HTTP错误: {e}"}
        except json.JSONDecodeError:
            log(f"[{self.account_name}] 响应解析失败: {method_name}", "ERROR")
            return {"errno": -4, "errmsg": "响应解析失败"}
        except Exception as e:
            log(f"[{self.account_name}] 未知异常: {e}", "ERROR")
            return {"errno": -5, "errmsg": str(e)}

    def check_login(self):
        """
        验证BDUSS是否有效

        Returns:
            bool: 是否有效
        """
        result = self._request("query_info")
        errno = result.get("errno", -1)

        if errno == 0:
            log(f"[{self.account_name}] BDUSS验证成功")
            # 提取bdstoken和uid
            data = result.get("data", {})
            self.bdstoken = data.get("bdstoken", "")
            self.uid = str(data.get("uid", ""))
            return True
        elif errno == -6:
            log(f"[{self.account_name}] BDUSS已失效，请重新获取", "ERROR")
            return False
        else:
            errmsg = result.get("errmsg", "未知错误")
            log(f"[{self.account_name}] BDUSS验证失败: errno={errno}, {errmsg}", "WARN")
            # 尝试继续签到
            return errno not in [-6, -1, -2, -3, -4, -5]

    def get_user_info(self):
        """
        获取用户成长信息

        Returns:
            dict: 用户信息
        """
        result = self._request("query_info")
        errno = result.get("errno", -1)

        if errno != 0:
            log(f"[{self.account_name}] 获取用户信息失败: {result.get('errmsg', '未知错误')}", "WARN")
            return {}

        data = result.get("data", {})

        # 提取关键信息
        info = {
            "uid": data.get("uid", ""),
            "username": data.get("username", ""),
            "level": data.get("level", "未知"),
            "growth": data.get("growth", "未知"),
            "growth_max": data.get("growth_max", "未知"),
            "is_svip": data.get("is_svip", 0),
            "is_vip": data.get("is_vip", 0),
            "vip_expired": data.get("vip_expired", ""),
            "svip_expired": data.get("svip_expired", ""),
            "today_growth": data.get("today_growth", 0),
            "is_sign": data.get("is_sign", 0),
            "bdstoken": data.get("bdstoken", ""),
            "sign_continuous_days": data.get("sign_continuous_days", 0),
        }

        self.bdstoken = info["bdstoken"]
        self.uid = str(info["uid"])

        return info

    def sign_in(self):
        """
        执行每日签到

        Returns:
            dict: 签到结果
        """
        # 先检查是否已签到
        info = self.get_user_info()
        if info and info.get("is_sign"):
            log(f"[{self.account_name}] 今日已签到，无需重复签到")
            return {
                "success": True,
                "already_signed": True,
                "message": "今日已签到",
                "info": info,
            }

        # 执行签到
        extra_params = {}
        if self.bdstoken:
            extra_params["bdstoken"] = self.bdstoken

        result = self._request("sign", http_method="POST", extra_params=extra_params)
        errno = result.get("errno", -1)
        errmsg = result.get("errmsg", "")

        sign_result = {
            "success": errno == 0,
            "already_signed": False,
            "message": "",
            "info": info,
        }

        if errno == 0:
            # 签到成功
            data = result.get("data", {})
            growth = data.get("growth", 0)
            reward = data.get("reward", "")
            sign_result["message"] = f"签到成功！获得 {growth} 成长值" + (f"，{reward}" if reward else "")
            log(f"[{self.account_name}] {sign_result['message']}", "SUCCESS")

            # 获取签到后的最新信息
            new_info = self.get_user_info()
            if new_info:
                sign_result["info"] = new_info

        elif errno == 1 or "已签到" in errmsg or "already" in errmsg.lower():
            sign_result["already_signed"] = True
            sign_result["success"] = True
            sign_result["message"] = "今日已签到，无需重复签到"
            log(f"[{self.account_name}] {sign_result['message']}")

        elif errno == -6:
            sign_result["message"] = "BDUSS已失效，请重新获取"
            log(f"[{self.account_name}] {sign_result['message']}", "ERROR")

        else:
            sign_result["message"] = f"签到失败: errno={errno}, {errmsg}"
            log(f"[{self.account_name}] {sign_result['message']}", "ERROR")

        return sign_result

    def get_task_list(self):
        """
        获取任务列表

        Returns:
            list: 任务列表
        """
        result = self._request("task_list")
        errno = result.get("errno", -1)

        if errno != 0:
            log(f"[{self.account_name}] 获取任务列表失败: {result.get('errmsg', '')}", "WARN")
            return []

        data = result.get("data", {})
        tasks = data.get("tasks", data.get("list", []))
        return tasks

    def format_report(self, sign_result):
        """格式化签到报告"""
        info = sign_result.get("info", {})

        lines = []
        lines.append(f"账号: {self.account_name}")
        lines.append(f"状态: {sign_result['message']}")

        if info:
            lines.append("")
            lines.append("── 用户信息 ──")

            if info.get("username"):
                lines.append(f"  用户名: {info['username']}")

            if info.get("level"):
                lines.append(f"  等级: Lv.{info['level']}")

            if info.get("growth") != "未知":
                growth_max = info.get("growth_max", "未知")
                if growth_max != "未知":
                    lines.append(f"  成长值: {info['growth']}/{growth_max}")
                else:
                    lines.append(f"  成长值: {info['growth']}")

            if info.get("sign_continuous_days"):
                lines.append(f"  连续签到: {info['sign_continuous_days']}天")

            vip_status = "普通用户"
            if info.get("is_svip"):
                vip_status = "超级会员(SVIP)"
                if info.get("svip_expired"):
                    lines.append(f"  SVIP到期: {info['svip_expired']}")
            elif info.get("is_vip"):
                vip_status = "普通会员(VIP)"
                if info.get("vip_expired"):
                    lines.append(f"  VIP到期: {info['vip_expired']}")
            lines.append(f"  会员状态: {vip_status}")

        return "\n".join(lines)

    def run(self):
        """执行完整签到流程"""
        log(f"[{self.account_name}] 开始签到流程...")

        # 验证登录
        if not self.check_login():
            return {
                "success": False,
                "message": "BDUSS验证失败，请检查Cookie是否有效",
                "report": f"账号: {self.account_name}\n状态: BDUSS已失效，请重新获取",
            }

        # 执行签到
        sign_result = self.sign_in()

        # 生成报告
        report = self.format_report(sign_result)

        log(f"[{self.account_name}] 签到流程完成")

        return {
            "success": sign_result["success"],
            "message": sign_result["message"],
            "report": report,
        }


# ==================== 百度账号密码登录 ====================

def login_baidu(username, password):
    """
    通过账号密码登录百度，获取BDUSS

    注意：百度登录有风控机制，服务器IP可能触发设备验证或短信验证。
    如遇验证，请改用BDUSS方式（推荐）。

    Args:
        username: 手机号或用户名
        password: 密码

    Returns:
        tuple: (bduss, stoken, message) 登录成功返回Cookie值，失败返回错误信息
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://pan.baidu.com/",
    })

    # Step 0: 访问百度网盘首页，获取初始Cookie（BAIDUID等）
    try:
        session.get("https://pan.baidu.com/", timeout=15)
        log("访问百度网盘首页，获取初始Cookie")
    except Exception:
        log("访问百度网盘首页失败，继续尝试登录", "WARN")

    ts = str(int(time.time() * 1000))

    # Step 1: 获取登录token
    try:
        resp = session.get(PASSPORT_GETAPI, params={
            "tpl": "pp",
            "apiver": "v3",
            "class": "login",
            "logintype": "dialogLogin",
            "tt": ts,
            "_": ts,
        }, timeout=15)

        data = parse_baidu_response(resp)
        token = data.get("data", {}).get("token", "")

        if not token:
            return None, None, "获取登录token失败"

        log(f"获取token成功: {token[:8]}...")

    except Exception as e:
        return None, None, f"获取token异常: {e}"

    # Step 2: 获取RSA公钥
    try:
        resp = session.get(PASSPORT_PUBKEY, params={
            "tpl": "pp",
            "apiver": "v3",
            "tt": ts,
            "_": ts,
        }, timeout=15)

        data = parse_baidu_response(resp)
        pubkey_pem = data.get("pubkey", "")
        key = data.get("key", "")

        if not pubkey_pem:
            return None, None, "获取RSA公钥失败"

        log("获取RSA公钥成功")

    except Exception as e:
        return None, None, f"获取公钥异常: {e}"

    # Step 3: RSA加密密码
    try:
        encrypted_password = rsa_encrypt_password(password, pubkey_pem)
        if not encrypted_password:
            return None, None, "密码加密失败（缺少rsa库），请使用BDUSS方式"
        log("密码加密成功")
    except Exception as e:
        return None, None, f"密码加密异常: {e}"

    # Step 4: 提交登录
    try:
        ts2 = str(int(time.time() * 1000))
        login_data = {
            "staticpage": "https://pan.baidu.com/",
            "charset": "utf-8",
            "token": token,
            "tpl": "pp",
            "apiver": "v3",
            "tt": ts2,
            "codestring": "",
            "safeflg": "0",
            "u": "https://pan.baidu.com/",
            "isPhone": "false",
            "quickuser": "0",
            "logintype": "dialogLogin",
            "logLoginType": "pc_loginDialog",
            "idc": "",
            "loginmerge": "true",
            "username": username,
            "password": encrypted_password,
            "verifycode": "",
            "mem_pass": "on",
            "ppui_logintime": ts2,
        }

        resp = session.post(PASSPORT_LOGIN, data=login_data, timeout=15)
        text = resp.text

        # 从Cookie中提取BDUSS
        cookies = session.cookies.get_dict()
        bduss = cookies.get("BDUSS", "")
        stoken = cookies.get("STOKEN", "")

        if bduss:
            log(f"登录成功！BDUSS: {bduss[:8]}...")
            return bduss, stoken, "登录成功"

        # BDUSS未获取到，分析错误原因
        # 百度登录失败时返回HTML页面，错误信息在URL参数中
        err_no_match = re.search(r'err_no[=:]\s*(\d+)', text)
        err_no = err_no_match.group(1) if err_no_match else ""

        # 尝试从JSON响应中解析
        if not err_no:
            result = parse_baidu_response(resp)
            err_info = result.get("errInfo", {})
            err_no = err_info.get("no", "-1")

        # 错误码映射
        error_map = {
            "0": "登录成功",
            "400023": "需要验证码，请使用BDUSS方式登录",
            "400034": "需要短信验证码，请使用BDUSS方式登录",
            "50052": "触发设备验证（服务器IP风控），请使用BDUSS方式登录",
            "500001": "需要短信验证，请使用BDUSS方式登录",
            "160002": "账号或密码错误，请检查",
            "120016": "账号异常，请联系百度客服",
            "50031": "需要邮箱验证，请使用BDUSS方式登录",
        }

        err_msg = error_map.get(err_no, f"登录失败: errNo={err_no}")
        if not err_no:
            err_msg = f"登录失败（未知错误），请使用BDUSS方式登录"

        # 检查是否需要验证码
        codestring_match = re.search(r'codeString[=:]\s*([^&\s"\']+)', text)
        if codestring_match and codestring_match.group(1):
            err_msg = f"需要验证码（{codestring_match.group(1)}），请使用BDUSS方式登录"

        log(f"登录失败: {err_msg}", "WARN")
        return None, None, err_msg

    except Exception as e:
        return None, None, f"登录请求异常: {e}"


def rsa_encrypt_password(password, pubkey_pem):
    """
    使用RSA公钥加密密码

    Args:
        password: 明文密码
        pubkey_pem: PEM格式的RSA公钥（可能含转义的\\n）

    Returns:
        str: Base64编码的加密密码，失败返回None
    """
    # 处理转义字符（百度API返回的pubkey中\n是字面量）
    pubkey_pem = pubkey_pem.replace("\\n", "\n")

    # 确保PEM格式正确
    if "BEGIN PUBLIC KEY" not in pubkey_pem:
        pubkey_pem = "-----BEGIN PUBLIC KEY-----\n" + pubkey_pem + "\n-----END PUBLIC KEY-----"

    # 尝试使用rsa库
    try:
        import rsa as rsa_lib
        pubkey = rsa_lib.PublicKey.load_pkcs1_openssl_pem(pubkey_pem.encode())
        encrypted = rsa_lib.encrypt(password.encode("utf-8"), pubkey)
        return base64.b64encode(encrypted).decode()
    except ImportError:
        pass

    # 尝试使用pycryptodome
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        pubkey = RSA.import_key(pubkey_pem)
        cipher = PKCS1_v1_5.new(pubkey)
        encrypted = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode()
    except ImportError:
        pass

    log("RSA加密失败：缺少rsa或pycryptodome库，请执行 pip install rsa", "ERROR")
    return None


# ==================== 主函数 ====================

def parse_accounts():
    """
    从环境变量解析账号信息

    Returns:
        list: 账号列表 [{bduss, stoken, name, type}, ...]
    """
    accounts = []

    # 优先读取BDUSS（推荐方式）
    bduss_str = os.environ.get("BDUSS", "").strip()
    stoken_str = os.environ.get("STOKEN", "").strip()

    if bduss_str:
        bduss_list = re.split(r'[&\n]', bduss_str)
        bduss_list = [b.strip() for b in bduss_list if b.strip()]

        stoken_list = []
        if stoken_str:
            stoken_list = re.split(r'[&\n]', stoken_str)
            stoken_list = [s.strip() for s in stoken_list if s.strip()]

        for i, bduss in enumerate(bduss_list):
            stoken = stoken_list[i] if i < len(stoken_list) else ""
            accounts.append({
                "type": "bduss",
                "bduss": bduss,
                "stoken": stoken,
                "name": f"BDUSS账号{i+1}",
            })

    # 读取账号密码（备选方式）
    accounts_str = os.environ.get("BAIDU_ACCOUNTS", "").strip()
    if accounts_str:
        account_list = re.split(r'[&\n]', accounts_str)
        account_list = [a.strip() for a in account_list if a.strip()]

        for i, account in enumerate(account_list):
            parts = account.split("#")
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].strip()
                accounts.append({
                    "type": "login",
                    "username": username,
                    "password": password,
                    "name": f"账号密码{i+1}",
                })
            else:
                log(f"账号密码格式错误: {account}（格式应为 手机号#密码）", "WARN")

    return accounts


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════╗
║     百度网盘自动签到 (青龙面板版)        ║
║     Baidu Pan Auto Check-in for QL      ║
╚══════════════════════════════════════════╝
    """)

    # 解析账号
    accounts = parse_accounts()

    if not accounts:
        msg = (
            "未检测到账号配置！\n\n"
            "请设置以下环境变量之一：\n"
            "1. BDUSS: BDUSS Cookie值（推荐）\n"
            "2. BAIDU_ACCOUNTS: 手机号#密码\n\n"
            "多账号用 & 分隔\n"
            "获取BDUSS方法：\n"
            "  1. 浏览器登录 pan.baidu.com\n"
            "  2. F12 → Application → Cookies → BDUSS\n"
            "  3. 复制BDUSS的值"
        )
        log(msg, "ERROR")
        notify_send("百度网盘签到", msg)
        return

    log(f"共检测到 {len(accounts)} 个账号")

    reports = []
    success_count = 0
    fail_count = 0

    for account in accounts:
        log(f"\n{'─'*40}")
        log(f"开始处理 {account['name']}")

        try:
            if account["type"] == "bduss":
                # BDUSS方式
                checkin = BaiduPanCheckin(
                    bduss=account["bduss"],
                    stoken=account.get("stoken", ""),
                    account_name=account["name"],
                )
                result = checkin.run()

            elif account["type"] == "login":
                # 账号密码登录方式
                username = account["username"]
                password = account["password"]
                account_label = f"{username[:3]}****{username[-4:]}" if len(username) >= 7 else username

                log(f"[{account_label}] 尝试账号密码登录...")
                bduss, stoken, login_msg = login_baidu(username, password)

                if bduss:
                    log(f"[{account_label}] {login_msg}")
                    checkin = BaiduPanCheckin(
                        bduss=bduss,
                        stoken=stoken,
                        account_name=account_label,
                    )
                    result = checkin.run()
                else:
                    log(f"[{account_label}] {login_msg}", "ERROR")
                    result = {
                        "success": False,
                        "message": login_msg,
                        "report": f"账号: {account_label}\n状态: {login_msg}",
                    }

            else:
                continue

            reports.append(result["report"])
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            err_msg = f"处理异常: {e}"
            log(f"[{account['name']}] {err_msg}", "ERROR")
            log(traceback.format_exc(), "DEBUG")
            reports.append(f"账号: {account['name']}\n状态: {err_msg}")
            fail_count += 1

        # 多账号间隔，避免请求过快
        time.sleep(2)

    # 汇总通知
    log(f"\n{'═'*40}")
    log(f"签到完成: 成功 {success_count} 个, 失败 {fail_count} 个")

    summary = (
        f"签到完成: 成功 {success_count}/{len(accounts)}\n\n"
        + "\n\n──────────\n\n".join(reports)
    )

    notify_send("百度网盘签到通知", summary)


if __name__ == "__main__":
    main()
