#!/usr/bin/env python3
"""
WPS 会员自动签到 & 邀请脚本
=================================
功能：
  1. 自动签到打卡（可能受 client_code 限制）
  2. 自动邀请好友（每日最多 10 人，邀请成功后额外获得会员天数）
  3. 支持 Server酱 / 企业微信 / 钉钉 通知推送

使用方式：
  1. 填写下方 CONFIG 配置区
  2. python3 wps_auto_signin.py

定时运行：
  - Linux: crontab -e 添加定时任务
  - GitHub Actions: 使用配套的 .github/workflows/wps_signin.yml
"""

import json
import os
import time
import random
import hashlib
import requests
from datetime import datetime

# ============================================================
# 配置区 - 请修改以下配置
# ============================================================

CONFIG = {
    # ---------- WPS 签到配置 ----------
    # 你的 WPS sid（从浏览器 Cookie 中获取，V02S... 开头）
    "wps_sid": os.environ.get("WPS_SID", "YOUR_WPS_SID_HERE"),

    # 你的 WPS 用户 ID（纯数字，如 191641526）
    "invite_userid": int(os.environ.get("WPS_INVITE_USERID", "0")),

    # ---------- 预置小号 sid（用于接受邀请）----------
    # 每个小号每天只能被邀请一次，建议间隔 >= 2 秒
    "invite_sids": os.environ.get("WPS_INVITE_SIDS", "").split(",") if os.environ.get("WPS_INVITE_SIDS", "") else [
        "V02StVuaNcoKrZ3BuvJQ1FcFS_xnG2k00af250d4002664c02f",
        "V02SWIvKWYijG6Rggo4m0xvDKj1m7ew00a8e26d3002508b828",
        "V02Sr3nJ9IicoHWfeyQLiXgvrRpje6E00a240b890023270f97",
        "V02SBsNOf4sJZNFo4jOHdgHg7-2Tn1s00a338776000b669579",
        "V02ScVbtm2pQD49ArcgGLv360iqQFLs014c8062e000b6c37b6",
        "V02S2oI49T-Jp0_zJKZ5U38dIUSIl8Q00aa679530026780e96",
        "V02ShotJqqiWyubCX0VWTlcbgcHqtSQ00a45564e002678124c",
        "V02SFiqdXRGnH5oAV2FmDDulZyGDL3M00a61660c0026781be1",
        "V02S7tldy5ltYcikCzJ8PJQDSy_ElEs00a327c3c0026782526",
        "V02SPoOluAnWda0dTBYTXpdetS97tyI00a16135e002684bb5c",
    ],

    # ---------- 通知推送配置（可选）----------
    # Server酱 Turbo 版 SendKey
    "server_chan_key": os.environ.get("SERVER_CHAN_KEY", ""),
    # 企业微信机器人 Webhook
    "wecom_webhook": os.environ.get("WECOM_WEBHOOK", ""),
    # 钉钉机器人 Webhook
    "dingtalk_webhook": os.environ.get("DINGTALK_WEBHOOK", ""),
}

# ============================================================
# API 端点
# ============================================================

API = {
    "sign_up": "http://zt.wps.cn/2018/clock_in/api/sign_up",
    "get_question": "http://zt.wps.cn/2018/clock_in/api/get_question",
    "answer": "http://zt.wps.cn/2018/clock_in/api/answer",
    "clock_in": "http://zt.wps.cn/2018/clock_in/api/clock_in",
    "invite": "http://zt.wps.cn/2018/clock_in/api/invite",
    "base_info": "https://zt.wps.cn/2019/docer_sign_ppt/api/base_info",
    "docer_checkin": "https://zt.wps.cn/2019/docer_sign_ppt/api/checkin",
}

HEADERS_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}


def make_headers(sid):
    """构建请求头"""
    h = HEADERS_TEMPLATE.copy()
    h["sid"] = sid
    return h


def get_session():
    """创建持久化 Session"""
    s = requests.Session()
    s.headers.update(HEADERS_TEMPLATE)
    return s


# ============================================================
# 签到相关
# ============================================================

def sign_up(sid):
    """报名参加打卡活动"""
    try:
        resp = requests.get(
            API["sign_up"],
            params={"member": "wps"},
            headers=make_headers(sid),
            timeout=15,
        )
        data = resp.json()
        log(f"[报名] {data}")
        return data.get("result") == "ok"
    except Exception as e:
        log(f"[报名] 失败: {e}", "error")
        return False


