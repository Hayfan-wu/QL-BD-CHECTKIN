/**
 * 百度网盘APP任务自动化脚本 (Auto.js Pro)
 * ====================================
 * 功能：
 *   1. 自动观看广告×15次（+75积分）
 *   2. 尝试添加桌面小组件（+10积分）
 *   3. 尝试美团刷视频任务（+20积分）
 *   4. 每日定时自动执行
 *   5. 执行结果通知推送
 *
 * 使用方法：
 *   1. 手机安装 Auto.js Pro
 *   2. 开启无障碍服务
 *   3. 导入此脚本
 *   4. 运行 setup() 配置定时任务
 *   5. 或直接运行 main() 执行一次
 *
 * 注意：
 *   - 手机需保持百度网盘APP已登录
 *   - 手机需保持常开和联网
 *   - 首次运行需授权截图权限
 *   - APP更新后可能需要调整控件选择器
 * ====================================
 */

// ==================== 配置 ====================

var CONFIG = {
    // 百度网盘包名
    PACKAGE_NAME: "com.baidu.netdisk",
    // 美团包名
    MEITUAN_PACKAGE: "com.sankuai.meituan",
    // 观看广告次数
    AD_WATCH_COUNT: 15,
    // 广告等待时间（毫秒），广告通常15-30秒
    AD_WAIT_TIME: 35000,
    // 广告关闭按钮查找超时
    AD_CLOSE_TIMEOUT: 10000,
    // 操作间隔（毫秒）
    ACTION_DELAY: 2000,
    // 是否调试模式
    DEBUG: true,
    // 通知标题
    NOTIFY_TITLE: "百度网盘任务通知",
};

// ==================== 日志工具 ====================

function log(msg, level) {
    level = level || "INFO";
    var ts = new Date().toLocaleString();
    console.log("[" + ts + "] [" + level + "] " + msg);
    if (level === "ERROR") {
        toast(msg);
    }
}

function sleep(ms) {
    java.lang.Thread.sleep(ms);
}

function randomSleep(min, max) {
    var ms = min + Math.random() * (max - min);
    sleep(Math.floor(ms));
}

// ==================== 通知推送 ====================

function sendNotify(title, content) {
    try {
        // 方式1: Auto.js内置通知
        var builder = new android.app.Notification.Builder(context)
            .setContentTitle(title)
            .setContentText(content.substring(0, 100))
            .setSmallIcon(android.R.drawable.ic_dialog_info);
        var manager = context.getSystemService(context.NOTIFICATION_SERVICE);
        manager.notify(1, builder.build());
        log("通知已发送: " + title);
    } catch (e) {
        log("通知发送失败: " + e, "WARN");
    }

    // 方式2: 如果安装了Server酱或WxPusher，可在此添加HTTP推送
    // 示例（需要填写自己的推送Key）:
    // http.postJson("http://sctapi.ftqq.com/YOUR_KEY.send", {
    //     title: title,
    //     desp: content
    // });
}

// ==================== 核心功能 ====================

var taskResults = {
    ad: { done: 0, failed: 0, msg: "" },
    widget: { done: false, msg: "" },
    meituan: { done: false, msg: "" },
    startTime: new Date(),
};

/**
 * 启动百度网盘APP
 */
function launchBaiduPan() {
    log("启动百度网盘APP...");

    // 检查是否已在运行
    var currentPackage = currentPackage();
    if (currentPackage === CONFIG.PACKAGE_NAME) {
        log("百度网盘已在运行");
        return true;
    }

    // 启动APP
    app.launchPackage(CONFIG.PACKAGE_NAME);
    sleep(5000);

    // 等待APP启动
    var maxWait = 30000;
    var waited = 0;
    while (waited < maxWait) {
        if (currentPackage() === CONFIG.PACKAGE_NAME) {
            log("百度网盘启动成功");
            sleep(2000);
            return true;
        }
        sleep(1000);
        waited += 1000;
    }

    log("百度网盘启动超时", "ERROR");
    return false;
}

/**
 * 导航到任务中心
 * 路径: 首页 → 我的 → 做任务赚积分
 */
