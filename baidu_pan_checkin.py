#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘自动化脚本 (青龙面板版) v4.0
===================================
功能：
  1. BDUSS验证 - 自动检测Cookie有效性
  2. STOKEN自动获取 - 通过BDUSS调用PCS API
  3. 签到尝试 - 每日尝试签到API（百度废弃后返回空响应）
  4. 会员信息查询 - 等级、成长值、会员状态
  5. 成长值历史 - 查看近期成长值变化记录
  6. 金币系统 - 查询金币余额和记录
  7. 网盘容量 - 查询总容量和已使用空间
  8. 多账号支持 - 批量处理多个账号
  9. 通知推送 - 青龙面板通知

环境变量：
  BDUSS         - BDUSS Cookie值，多账号用 & 或换行分隔（推荐）
  STOKEN        - STOKEN Cookie值（可选，不填则自动获取）
  BAIDU_ACCOUNTS - 账号密码登录，格式: 手机号#密码，多账号用 & 分隔

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
APP_ID_PCS = "266719"  # PCS API使用的app_id
CLIENT_TYPE = "0"
WEB_FLAG = "1"

USER_AGENT_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
USER_AGENT_APP = "netdisk;8.5.0.5;Android;13;Redmi K40;androidapp"

# 百度网盘API端点
MEMBERSHIP_USER_API = "https://pan.baidu.com/rest/2.0/membership/user"
MEMBERSHIP_LEVEL_API = "https://pan.baidu.com/rest/2.0/membership/level"
MEMBERSHIP_COIN_API = "https://pan.baidu.com/rest/2.0/membership/coin"
XNAS_API = "https://pan.baidu.com/rest/2.0/xpan/nas"
LOGIN_STATUS_API = "https://pan.baidu.com/api/loginStatus"
PCS_PLANTCOOKIE_API = "https://pcs.baidu.com/rest/2.0/pcs/file"
PCS_QUOTA_API = "https://pcs.baidu.com/rest/2.0/pcs/quota"

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
    """将百度的非标准JSON（单引号混用）转换为标准JSON"""
    result = []
    i = 0
    in_dq = False
    in_sq = False
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
    """解析百度API响应，兼容标准JSON和非标准JSON"""
    text = resp.text
    if not text or not text.strip():
        return {}
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError):
        pass
    jsonp_match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
    if jsonp_match:
        try:
            return json.loads(jsonp_match.group(1))
        except (json.JSONDecodeError, ValueError):
            try:
                return json.loads(normalize_baidu_json(jsonp_match.group(1)))
            except (json.JSONDecodeError, ValueError):
                pass
    try:
        return json.loads(normalize_baidu_json(text))
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


# ==================== 百度网盘自动化核心类 ====================