def get_question(sid):
    """获取签到问题"""
    try:
        resp = requests.get(
            API["get_question"],
            params={"member": "wps"},
            headers=make_headers(sid),
            timeout=15,
        )
        data = resp.json()
        log(f"[问题] {data}")

        if data.get("result") != "ok":
            return None

        question_data = data.get("data", {})
        # 如果是多选题，递归获取单选题
        if question_data.get("multi_select") == 1:
            log("[问题] 遇到多选题，重新获取...")
            time.sleep(1)
            return get_question(sid)

        return question_data
    except Exception as e:
        log(f"[获取问题] 失败: {e}", "error")
        return None


def answer_question(sid, question):
    """尝试回答签到问题"""
    title = question.get("title", "")
    options = question.get("options", [])
    log(f"[答题] 题目: {title}")
    log(f"[答题] 选项: {options}")

    # 逐个尝试答案（1-4），直到答对
    for answer_num in range(1, len(options) + 1):
        try:
            resp = requests.post(
                API["answer"],
                params={"member": "wps"},
                headers=make_headers(sid),
                data={"answer": str(answer_num)},
                timeout=15,
            )
            data = resp.json()
            log(f"[答题] 尝试选项 {answer_num}: {data}")

            if data.get("msg") != "wrong answer":
                log(f"[答题] 答案正确: 选项 {answer_num}")
                return True
        except Exception as e:
            log(f"[答题] 选项 {answer_num} 请求失败: {e}", "error")

        time.sleep(0.5)

    log("[答题] 所有选项都失败了", "error")
    return False


def do_clock_in(sid):
    """执行签到"""
    try:
        resp = requests.get(
            API["clock_in"],
            params={"member": "wps"},
            headers=make_headers(sid),
            timeout=15,
        )
        data = resp.json()
        log(f"[签到] {data}")
        return data.get("result") == "ok"
    except Exception as e:
        log(f"[签到] 失败: {e}", "error")
        return False


def wps_clock_in(sid):
    """完整签到流程: 报名 -> 答题 -> 签到"""
    log("=" * 50)
    log("开始 WPS 签到流程...")

    # 1. 报名
    log("步骤 1/3: 报名活动")
    if not sign_up(sid):
        # 可能已经报过名了，继续尝试
        log("[报名] 可能已报名，继续...")

    time.sleep(1)

    # 2. 获取问题并答题
    log("步骤 2/3: 获取问题并答题")
    question = get_question(sid)
    if question:
        time.sleep(1)
        answer_question(sid, question)
    else:
        log("[问题] 未获取到问题，可能无需答题", "warn")

    time.sleep(1)

    # 3. 签到
    log("步骤 3/3: 执行签到")
    result = do_clock_in(sid)

    if result:
        log("签到成功！", "success")
    else:
        log("签到可能失败，请检查 sid 是否有效或手动签到", "warn")

    return result


# ============================================================
# 稻壳签到
# ============================================================

def docer_checkin(sid):
    """稻壳签到（7:00-14:00 无需答题）"""
    log("-" * 30)
    log("开始稻壳签到...")

    try:
        # 获取基础信息
        resp = requests.get(
            API["base_info"],
            headers=make_headers(sid),
            timeout=15,
        )
        data = resp.json()
        log(f"[稻壳-信息] {data}")

        time.sleep(1)

        # 签到
        resp = requests.post(
            API["docer_checkin"],
            headers=make_headers(sid),
            json={"is_question": 0},
            timeout=15,
        )
        data = resp.json()
        log(f"[稻壳-签到] {data}")

        if data.get("result") == "ok":
            log("稻壳签到成功！", "success")
            return True
        else:
            log("稻壳签到失败", "warn")
            return False
    except Exception as e:
        log(f"[稻壳签到] 失败: {e}", "error")
        return False


# ============================================================
# 邀请相关
# ============================================================

def invite_user(inviter_sid, invite_userid):
    """邀请单个用户"""
    try:
        payload = {"invite_userid": str(invite_userid)}
        resp = requests.post(
            API["invite"],
            headers=make_headers(inviter_sid),
            json=payload,
            timeout=15,
        )
        data = resp.json()
        return data
    except Exception as e:
        return {"error": str(e)}