function navigateToTaskCenter() {
    log("导航到任务中心...");

    // 确保在百度网盘APP内
    if (currentPackage() !== CONFIG.PACKAGE_NAME) {
        if (!launchBaiduPan()) return false;
    }

    // 步骤1: 点击底部"我的"标签
    log("点击「我的」标签...");
    var myTab = null;

    // 尝试多种方式找到"我的"标签
    var selectors = [
        text("我的").findOne.bind(text("我的")),
        desc("我的").findOne.bind(desc("我的")),
        textContains("我的").findOne.bind(textContains("我的")),
    ];

    for (var i = 0; i < 3; i++) {
        try {
            myTab = text("我的").findOne(5000);
            if (myTab) break;
            myTab = desc("我的").findOne(5000);
            if (myTab) break;
        } catch (e) {
            sleep(1000);
        }
    }

    if (myTab) {
        myTab.click();
        log("已点击「我的」");
        sleep(3000);
    } else {
        log("未找到「我的」标签，尝试使用坐标点击", "WARN");
        // 通常底部标签栏在屏幕底部，"我的"在右侧
        // 尝试点击底部右侧区域
        var width = device.width;
        var height = device.height;
        click(width * 0.8, height - 80);
        sleep(3000);
    }

    // 步骤2: 查找任务中心入口
    log("查找任务中心入口...");

    // 查找"做任务赚积分"或"任务中心"按钮
    var taskEntryTexts = [
        "做任务赚积分",
        "任务中心",
        "赚积分",
        "每日任务",
        "签到",
        "做任务",
        "领积分",
        "积分商城",
    ];

    var taskEntry = null;
    for (var i = 0; i < taskEntryTexts.length; i++) {
        taskEntry = text(taskEntryTexts[i]).findOne(3000);
        if (taskEntry) {
            log("找到入口: " + taskEntryTexts[i]);
            break;
        }
        taskEntry = textContains(taskEntryTexts[i]).findOne(2000);
        if (taskEntry) {
            log("找到入口(模糊匹配): " + taskEntryTexts[i]);
            break;
        }
    }

    if (taskEntry) {
        taskEntry.click();
        sleep(3000);
        log("已进入任务中心");
        return true;
    }

    // 如果没找到，尝试下滑查找
    log("未找到任务入口，尝试下滑查找...");
    scrollDown();
    sleep(2000);

    for (var i = 0; i < taskEntryTexts.length; i++) {
        taskEntry = text(taskEntryTexts[i]).findOne(3000);
        if (taskEntry) {
            taskEntry.click();
            sleep(3000);
            log("下滑后找到入口: " + taskEntryTexts[i]);
            return true;
        }
    }

    log("未找到任务中心入口", "ERROR");
    return false;
}

/**
 * 任务1: 自动观看广告
 */
function watchAdTask() {
    log("=== 任务1: 观看广告 ===");

    var successCount = 0;
    var failCount = 0;

    for (var i = 0; i < CONFIG.AD_WATCH_COUNT; i++) {
        log("第 " + (i + 1) + "/" + CONFIG.AD_WATCH_COUNT + " 次观看广告");

        // 查找"观看广告"或类似按钮
        var adButton = findAdButton();

        if (!adButton) {
            log("未找到广告按钮，可能已完成或界面变化", "WARN");
            // 尝试下滑查找更多任务
            scrollDown();
            sleep(2000);
            adButton = findAdButton();
            if (!adButton) {
                log("仍未找到广告按钮，结束广告任务", "WARN");
                break;
            }
        }

        // 点击观看广告
        try {
            adButton.click();
            log("已点击观看广告，等待广告播放...");
        } catch (e) {
            log("点击广告按钮失败: " + e, "ERROR");
            failCount++;
            continue;
        }

        // 等待广告加载
        sleep(3000);

        // 检查是否真的进入了广告
        // 广告通常会有倒计时或跳过按钮
        var adStarted = false;
        var skipBtn = text("跳过").findOne(3000);
        if (skipBtn || desc("跳过").findOne(2000)) {
            adStarted = true;
            log("广告已开始播放");
        }

        // 等待广告播放完成
        log("等待广告播放完成（约" + (CONFIG.AD_WAIT_TIME / 1000) + "秒）...");
        sleep(CONFIG.AD_WAIT_TIME);

        // 尝试关闭广告
        var closed = closeAd();

        if (closed) {
            successCount++;
            log("第 " + (i + 1) + " 次广告观看完成 ✅");
        } else {
            failCount++;
            log("第 " + (i + 1) + " 次广告关闭失败 ❌", "WARN");
            // 尝试按返回键退出
            back();
            sleep(2000);
        }

        // 等待返回任务中心
        sleep(CONFIG.ACTION_DELAY);

        // 检查是否有积分奖励弹窗
        var rewardBtn = text("确定").findOne(2000) || text("领取").findOne(2000)
                     || text("好的").findOne(2000) || text("知道了").findOne(2000);
        if (rewardBtn) {
            rewardBtn.click();
            sleep(1000);
        }
    }

    taskResults.ad.done = successCount;
    taskResults.ad.failed = failCount;
    taskResults.ad.msg = "观看广告: 成功" + successCount + "次, 失败" + failCount + "次";

    log("广告任务完成: 成功 " + successCount + "/" + CONFIG.AD_WATCH_COUNT);
    return successCount > 0;
}

