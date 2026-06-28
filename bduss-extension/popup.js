// BDUSS 提取工具 - 浏览器插件
// 使用 chrome.cookies API 读取 HttpOnly 的 BDUSS Cookie

const BAIDU_DOMAINS = [
  "pan.baidu.com",
  ".pan.baidu.com",
  "baidu.com",
  ".baidu.com"
];

function showAlert(type, message) {
  const box = document.getElementById("alertBox");
  box.className = "alert alert-" + type;
  box.style.display = "block";
  box.textContent = message;
}

function hideAlert() {
  document.getElementById("alertBox").style.display = "none";
}

function extractBDUSS() {
  const btn = document.getElementById("extractBtn");
  btn.disabled = true;
  btn.textContent = "⏳ 正在提取...";
  hideAlert();

  // 百度网盘域名列表
  const domains = [
    "https://pan.baidu.com",
    "https://d.pcs.baidu.com",
    "https://passport.baidu.com"
  ];

  let foundBduss = null;
  let foundStoken = null;
  let checkedCount = 0;
  const totalDomains = domains.length;

  function tryGetCookie(domain, name) {
    return new Promise((resolve) => {
      chrome.cookies.get(
        { url: domain, name: name },
        (cookie) => {
          resolve(cookie);
        }
      );
    });
  }

  async function search() {
    // 遍历所有域名尝试获取 BDUSS
    for (const domain of domains) {
      // BDUSS
      const bdussCookie = await tryGetCookie(domain, "BDUSS");
      if (bdussCookie && bdussCookie.value) {
        foundBduss = bdussCookie.value;
      }

      // STOKEN
      const stokenCookie = await tryGetCookie(domain, "STOKEN");
      if (stokenCookie && stokenCookie.value) {
        foundStoken = stokenCookie.value;
      }

      // 也尝试获取 PT_PGU 和 STOKEN_LOGIN
      const ptPguCookie = await tryGetCookie(domain, "PT_PGU");
    }

    if (foundBduss) {
      // 显示结果
      document.getElementById("bdussValue").textContent = foundBduss;
      document.getElementById("resultArea").style.display = "block";

      if (foundStoken) {
        document.getElementById("stokenValue").textContent = foundStoken;
        document.getElementById("stokenArea").style.display = "block";
      }

      document.getElementById("copyBtn").style.display = "block";
      showAlert("success", "✅ 提取成功！点击下方按钮复制");

      // 自动复制到剪贴板
      try {
        navigator.clipboard.writeText(foundBduss).then(() => {
          showAlert("success", "✅ 提取成功！BDUSS 已自动复制到剪贴板");
        }).catch(() => {
          // 降级方案
          const textarea = document.createElement("textarea");
          textarea.value = foundBduss;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand("copy");
          document.body.removeChild(textarea);
          showAlert("success", "✅ 提取成功！BDUSS 已复制到剪贴板");
        });
      } catch (e) {
        showAlert("success", "✅ 提取成功！请点击下方按钮复制");
      }
    } else {
      // 尝试获取所有百度域名的所有Cookie
      chrome.cookies.getAll({}, (allCookies) => {
        const bdussCookies = allCookies.filter(
          (c) => c.name === "BDUSS" && c.domain.includes("baidu.com")
        );

        if (bdussCookies.length > 0) {
          foundBduss = bdussCookies[0].value;
          document.getElementById("bdussValue").textContent = foundBduss;
          document.getElementById("resultArea").style.display = "block";

          const stokenCookies = allCookies.filter(
            (c) => c.name === "STOKEN" && c.domain.includes("baidu.com")
          );
          if (stokenCookies.length > 0) {
            foundStoken = stokenCookies[0].value;
            document.getElementById("stokenValue").textContent = foundStoken;
            document.getElementById("stokenArea").style.display = "block";
          }

          document.getElementById("copyBtn").style.display = "block";
          copyToClipboard(foundBduss);
          showAlert("success", "✅ 提取成功！BDUSS 已复制到剪贴板");
        } else {
          showAlert(
            "error",
            "❌ 未找到 BDUSS，请先在浏览器中登录百度网盘 (pan.baidu.com)"
          );
        }
      });
    }

    btn.disabled = false;
    btn.textContent = "🔍 重新提取";
  }

  search();
}

function copyToClipboard(text) {
  try {
    navigator.clipboard.writeText(text);
  } catch (e) {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }
}

function copyBDUSS() {
  const value = document.getElementById("bdussValue").textContent;
  copyToClipboard(value);
  showAlert("success", "✅ 已复制到剪贴板！");
}

document.addEventListener("DOMContentLoaded", () => {
  // 页面加载后自动提取
  setTimeout(() => {
    extractBDUSS();
  }, 300);
});
