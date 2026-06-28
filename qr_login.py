#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘扫码登录工具 - 获取BDUSS
===================================
在本地运行此脚本，用手机百度APP扫码登录后自动获取BDUSS

使用方法：
  python3 qr_login.py

注意：
  - 请在本地电脑运行（非服务器），避免IP风控
  - 需要安装 requests 库: pip install requests
===================================
"""
import requests
import time
import json
import re
import sys

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

GETQRCODE_API = "https://passport.baidu.com/v2/api/getqrcode"
QRIMAGE_URL = "https://passport.baidu.com/v2/api/qrcode"
UNICAST_API = "https://passport.baidu.com/channel/unicast"
LOGIN_API = "https://passport.baidu.com/v2/api/?login"


def normalize_json(text):
    """将百度的非标准JSON(单引号)转换为标准JSON"""
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


def parse_resp(resp):
    """解析百度API响应"""
    text = resp.text
    try:
        return resp.json()
    except:
        pass
    try:
        return json.loads(normalize_json(text))
    except:
        pass
    match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            try:
                return json.loads(normalize_json(match.group(1)))
            except:
                pass
    return {}


def main():
    print("""
╔══════════════════════════════════════════╗
║   百度网盘扫码登录 - 获取BDUSS           ║
║   请在本地电脑运行此脚本                 ║
╚══════════════════════════════════════════╝
    """)

    try:
        import requests
    except ImportError:
        print("缺少 requests 库，请执行: pip install requests")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://passport.baidu.com/v2/?login",
    })

    # 初始化
    print("[1/5] 初始化会话...")
    session.get("https://pan.baidu.com/", timeout=15)
    print("  完成")

    total_deadline = time.time() + 300
    attempt = 0

    while time.time() < total_deadline:
        attempt += 1
        ts = str(int(time.time() * 1000))
        gid = str(int(time.time() * 1000) % 1000000)

        # 获取二维码
        print(f"\n[2/5] 生成二维码(第{attempt}次)...")
        resp = session.get(GETQRCODE_API, params={
            "lp": "pc", "qrloginfrom": "pc", "gid": gid,
            "apiver": "v3", "tt": ts, "_": ts,
            "tpl": "pp", "clientfrom": "web",
        }, timeout=15)
        data = parse_resp(resp)
        sign = data.get("sign", "")

        if not sign:
            print(f"  获取失败: {data}")
            time.sleep(5)
            continue

        # 下载二维码
        imgurl = data.get("imgurl", "")
        qr_url = f"https://{imgurl}" if not imgurl.startswith("http") else imgurl
        resp_img = session.get(qr_url, timeout=15)

        qr_path = "baidu_qrcode.png"
        with open(qr_path, "wb") as f:
            f.write(resp_img.content)
        print(f"  二维码已保存: {qr_path}")
        print(f"  二维码链接: {qr_url}")

        # 尝试用终端显示二维码（如果安装了qrcode库）
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=1, border=1)
            qr.add_data(qr_url)
            qr.make(fit=True)
            print("\n  二维码（也可用手机扫描下方字符画）：\n")
            qr.print_ascii(invert=True)
            print()
        except ImportError:
            pass

        print("\n[3/5] 请用手机百度APP扫描二维码！")
        print("    扫码后在手机上点击「确认登录」")
        print("    (二维码有效期约120秒)")

        # 轮询等待扫码
        qr_deadline = time.time() + 120
        vcode = None
        scanned = False

        while time.time() < qr_deadline and time.time() < total_deadline:
            ts = str(int(time.time() * 1000))
            try:
                resp = session.get(UNICAST_API, params={
                    "channel_id": sign, "tpl": "pp", "qrloginfrom": "pc",
                    "gid": gid, "apiver": "v3", "tt": ts, "_": ts,
                    "clientfrom": "web",
                }, timeout=30)
                data = parse_resp(resp)
            except requests.exceptions.ReadTimeout:
                data = {"errno": -1}
            except Exception as e:
                print(f"  异常: {e}")
                time.sleep(2)
                continue

            errno = data.get("errno", -1)

            if errno == 0:
                v = data.get("v", "")
                vcode = v
                # 尝试解析v
                if isinstance(v, str):
                    try:
                        vp = json.loads(v)
                        vcode = vp.get("vcode", v)
                    except:
                        if "vcode=" in v:
                            m = re.search(r'vcode=([^&]+)', v)
                            vcode = m.group(1) if m else v
                print("\n  扫码确认成功！")
                break
            elif errno == -1:
                remaining = int(qr_deadline - time.time())
                if scanned:
                    print(f"  已扫码，请确认！剩余{remaining}秒")
                else:
                    print(f"  等待扫码... 剩余{remaining}秒")
            elif errno == 1:
                scanned = True
                print("  已扫码！请在手机上点击「确认登录」")
            else:
                print(f"  状态: errno={errno}")

            time.sleep(1 if scanned else 3)

        if not vcode:
            print("  二维码过期，重新生成...")
            continue

        # 登录
        print("\n[4/5] 正在登录...")
        ts = str(int(time.time() * 1000))
        session.get(LOGIN_API, params={
            "vcode": vcode, "tpl": "pp", "apiver": "v3",
            "loginmerge": "true", "clientfrom": "web",
            "tt": ts, "_": ts,
        }, timeout=15, allow_redirects=True)

        cookies = session.cookies.get_dict()
        bduss = cookies.get("BDUSS", "")
        stoken = cookies.get("STOKEN", "")

        if bduss:
            print("\n[5/5] 登录成功！")
            print("\n" + "=" * 60)
            print("  BDUSS 获取成功！")
            print("=" * 60)
            print(f"\n  BDUSS:  {bduss}")
            if stoken:
                print(f"  STOKEN: {stoken}")
            print("\n  请将上面的 BDUSS 值填入青龙面板环境变量")
            print("=" * 60)

            # 保存到文件
            with open("bduss.txt", "w") as f:
                f.write(f"BDUSS={bduss}\n")
                if stoken:
                    f.write(f"STOKEN={stoken}\n")
            print(f"\n  已保存到 bduss.txt")
            return
        else:
            print("  登录失败，BDUSS未获取")
            print(f"  Cookie列表: {list(cookies.keys())}")
            print("  重试中...")
            continue

    print("\n超时，请重新运行脚本")


if __name__ == "__main__":
    main()