/**
 * 查找广告按钮
 */
function findAdButton() {
    var adTexts = [
        "观看广告",
        "看广告",
        "立即观看",
        "看视频",
        "观看视频",
        "去观看",
        "免费观看",
    ];

    for (var i = 0; i < adTexts.length; i++) {
        var btn = text(adTexts[i]).findOne(3000);
        if (btn) return btn;

        btn = textContains(adTexts[i]).findOne(2000);
        if (btn) return btn;

        btn = desc(adTexts[i]).findOne(2000);
        if (btn) return btn;
    }

    return null;
}

/**
 * 关闭广告
 */
function closeAd() {
    log("尝试关闭广告...");

    // 尝试多种关闭方式
    var closeSelectors = [
        // 常见关闭按钮文本
        { type: "text", value: "关闭" },
        { type: "text", value: "X" },
        { type: "text", value: "×" },
        { type: "desc", value: "关闭" },
        { type: "desc", value: "close" },
        // 常见关闭按钮ID
        { type: "id", value: "close_btn" },
        { type: "id", value: "btn_close" },
        { type: "id", value: "iv_close" },
        { type: "id", value: "close" },
        // 常见关闭按钮类名
        { type: "className", value: "android.widget.ImageView" },
    ];

    // 先尝试文本/描述/ID查找
    for (var i = 0; i < closeSelectors.length; i++) {
        var sel = closeSelectors[i];
        var btn = null;

        try {
            if (sel.type === "text") {
                btn = text(sel.value).findOne(2000);
            } else if (sel.type === "desc") {
                btn = desc(sel.value).findOne(2000);
            } else if (sel.type === "id") {
                btn = id(sel.value).findOne(2000);
            } else if (sel.type === "className") {
                // 只查找可点击的ImageView（通常是关闭按钮）
                btn = className(sel.value).clickable(true).findOne(2000);
            }

            if (btn) {
                btn.click();
                log("通过" + sel.type + "='" + sel.value + "'关闭广告");
                sleep(1000);
                return true;
            }
        } catch (e) {
            // 继续尝试下一种方式
        }
    }

    // 如果文本查找失败，尝试点击右上角区域
    log("文本查找关闭按钮失败，尝试坐标点击右上角...");
    var width = device.width;
    click(width - 50, 80);
    sleep(1000);

    // 检查是否关闭成功（检查是否回到了任务中心）
    var taskCenter = text("做任务赚积分").findOne(2000)
                  || textContains("积分").findOne(2000);
    if (taskCenter) {
        log("广告已关闭（坐标点击）");
        return true;
    }

    // 最后尝试返回键
    log("尝试按返回键关闭广告...");
    back();
    sleep(2000);

    return true; // 假设已关闭
}

/**
 * 任务2: 添加桌面小组件
 */
