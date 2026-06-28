# BDUSS 获取方法

本文档介绍三种获取 BDUSS 的方法，推荐使用**方法一**。

## 方法一：扫码登录（推荐）

在**本地电脑**（非服务器）上运行扫码登录脚本：

```bash
# 安装依赖
pip install requests qrcode

# 运行扫码登录
python3 qr_login.py
```

运行后会生成二维码，用手机百度APP扫码并确认登录，自动获取 BDUSS。

> **注意**：必须在本地电脑运行，服务器IP会触发百度风控导致扫码失败。

## 方法二：浏览器手动提取

1. 打开浏览器访问 [pan.baidu.com](https://pan.baidu.com) 并登录
2. 按 `F12` 打开开发者工具
3. 点击顶部 **Application**（应用程序）标签
   - Chrome 中文版：**应用程序**
   - Firefox：**存储** → **Cookie**
4. 左侧找到 **Cookies** → `https://pan.baidu.com`
5. 在列表中找到 `BDUSS`
6. 双击 Value 列，复制完整值（一长串字符）
7. 将复制的值填入青龙面板环境变量

### Chrome 浏览器截图指引

```
F12 → Application → Cookies → pan.baidu.com → BDUSS

┌─────────────────────────────────────────────┐
│ Name        Value                           │
├─────────────────────────────────────────────┤
│ BDUSS       xxxxxxxxxxxxxxxxxxxxxxxxx...    │ ← 复制这个值
│ STOKEN      yyyyyyyyyyyyyyyyyyyyyyyyy...    │
│ BAIDUID     zzzzzzzzzzzzzzzzzzzzzzzzz...    │
└─────────────────────────────────────────────┘
```

## 方法三：Cookie 编辑器插件

1. 安装浏览器插件 **Cookie-Editor** 或 **EditThisCookie**
2. 访问 [pan.baidu.com](https://pan.baidu.com) 并登录
3. 点击插件图标
4. 找到 `BDUSS` 条目，复制其值

## 配置到青龙面板

获取 BDUSS 后，在青龙面板中配置：

1. 进入 **环境变量** 页面
2. 点击 **添加**
3. 名称填 `BDUSS`
4. 值填你获取的 BDUSS
5. 点击确定保存

多账号配置：多个 BDUSS 用 `&` 分隔
```
BDUSS=第一个BDUSS值&第二个BDUSS值
```

## BDUSS 有效期

- BDUSS 通常有效期较长（数月）
- 修改密码、异地登录等情况会导致失效
- 失效后重新获取即可
