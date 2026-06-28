# BDUSS 提取浏览器插件

这是一个 Chrome/Edge 浏览器插件，用于一键提取百度网盘的 BDUSS Cookie。

插件使用浏览器的 `cookies` API，可以直接读取 **HttpOnly** 的 BDUSS（普通网页 JavaScript 无法读取）。

## 安装步骤

### 1. 下载插件

从仓库下载 `bduss-extension` 文件夹，或克隆整个仓库：

```bash
git clone https://github.com/Hayfan-wu/QL-BD-CHECKIN.git
```

### 2. 打开浏览器扩展管理页

- **Chrome**：地址栏输入 `chrome://extensions/`
- **Edge**：地址栏输入 `edge://extensions/`

### 3. 开启「开发者模式」

在扩展管理页面右上角，打开「开发者模式」开关。

### 4. 加载插件

点击「加载已解压的扩展程序」按钮，选择 `bduss-extension` 文件夹。

### 5. 使用插件

1. 确保浏览器已登录 [百度网盘](https://pan.baidu.com)
2. 点击浏览器工具栏中的插件图标（紫色钥匙图标）
3. 插件会自动提取 BDUSS 并复制到剪贴板
4. 将 BDUSS 粘贴到青龙面板环境变量中

## 截图说明

```
┌──────────────────────────────────┐
│  🔑 BDUSS 提取工具               │
│  百度网盘 Cookie 自动获取          │
├──────────────────────────────────┤
│  ✅ 提取成功！BDUSS 已复制到剪贴板 │
│                                  │
│  ┌──────────────────────────────┐│
│  │ BDUSS                        ││
│  │ xxxxxxxxxxxxxxxxxxxxxxxx...  ││
│  └──────────────────────────────┘│
│                                  │
│  [📋 复制 BDUSS]                 │
│  请确保浏览器已登录百度网盘        │
└──────────────────────────────────┘
```

## 原理

- BDUSS 是百度网盘的 `HttpOnly` Cookie，普通 JavaScript 无法通过 `document.cookie` 读取
- 浏览器插件的 `chrome.cookies` API 拥有更高权限，可以直接读取 HttpOnly Cookie
- 插件声明了 `cookies` 权限和 `*://*.baidu.com/*` 主机权限

## 文件结构

```
bduss-extension/
├── manifest.json    # 插件配置清单
├── popup.html       # 弹窗界面
├── popup.js         # Cookie 提取逻辑
└── icons/
    ├── icon16.png   # 16x16 图标
    ├── icon48.png   # 48x48 图标
    └── icon128.png  # 128x128 图标
```

## 支持的浏览器

- Google Chrome
- Microsoft Edge
- 其他基于 Chromium 的浏览器（如 Brave、360 浏览器等）