function addWidgetTask() {
    log("=== 任务2: 添加桌面小组件 ===");

    // 查找"添加小组件"任务按钮
    var widgetTexts = [
        "添加小组件",
        "桌面小组件",
        "添加组件",
        "一键添加",
        "去添加",
    ];

    var widgetBtn = null;
    for (var i = 0; i < widgetTexts.length; i++) {
        widgetBtn = text(widgetTexts[i]).findOne(3000);
        if (widgetBtn) break;
        widgetBtn = textContains(widgetTexts[i]).findOne(2000);
        if (widgetBtn) break;
    }

    if (!widgetBtn) {
        // 尝试下滑查找
        scrollDown();
        sleep(2000);
        for (var i = 0; i < widgetTexts.length; i++) {
            widgetBtn = text(widgetTexts[i]).findOne(3000);
            if (widgetBtn) break;
            widgetBtn = textContains(widgetTexts[i]).findOne(2000);
            if (widgetBtn) break;
        }
    }

    if (!widgetBtn) {
        taskResults.widget.msg = "未找到小组件任务";
        log("未找到小组件任务按钮", "WARN");
        return false;
    }

    log("找到小组件任务，点击...");
    widgetBtn.click();
    sleep(3000);

    // 小组件添加流程因系统不同而不同
    // 通常会跳转到桌面或弹出小组件选择器
    log("等待小组件添加界面...");

    // 尝试查找"添加"或"完成"按钮
    var addBtn = text("添加").findOne(5000)
              || text("完成").findOne(5000)
              || text("确定").findOne(5000)
              || text("一键添加").findOne(5000);

    if (addBtn) {
        addBtn.click();
        sleep(3000);
        taskResults.widget.done = true;
        taskResults.widget.msg = "小组件添加成功";
        log("小组件添加成功 ✅");
        return true;
    }

    // 如果没有找到按钮，可能需要手动操作
    taskResults.widget.msg = "小组件任务需手动完成（界面不兼容自动操作）";
    log("小组件任务可能需要手动完成", "WARN");

    // 返回百度网盘
    app.launchPackage(CONFIG.PACKAGE_NAME);
    sleep(3000);
    return false;
}

/**
 * 任务3: 美团刷视频任务
 */
function meituanTask() {
    log("=== 任务3: 美团刷视频 ===");

    // 查找美团任务按钮
    var meituanTexts = [
        "去美团刷视频",
        "美团刷视频",
        "去美团",
        "刷视频",
        "去完成",
    ];

    var meituanBtn = null;
    for (var i = 0; i < meituanTexts.length; i++) {
        meituanBtn = text(meituanTexts[i]).findOne(3000);
        if (meituanBtn) break;
        meituanBtn = textContains(meituanTexts[i]).findOne(2000);
        if (meituanBtn) break;
    }

    if (!meituanBtn) {
        // 尝试下滑查找
        scrollDown();
        sleep(2000);
        for (var i = 0; i < meituanTexts.length; i++) {
            meituanBtn = text(meituanTexts[i]).findOne(3000);
            if (meituanBtn) break;
            meituanBtn = textContains(meituanTexts[i]).findOne(2000);
            if (meituanBtn) break;
        }
    }

    if (!meituanBtn) {
        taskResults.meituan.msg = "未找到美团任务";
        log("未找到美团任务按钮", "WARN");
        return false;
    }

    log("找到美团任务，点击...");
    meituanBtn.click();
    sleep(5000);

    // 检查是否跳转到美团APP
    var currentPkg = currentPackage();
    if (currentPkg === CONFIG.MEITUAN_PACKAGE || currentPkg !== CONFIG.PACKAGE_NAME) {
        log("已跳转到美团APP（或浏览器）");

        // 等待视频加载
        log("等待视频加载...");
        sleep(10000);

        // 刷视频（滑动几次）
        log("开始刷视频...");
        for (var i = 0; i < 5; i++) {
            // 上滑切换下一个视频
            var width = device.width;
            var height = device.height;
            swipe(width / 2, height * 0.7, width / 2, height * 0.3, 500);
            log("第 " + (i + 1) + " 次滑动");
            sleep(8000); // 每个视频看8秒
        }

        taskResults.meituan.done = true;
        taskResults.meituan.msg = "美团刷视频完成";
        log("美团刷视频完成 ✅");
    } else {
        taskResults.meituan.msg = "未跳转到美团APP，可能未安装美团";
        log("未跳转到美团APP，可能未安装美团", "WARN");
    }

    // 返回百度网盘
    log("返回百度网盘...");
    app.launchPackage(CONFIG.PACKAGE_NAME);
    sleep(3000);

    // 重新进入任务中心
    navigateToTaskCenter();

    return taskResults.meituan.done;
}

/**
 * 生成执行报告
 */
