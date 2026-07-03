# WPS 自动签到配置指南

## 当前状态说明

- **自动签到**：WPS 官方增加了 `client_code` 时效性参数，纯 API 自动签到**可能不稳定**。建议每日仍在小程序手动签到一次（6:00-13:00）。
- **自动邀请**：邀请好友功能**仍然有效**，每日可邀请最多 10 人，每人额外获得 1 天会员。
- **稻壳签到**：每日 7:00-14:00 可自动签到。

## 方案一：GitHub Actions 自动化（推荐，免费）

### 1. 获取 WPS 凭证

**获取 sid：**
1. 浏览器打开 https://zt.wps.cn/2018/clock_in/
2. 微信扫码登录
3. 按 F12 打开开发者工具 → Application → Cookies → 找到 `wps_sid`
4. 复制 `V02S...` 开头的值

**获取 invite_userid：**
1. 打开 https://vip.wps.cn/center_page/user_index
2. 页面会显示你的用户 ID（纯数字）

### 2. Fork 并配置 GitHub Secrets

1. 将本项目 Fork 到你的 GitHub 账号
2. 进入仓库 Settings → Secrets and variables → Actions → New repository secret
3. 添加以下 Secrets：

| Secret 名称 | 说明 | 必填 |
|-------------|------|------|
| `WPS_SID` | 你的 WPS sid | 是 |
| `WPS_INVITE_USERID` | 你的 WPS 用户 ID（纯数字） | 是 |
| `SERVER_CHAN_KEY` | Server酱 SendKey（可选） | 否 |
| `WECOM_WEBHOOK` | 企业微信机器人 Webhook（可选） | 否 |
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook（可选） | 否 |

### 3. 启用 GitHub Actions

1. 进入仓库 Actions 页面
2. 点击 "I understand my workflows..." 启用
3. 手动触发一次测试：Actions → WPS 自动签到 → Run workflow

## 方案二：Linux 服务器 Crontab 定时执行

```bash
# 1. 安装依赖
pip3 install requests --break-system-packages

# 2. 编辑脚本配置
# 修改 wps_auto_signin.py 中的 CONFIG 字典，或设置环境变量

# 3. 添加 crontab 定时任务（每天早上 8:00 执行）
crontab -e
# 添加以下行：
0 8 * * * cd /path/to/project && python3 wps_auto_signin.py >> /var/log/wps_signin.log 2>&1
```

## 方案三：Windows 任务计划程序

1. 安装 Python 3 和 requests 库
2. 修改 `wps_auto_signin.py` 中的 CONFIG 配置
3. 打开"任务计划程序" → 创建基本任务
4. 触发器：每天 8:00
5. 操作：启动程序 → `python3` → 参数：`wps_auto_signin.py`
6. 起始位置：脚本所在目录

## 方案四：金山文档 AirScript（零服务器）

如果你有金山文档账号，可以使用 AirScript 在云端直接运行签到脚本，无需任何服务器：

1. 访问 https://github.com/imoki/sign_script（796 stars）
2. 按照 README 将脚本导入金山文档
3. 在表格中配置你的 sid
4. 设置定时触发器

## 通知推送配置（可选）

| 推送方式 | 获取地址 |
|----------|---------|
| Server酱 Turbo | https://sct.ftqq.com/ |
| 企业微信机器人 | 企业微信群 → 群机器人 → 复制 Webhook |
| 钉钉机器人 | 钉钉群 → 智能群助手 → 添加机器人 |

## 常见问题

**Q: 签到提示失败？**
A: WPS 自动签到可能因 `client_code` 限制而失败。建议仍每天手动签到一次，邀请功能可自动完成。

**Q: sid 多久过期？**
A: 通常 1-2 周，过期后需重新从浏览器获取。

**Q: 会员什么时候到账？**
A: 当日签到，次日 18:00 左右到账。