class BaiduPanAutomation:
    """百度网盘自动化类 - 模拟APP日常任务"""

    def __init__(self, bduss, stoken="", account_name=""):
        self.bduss = bduss
        self.stoken = stoken
        self.account_name = account_name or self._mask_bduss(bduss)
        self.session = requests.Session()
        self.bdstoken = ""
        self.username = ""
        self.uk = ""
        self.baidu_name = ""
        self.vip_type = 0
        self.vip_level = 0
        self.current_level = 0
        self.current_growth = 0
        self.history_level = 0
        self.history_growth = 0
        self.quota_total = 0
        self.quota_used = 0
        self.tasks_done = []
        self.tasks_failed = []

        self._update_cookie()

    def _update_cookie(self):
        """更新Cookie头"""
        cookie_str = f"BDUSS={self.bduss}"
        if self.stoken:
            cookie_str += f"; STOKEN={self.stoken}"
        self.session.headers.update({
            "User-Agent": USER_AGENT_WEB,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://pan.baidu.com/",
            "Cookie": cookie_str,
            "Accept-Encoding": "identity",
        })

    @staticmethod
    def _mask_bduss(bduss):
        if len(bduss) <= 8:
            return "***"
        return f"{bduss[:4]}...{bduss[-4:]}"

    def _set_app_ua(self):
        """切换为APP User-Agent"""
        self.session.headers["User-Agent"] = USER_AGENT_APP

    def _set_web_ua(self):
        """切换为Web User-Agent"""
        self.session.headers["User-Agent"] = USER_AGENT_WEB

    def _get_stoken(self):
        """通过BDUSS自动获取STOKEN（使用PCS API）"""
        if self.stoken:
            return True
        try:
            log(f"[{self.account_name}] 自动获取STOKEN...")
            resp = self.session.get(
                PCS_PLANTCOOKIE_API,
                params={"method": "plantcookie", "type": "stoken", "source": "pcs"},
                timeout=15,
            )
            stoken = self.session.cookies.get("STOKEN", "")
            if stoken:
                self.stoken = stoken
                self._update_cookie()
                log(f"[{self.account_name}] STOKEN获取成功: {stoken[:12]}...")
                return True
            else:
                log(f"[{self.account_name}] STOKEN获取失败（不影响基础功能）", "WARN")
                return False
        except Exception as e:
            log(f"[{self.account_name}] STOKEN获取异常: {e}", "WARN")
            return False

    def check_login(self):
        """验证BDUSS是否有效"""
        try:
            resp = self.session.get(
                XNAS_API,
                params={"method": "uinfo"},
                timeout=15,
            )
            data = resp.json()
            if data.get("errno", -1) == 0 or "netdisk_name" in data:
                self.username = data.get("netdisk_name", "未知")
                self.baidu_name = data.get("baidu_name", "")
                self.uk = str(data.get("uk", ""))
                self.vip_type = data.get("vip_type", 0)
                log(f"[{self.account_name}] BDUSS验证成功，用户: {self.username} (UK: {self.uk})")
                self._get_stoken()
                self._get_bdstoken()
                return True
            else:
                errno = data.get("errno", -1)
                if errno == -6:
                    log(f"[{self.account_name}] BDUSS已失效，请重新获取", "ERROR")
                else:
                    log(f"[{self.account_name}] BDUSS验证失败: errno={errno}", "WARN")
                return False
        except Exception as e:
            log(f"[{self.account_name}] 验证异常: {e}", "ERROR")
            return False

    def _get_bdstoken(self):
        """获取bdstoken"""
        try:
            resp = self.session.get(
                LOGIN_STATUS_API,
                params={"clienttype": "0", "app_id": APP_ID},
                timeout=15,
            )
            data = resp.json()
            self.bdstoken = data.get("login_info", {}).get("bdstoken", "")
            login_info = data.get("login_info", {})
            if login_info.get("username"):
                self.username = login_info["username"]
            if login_info.get("vip_level"):
                self.vip_level = login_info["vip_level"]
        except Exception:
            pass

    # ==================== 任务1: 签到 ====================

    def task_sign(self):
        """任务1: 尝试签到"""
        log(f"[{self.account_name}] [任务1] 尝试签到...")
        self._set_app_ua()
        try:
            self.session.headers.update({
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://pan.baidu.com",
                "Referer": "https://pan.baidu.com/disk/home",
                "X-Requested-With": "XMLHttpRequest",
            })

            resp = self.session.post(
                MEMBERSHIP_USER_API,
                params={
                    "method": "sign",
                    "clienttype": CLIENT_TYPE,
                    "app_id": APP_ID,
                    "web": WEB_FLAG,
                    "bdstoken": self.bdstoken,
                },
                timeout=15,
            )

            if resp.text and resp.text.strip():
                data = resp.json()
                errno = data.get("errno", -1)
                if errno == 0:
                    msg = "签到成功"
                    self.tasks_done.append(("签到", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                elif errno == 1 or "已签到" in str(data):
                    msg = "今日已签到"
                    self.tasks_done.append(("签到", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                elif errno == -6:
                    msg = "BDUSS已失效"
                    self.tasks_failed.append(("签到", msg))
                    log(f"[{self.account_name}] ❌ {msg}", "ERROR")
                    return False, msg
                else:
                    msg = f"签到返回errno={errno}"
                    self.tasks_failed.append(("签到", msg))
                    log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                    return False, msg
            else:
                msg = "签到API返回空响应（百度已废弃Web端签到）"
                self.tasks_failed.append(("签到", msg))
                log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                return False, msg
        except Exception as e:
            msg = f"签到异常: {e}"
            self.tasks_failed.append(("签到", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 任务2: 获取会员信息 ====================

    def task_membership_info(self):
        """任务2: 获取会员信息"""
        log(f"[{self.account_name}] [任务2] 获取会员信息...")
        try:
            resp = self.session.get(
                MEMBERSHIP_USER_API,
                params={
                    "method": "query",
                    "clienttype": CLIENT_TYPE,
                    "app_id": APP_ID,
                    "bdstoken": self.bdstoken,
                },
                timeout=15,
            )
            if resp.text and resp.text.strip():
                data = resp.json()
                if data.get("error_code", -1) == 0:
                    level_info = data.get("level_info", {})
                    self.current_level = level_info.get("current_level", 0)
                    self.current_growth = level_info.get("current_value", 0)
                    self.history_level = level_info.get("history_level", 0)
                    self.history_growth = level_info.get("history_value", 0)

                    user_tag_str = data.get("user_tag", "{}")
                    try:
                        user_tag = json.loads(user_tag_str) if isinstance(user_tag_str, str) else user_tag_str
                    except (json.JSONDecodeError, TypeError):
                        user_tag = {}

                    is_vip = user_tag.get("is_vip", 0)
                    is_svip = user_tag.get("is_svip", 0)

                    msg = f"等级Lv.{self.current_level}, 成长值{self.current_growth}, {'SVIP' if is_svip else 'VIP' if is_vip else '普通用户'}"
                    self.tasks_done.append(("会员信息", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                else:
                    msg = f"获取会员信息失败: error_code={data.get('error_code', -1)}"
                    self.tasks_failed.append(("会员信息", msg))
                    log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                    return False, msg
            else:
                msg = "会员信息API返回空响应"
                self.tasks_failed.append(("会员信息", msg))
                log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                return False, msg
        except Exception as e:
            msg = f"获取会员信息异常: {e}"
            self.tasks_failed.append(("会员信息", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 任务3: 获取成长值历史 ====================

    def task_growth_history(self):
        """任务3: 获取成长值变化历史"""
        log(f"[{self.account_name}] [任务3] 获取成长值历史...")
        try:
            resp = self.session.get(
                MEMBERSHIP_LEVEL_API,
                params={
                    "method": "list",
                    "app_id": APP_ID,
                    "bdstoken": self.bdstoken,
                },
                timeout=15,
            )
            if resp.text and resp.text.strip():
                data = resp.json()
                if data.get("error_code", -1) == 0:
                    records = data.get("level_list_infos", [])
                    # 统计近期变化
                    recent = records[:7] if len(records) >= 7 else records
                    total_change = sum(r.get("value", 0) for r in recent)
                    msg = f"近{len(recent)}天成长值变化: {total_change:+d}"
                    self.tasks_done.append(("成长值历史", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                else:
                    msg = f"获取成长值历史失败: error_code={data.get('error_code', -1)}"
                    self.tasks_failed.append(("成长值历史", msg))
                    log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                    return False, msg
            else:
                msg = "成长值历史API返回空响应"
                self.tasks_failed.append(("成长值历史", msg))
                log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                return False, msg
        except Exception as e:
            msg = f"获取成长值历史异常: {e}"
            self.tasks_failed.append(("成长值历史", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 任务4: 获取金币信息 ====================

    def task_coin_info(self):
        """任务4: 获取金币信息"""
        log(f"[{self.account_name}] [任务4] 获取金币信息...")
        try:
            resp = self.session.get(
                MEMBERSHIP_COIN_API,
                params={
                    "method": "query",
                    "app_id": APP_ID,
                    "bdstoken": self.bdstoken,
                    "clienttype": "2",
                },
                timeout=15,
            )
            if resp.text and resp.text.strip():
                data = resp.json()
                if data.get("errno", -1) == 0:
                    coin_info = data.get("data", {}).get("coin_info", [])
                    coin_count = len(coin_info)
                    msg = f"金币记录{coin_count}条"
                    self.tasks_done.append(("金币信息", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                else:
                    msg = f"获取金币信息失败: errno={data.get('errno', -1)}"
                    self.tasks_failed.append(("金币信息", msg))
                    log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                    return False, msg
            else:
                msg = "金币信息API返回空响应"
                self.tasks_failed.append(("金币信息", msg))
                log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                return False, msg
        except Exception as e:
            msg = f"获取金币信息异常: {e}"
            self.tasks_failed.append(("金币信息", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 任务5: 获取网盘容量 ====================

    def task_quota(self):
        """任务5: 获取网盘容量"""
        log(f"[{self.account_name}] [任务5] 获取网盘容量...")
        try:
            resp = self.session.get(
                PCS_QUOTA_API,
                params={"method": "info", "app_id": APP_ID_PCS},
                timeout=15,
            )
            if resp.text and resp.text.strip():
                data = resp.json()
                if "quota" in data:
                    self.quota_total = data.get("quota", 0)
                    self.quota_used = data.get("used", 0)
                    total_gb = self.quota_total / 1024 / 1024 / 1024
                    used_gb = self.quota_used / 1024 / 1024 / 1024
                    free_gb = total_gb - used_gb
                    usage_pct = (used_gb / total_gb * 100) if total_gb > 0 else 0
                    msg = f"总容量{total_gb:.0f}GB, 已用{used_gb:.0f}GB ({usage_pct:.1f}%), 剩余{free_gb:.0f}GB"
                    self.tasks_done.append(("网盘容量", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
                else:
                    msg = f"获取容量失败: {data.get('error_msg', data.get('error_code', 'unknown'))}"
                    self.tasks_failed.append(("网盘容量", msg))
                    log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                    return False, msg
            else:
                msg = "容量API返回空响应"
                self.tasks_failed.append(("网盘容量", msg))
                log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
                return False, msg
        except Exception as e:
            msg = f"获取容量异常: {e}"
            self.tasks_failed.append(("网盘容量", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 任务6: 保持会话活跃 ====================

    def task_keepalive(self):
        """任务6: 保持会话活跃（访问网盘首页）"""
        log(f"[{self.account_name}] [任务6] 保持会话活跃...")
        try:
            resp = self.session.get(
                XNAS_API,
                params={"method": "uinfo"},
                timeout=15,
            )
            if resp.text and resp.text.strip():
                data = resp.json()
                if data.get("errno", -1) == 0:
                    msg = "会话活跃"
                    self.tasks_done.append(("会话保活", msg))
                    log(f"[{self.account_name}] ✅ {msg}", "SUCCESS")
                    return True, msg
            msg = "会话保活失败"
            self.tasks_failed.append(("会话保活", msg))
            log(f"[{self.account_name}] ⚠️ {msg}", "WARN")
            return False, msg
        except Exception as e:
            msg = f"会话保活异常: {e}"
            self.tasks_failed.append(("会话保活", msg))
            log(f"[{self.account_name}] ❌ {msg}", "ERROR")
            return False, msg

    # ==================== 报告生成 ====================

    def format_report(self):
        """格式化签到报告"""
        lines = []
        lines.append(f"账号: {self.account_name}")
        lines.append(f"用户名: {self.username}")
        if self.baidu_name and self.baidu_name != self.username:
            lines.append(f"百度名: {self.baidu_name}")
        lines.append(f"UK: {self.uk}")

        vip_status = "普通用户"
        if self.history_level >= 2 or self.current_level >= 2:
            vip_status = "历史会员"
        lines.append(f"会员状态: {vip_status}")

        lines.append("")
        lines.append("── 成长值信息 ──")
        lines.append(f"  当前等级: Lv.{self.current_level}")
        lines.append(f"  当前成长值: {self.current_growth}")
        if self.history_level:
            lines.append(f"  历史最高: Lv.{self.history_level} (成长值: {self.history_growth})")

        if self.quota_total > 0:
            total_gb = self.quota_total / 1024 / 1024 / 1024
            used_gb = self.quota_used / 1024 / 1024 / 1024
            free_gb = total_gb - used_gb
            usage_pct = (used_gb / total_gb * 100) if total_gb > 0 else 0
            lines.append("")
            lines.append("── 网盘容量 ──")
            lines.append(f"  总容量: {total_gb:.0f} GB")
            lines.append(f"  已使用: {used_gb:.0f} GB ({usage_pct:.1f}%)")
            lines.append(f"  剩余: {free_gb:.0f} GB")

        lines.append("")
        lines.append("── 任务执行结果 ──")
        if self.tasks_done:
            lines.append(f"  ✅ 成功 {len(self.tasks_done)} 项:")
            for name, msg in self.tasks_done:
                lines.append(f"    • {name}: {msg}")
        if self.tasks_failed:
            lines.append(f"  ⚠️ 失败 {len(self.tasks_failed)} 项:")
            for name, msg in self.tasks_failed:
                lines.append(f"    • {name}: {msg}")

        if not self.tasks_done:
            lines.append("")
            lines.append("── 说明 ──")
            lines.append("  百度网盘已废弃Web端签到API。")
            lines.append("  签到功能已迁移至百度网盘APP内。")
            lines.append("  本脚本会每日尝试签到并监控账户状态。")

        return "\n".join(lines)

    def run(self):
        """执行完整任务流程"""
        log(f"[{self.account_name}] 开始执行任务...")

        if not self.check_login():
            return {
                "success": False,
                "message": "BDUSS验证失败，请检查Cookie是否有效",
                "report": f"账号: {self.account_name}\n状态: BDUSS已失效，请重新获取",
            }

        # 执行所有任务
        self.task_sign()           # 任务1: 签到
        self.task_membership_info() # 任务2: 会员信息
        self.task_growth_history()  # 任务3: 成长值历史
        self.task_coin_info()       # 任务4: 金币信息
        self.task_quota()           # 任务5: 网盘容量
        self.task_keepalive()       # 任务6: 会话保活

        report = self.format_report()
        log(f"[{self.account_name}] 任务执行完成")
        return {
            "success": len(self.tasks_done) > 0,
            "message": f"成功{len(self.tasks_done)}项, 失败{len(self.tasks_failed)}项",
            "report": report,
        }


# ==================== 百度账号密码登录 ====================

def login_baidu(username, password):
    """通过账号密码登录百度，获取BDUSS"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT_WEB,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://pan.baidu.com/",
    })

    try:
        session.get("https://pan.baidu.com/", timeout=15)
    except Exception:
        pass

    ts = str(int(time.time() * 1000))

    try:
        resp = session.get(PASSPORT_GETAPI, params={
            "tpl": "pp", "apiver": "v3", "class": "login",
            "logintype": "dialogLogin", "tt": ts, "_": ts,
        }, timeout=15)
        data = parse_baidu_response(resp)
        token = data.get("data", {}).get("token", "")
        if not token:
            return None, None, "获取登录token失败"
        log(f"获取token成功: {token[:8]}...")
    except Exception as e:
        return None, None, f"获取token异常: {e}"

    try:
        resp = session.get(PASSPORT_PUBKEY, params={
            "tpl": "pp", "apiver": "v3", "tt": ts, "_": ts,
        }, timeout=15)
        data = parse_baidu_response(resp)
        pubkey_pem = data.get("pubkey", "")
        if not pubkey_pem:
            return None, None, "获取RSA公钥失败"
        log("获取RSA公钥成功")
    except Exception as e:
        return None, None, f"获取公钥异常: {e}"

    try:
        encrypted_password = rsa_encrypt_password(password, pubkey_pem)
        if not encrypted_password:
            return None, None, "密码加密失败（缺少rsa库），请使用BDUSS方式"
        log("密码加密成功")
    except Exception as e:
        return None, None, f"密码加密异常: {e}"

    try:
        ts2 = str(int(time.time() * 1000))
        login_data = {
            "staticpage": "https://pan.baidu.com/", "charset": "utf-8",
            "token": token, "tpl": "pp", "apiver": "v3", "tt": ts2,
            "codestring": "", "safeflg": "0", "u": "https://pan.baidu.com/",
            "isPhone": "false", "quickuser": "0", "logintype": "dialogLogin",
            "logLoginType": "pc_loginDialog", "idc": "", "loginmerge": "true",
            "username": username, "password": encrypted_password,
            "verifycode": "", "mem_pass": "on", "ppui_logintime": ts2,
        }
        resp = session.post(PASSPORT_LOGIN, data=login_data, timeout=15)
        cookies = session.cookies.get_dict()
        bduss = cookies.get("BDUSS", "")
        stoken = cookies.get("STOKEN", "")

        if bduss:
            log(f"登录成功！BDUSS: {bduss[:8]}...")
            return bduss, stoken, "登录成功"

        error_map = {
            "400023": "需要验证码，请使用BDUSS方式登录",
            "400034": "需要短信验证码，请使用BDUSS方式登录",
            "50052": "触发设备验证(服务器IP风控)，请使用BDUSS方式登录",
            "500001": "需要短信验证，请使用BDUSS方式登录",
            "160002": "账号或密码错误，请检查",
        }
        err_no_match = re.search(r'err_no[=:]\s*(\d+)', resp.text)
        err_no = err_no_match.group(1) if err_no_match else ""
        err_msg = error_map.get(err_no, f"登录失败: errNo={err_no}")
        if not err_no:
            err_msg = "登录失败(未知错误)，请使用BDUSS方式登录"
        log(f"登录失败: {err_msg}", "WARN")
        return None, None, err_msg
    except Exception as e:
        return None, None, f"登录请求异常: {e}"


def rsa_encrypt_password(password, pubkey_pem):
    """RSA加密密码"""
    pubkey_pem = pubkey_pem.replace("\\n", "\n")
    if "BEGIN PUBLIC KEY" not in pubkey_pem:
        pubkey_pem = "-----BEGIN PUBLIC KEY-----\n" + pubkey_pem + "\n-----END PUBLIC KEY-----"

    try:
        import rsa as rsa_lib
        pubkey = rsa_lib.PublicKey.load_pkcs1_openssl_pem(pubkey_pem.encode())
        encrypted = rsa_lib.encrypt(password.encode("utf-8"), pubkey)
        return base64.b64encode(encrypted).decode()
    except ImportError:
        pass

    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        pubkey = RSA.import_key(pubkey_pem)
        cipher = PKCS1_v1_5.new(pubkey)
        encrypted = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted).decode()
    except ImportError:
        pass

    log("RSA加密失败：缺少rsa或pycryptodome库", "ERROR")
    return None


# ==================== 主函数 ====================

def parse_accounts():
    """从环境变量解析账号信息"""
    accounts = []
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
                "type": "bduss", "bduss": bduss, "stoken": stoken,
                "name": f"BDUSS账号{i+1}",
            })

    accounts_str = os.environ.get("BAIDU_ACCOUNTS", "").strip()
    if accounts_str:
        account_list = re.split(r'[&\n]', accounts_str)
        account_list = [a.strip() for a in account_list if a.strip()]
        for i, account in enumerate(account_list):
            parts = account.split("#")
            if len(parts) >= 2:
                accounts.append({
                    "type": "login",
                    "username": parts[0].strip(),
                    "password": parts[1].strip(),
                    "name": f"账号密码{i+1}",
                })

    return accounts


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════╗
║   百度网盘自动化脚本 (青龙面板版) v4.0    ║
║   模拟APP日常任务 + 账户状态监控         ║
╚══════════════════════════════════════════╝
    """)

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
        notify_send("百度网盘自动化", msg)
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
                automation = BaiduPanAutomation(
                    bduss=account["bduss"],
                    stoken=account.get("stoken", ""),
                    account_name=account["name"],
                )
                result = automation.run()
            elif account["type"] == "login":
                username = account["username"]
                password = account["password"]
                account_label = f"{username[:3]}****{username[-4:]}" if len(username) >= 7 else username

                log(f"[{account_label}] 尝试账号密码登录...")
                bduss, stoken, login_msg = login_baidu(username, password)

                if bduss:
                    log(f"[{account_label}] {login_msg}")
                    automation = BaiduPanAutomation(
                        bduss=bduss, stoken=stoken, account_name=account_label,
                    )
                    result = automation.run()
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

        time.sleep(2)

    log(f"\n{'═'*40}")
    log(f"任务完成: 成功 {success_count} 个, 失败 {fail_count} 个")

    summary = (
        f"任务完成: 成功 {success_count}/{len(accounts)}\n\n"
        + "\n\n──────────\n\n".join(reports)
    )
    notify_send("百度网盘自动化通知", summary)


if __name__ == "__main__":
    main()