def wps_invite(sid, invite_userid, invite_sids):
    """批量邀请好友"""
    log("=" * 50)
    log("开始 WPS 邀请流程...")
    log(f"主账号 userid: {invite_userid}")
    log(f"待邀请小号数量: {len(invite_sids)}")

    success_count = 0
    fail_count = 0

    # 每日最多邀请 10 人
    max_invite = min(10, len(invite_sids))

    for i, target_sid in enumerate(invite_sids[:max_invite]):
        log(f"邀请 {i + 1}/{max_invite}: sid={target_sid[:20]}...")

        result = invite_user(target_sid, invite_userid)
        log(f"  结果: {result}")

        if result.get("result") == "ok":
            success_count += 1
        else:
            fail_count += 1

        # 间隔 2-3 秒，避免被过滤
        if i < max_invite - 1:
            delay = random.uniform(2, 3)
            time.sleep(delay)

    log(f"邀请完成: 成功 {success_count}, 失败 {fail_count}")
    return success_count, fail_count


# ============================================================
# 通知推送
# ============================================================

def send_notification(title, content):
    """发送通知到配置的渠道"""
    results = []

    # Server酱 Turbo
    if CONFIG["server_chan_key"]:
        try:
            url = f"https://sctapi.ftqq.com/{CONFIG['server_chan_key']}.send"
            resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
            results.append(f"Server酱: {resp.status_code}")
        except Exception as e:
            results.append(f"Server酱失败: {e}")

    # 企业微信
    if CONFIG["wecom_webhook"]:
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": f"## {title}\n{content}"},
            }
            resp = requests.post(CONFIG["wecom_webhook"], json=payload, timeout=10)
            results.append(f"企业微信: {resp.status_code}")
        except Exception as e:
            results.append(f"企业微信失败: {e}")

    # 钉钉
    if CONFIG["dingtalk_webhook"]:
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": title, "text": f"## {title}\n{content}"},
            }
            resp = requests.post(CONFIG["dingtalk_webhook"], json=payload, timeout=10)
            results.append(f"钉钉: {resp.status_code}")
        except Exception as e:
            results.append(f"钉钉失败: {e}")

    if results:
        log(f"通知推送: {', '.join(results)}")
    else:
        log("未配置通知渠道")


# ============================================================
# 工具函数
# ============================================================

def log(msg, level="info"):
    """带时间戳的日志输出"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"info": "ℹ", "success": "✅", "error": "❌", "warn": "⚠️"}.get(level, "ℹ")
    print(f"[{now}] {prefix} {msg}")

    # 同时收集日志用于通知
    global _log_lines
    if "_log_lines" not in globals():
        _log_lines = []
    _log_lines.append(f"[{now}] {msg}")


def get_log_text():
    """获取所有日志文本"""
    return "\n".join(globals().get("_log_lines", []))


# ============================================================
# 主流程
# ============================================================

def main():
    global _log_lines
    _log_lines = []

    log("=" * 50)
    log("WPS 自动签到脚本启动")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 50)

    sid = CONFIG["wps_sid"]
    invite_userid = CONFIG["invite_userid"]

    if not sid or sid == "YOUR_WPS_SID_HERE":
        log("请先配置 WPS_SID！", "error")
        log("获取方式: 登录 https://zt.wps.cn/2018/clock_in/ 后在 Cookie 中查找 wps_sid")
        return

    results = {
        "clock_in": False,
        "docer_checkin": False,
        "invite_success": 0,
        "invite_fail": 0,
    }

    # 1. 签到
    results["clock_in"] = wps_clock_in(sid)
    time.sleep(2)

    # 2. 稻壳签到
    results["docer_checkin"] = docer_checkin(sid)
    time.sleep(2)

    # 3. 邀请好友
    if invite_userid and invite_userid != 0:
        success, fail = wps_invite(sid, invite_userid, CONFIG["invite_sids"])
        results["invite_success"] = success
        results["invite_fail"] = fail
    else:
        log("未配置 invite_userid，跳过邀请", "warn")

    # 4. 汇总
    log("=" * 50)
    log("执行结果汇总:")
    log(f"  签到: {'成功' if results['clock_in'] else '失败/跳过'}")
    log(f"  稻壳签到: {'成功' if results['docer_checkin'] else '失败/跳过'}")
    log(f"  邀请: 成功 {results['invite_success']}, 失败 {results['invite_fail']}")
    log("=" * 50)

    # 5. 发送通知
    title = (
        f"WPS 签到 {'成功' if results['clock_in'] else '请检查'}"
        f" | 邀请 +{results['invite_success']}"
    )
    content = "\n".join([
        f"签到: {'✅ 成功' if results['clock_in'] else '❌ 失败'}",
        f"稻壳签到: {'✅ 成功' if results['docer_checkin'] else '❌ 失败'}",
        f"邀请: 成功 {results['invite_success']}, 失败 {results['invite_fail']}",
        "",
        "---",
        get_log_text(),
    ])
    send_notification(title, content)


if __name__ == "__main__":
    main()