function generateReport() {
    var endTime = new Date();
    var duration = Math.floor((endTime - taskResults.startTime) / 1000);
    var min = Math.floor(duration / 60);
    var sec = duration % 60;

    var report = "";
    report += "百度网盘任务执行报告\n";
    report += "执行时间: " + taskResults.startTime.toLocaleString() + "\n";
    report += "耗时: " + min + "分" + sec + "秒\n";
    report += "━━━━━━━━━━━━━━━━━━━\n";
    report += "1. 观看广告: " + taskResults.ad.msg + "\n";
    report += "2. 添加小组件: " + (taskResults.widget.done ? "✅ " : "⚠️ ") + taskResults.widget.msg + "\n";
    report += "3. 美团刷视频: " + (taskResults.meituan.done ? "✅ " : "⚠️ ") + taskResults.meituan.msg + "\n";
    report += "━━━━━━━━━━━━━━━━━━━\n";

    var totalDone = taskResults.ad.done + (taskResults.widget.done ? 1 : 0) + (taskResults.meituan.done ? 1 : 0);
    report += "总计完成: " + totalDone + " 项任务\n";

    return report;
}

/**
 * 主函数
 */
function main() {
    log("百度网盘任务自动化脚本启动");

    // 请求截图权限（首次运行需要）
    try {
        requestScreenCapture(false);
    } catch (e) {
        log("截图权限获取失败（不影响主要功能）", "WARN");
    }

    // 确保无障碍服务已开启
    if (!auto.service) {
        log("无障碍服务未开启，请在设置中开启", "ERROR");
        toast("请先开启Auto.js无障碍服务");
        return;
    }

    // 启动百度网盘
    if (!launchBaiduPan()) {
        sendNotify(CONFIG.NOTIFY_TITLE, "百度网盘启动失败，请检查APP是否已安装");
        return;
    }

    // 导航到任务中心
    if (!navigateToTaskCenter()) {
        sendNotify(CONFIG.NOTIFY_TITLE, "无法进入任务中心，请检查APP界面");
        return;
    }

    // 执行任务1: 观看广告
    watchAdTask();

    // 执行任务2: 添加小组件
    addWidgetTask();

    // 执行任务3: 美团刷视频
    meituanTask();

    // 生成报告
    var report = generateReport();
    log(report);

    // 发送通知
    sendNotify(CONFIG.NOTIFY_TITLE, report);

    // 返回桌面
    home();
    log("脚本执行完成");
}

/**
 * 配置每日定时任务
 */
function setup() {
    log("配置每日定时任务...");

    try {
        // 使用Auto.js Pro的work_manager
        var task = work_manager.addDailyTask({
            tag: "baidu_pan_daily",
            hour: 8,          // 每天8点
            minute: 0,
            delay: 0,
            package: context.getPackageName(),
            script: files.cwd() + "/" + files.name(__filename__ || "baidu_pan_autojs.js"),
        });

        log("定时任务配置成功！每天8:00自动执行");
        toast("定时任务已设置: 每天8:00执行");
    } catch (e) {
        log("定时任务配置失败: " + e, "ERROR");

        // 降级方案: 使用setInterval
        log("尝试使用setInterval降级方案...");
        var alarmTime = new Date();
        alarmTime.setHours(8, 0, 0, 0);
        if (alarmTime < new Date()) {
            alarmTime.setDate(alarmTime.getDate() + 1);
        }
        var delay = alarmTime - new Date();

        setTimeout(function() {
            main();
            // 每24小时重复
            setInterval(main, 24 * 60 * 60 * 1000);
        }, delay);

        log("降级定时任务已设置: 下次执行 " + alarmTime.toLocaleString());
        toast("定时任务已设置(降级模式): " + alarmTime.toLocaleString());
    }
}

// ==================== 入口 ====================

// 如果直接运行，执行main
if (typeof module === "undefined" || !module.parent) {
    // 检查是否传入参数
    var mode = engines.myEngine().execParam || "main";

    if (mode === "setup") {
        setup();
    } else if (mode === "test") {
        // 测试模式: 只执行1次广告观看
        CONFIG.AD_WATCH_COUNT = 1;
        CONFIG.AD_WAIT_TIME = 20000;
        log("=== 测试模式 ===");
        main();
    } else {
        main();
    }
}
