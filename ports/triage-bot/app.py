"""Triage Bot for Business Users — Slack App."""

import json
import logging
import os
import re
import threading

import yaml
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from claude_bridge import run_claude, pull_project, get_project_path
from slack_blocks import questions_to_blocks, result_to_blocks, triage_action_buttons
from ul_filter import apply_ul_filter
import state
import jira_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("triage-bot")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

ATDD_HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))
TRIAGE_CHANNEL_ID = os.environ.get("TRIAGE_CHANNEL_ID", "")
PM_CHANNEL_ID = os.environ.get("PM_CHANNEL_ID", "")
RD_LEAD_SLACK_USER_ID = os.environ.get("RD_LEAD_SLACK_USER_ID", "")

# Thread locks
conv_locks = {}


def _get_lock(thread_ts: str) -> threading.Lock:
    if thread_ts not in conv_locks:
        conv_locks[thread_ts] = threading.Lock()
    return conv_locks[thread_ts]


def _load_projects() -> list[str]:
    config_path = os.path.join(ATDD_HUB_PATH, ".claude/config/projects.yml")
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return list(data.get("projects", {}).keys())
    except Exception as e:
        logger.error(f"Failed to load projects: {e}")
        return ["core_web"]


def _strip_mention(text: str) -> str:
    return re.sub(r"<@[\w]+>\s*", "", text).strip()


def _send_long_message(channel: str, thread_ts: str, text: str):
    """Send a long message, splitting into chunks if needed."""
    MAX_LEN = 3000
    chunks = [text[i:i+MAX_LEN] for i in range(0, len(text), MAX_LEN)]
    for chunk in chunks:
        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, text=chunk,
        )


def _process_claude(prompt: str, thread_ts: str, channel: str,
                    session_id: str | None = None):
    """Run Claude CLI and send result to Slack."""
    conv = state.get(thread_ts) or {}

    try:
        thinking_msg = app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=":hourglass_flowing_sand: 處理中...",
        )

        result = run_claude(prompt, session_id=session_id)

        try:
            app.client.chat_delete(channel=channel, ts=thinking_msg["ts"])
        except Exception:
            pass

        conv["session_id"] = result["session_id"]

        if result["is_error"]:
            conv["status"] = "waiting_answer"
            state.set(thread_ts, conv)
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":x: 處理出錯: {result['result'][:500]}\n\n請重新回覆本訊息重試。",
            )
            return

        text = result["result"] or ""

        # Apply UL filter: replace English code names with Chinese business terms
        project = conv.get("project", "")
        if project and text:
            text = apply_ul_filter(text, project)

        if text:
            _send_long_message(channel, thread_ts, text)

        if result["questions"]:
            conv["status"] = "waiting_answer"
            state.set(thread_ts, conv)
            q_blocks = questions_to_blocks(result["questions"])
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=q_blocks, text="請回答上面的問題。",
            )
            return

        # Triage interview complete: show summary and action buttons
        conv["status"] = "waiting_confirmation"
        state.set(thread_ts, conv)
        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            blocks=triage_action_buttons(),
            text="訪談完成，請確認上面的信息。",
        )

    except Exception as e:
        logger.exception(f"Error in _process_claude: {e}")
        conv["status"] = "waiting_answer"
        state.set(thread_ts, conv)
        try:
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":warning: 內部錯誤: {str(e)[:300]}\n\n請重新回覆重試。",
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────
# Slash Command: /report
# ─────────────────────────────────────────────────


@app.command("/report")
def handle_report_command(ack, body, client):
    """Open modal for reporting an issue."""
    ack()
    projects = _load_projects()
    project_options = [
        {"text": {"type": "plain_text", "text": p}, "value": p}
        for p in projects
    ]

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "report_submit",
            "title": {"type": "plain_text", "text": "回報問題"},
            "submit": {"type": "plain_text", "text": "開始分析"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "project_block",
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "選擇系統"},
                        "options": project_options,
                        "action_id": "project_select",
                    },
                    "label": {"type": "plain_text", "text": "系統"},
                },
                {
                    "type": "input",
                    "block_id": "description_block",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "詳細描述遇到的問題..."},
                        "action_id": "description_input",
                    },
                    "label": {"type": "plain_text", "text": "問題描述"},
                },
            ],
        },
    )


@app.view("report_submit")
def handle_report_submit(ack, body, client):
    """Handle modal submission and start triage interview."""
    ack()
    user = body["user"]["id"]
    values = body["view"]["state"]["values"]
    project = values["project_block"]["project_select"]["selected_option"]["value"]
    description = values["description_block"]["description_input"]["value"]

    channel = TRIAGE_CHANNEL_ID
    if not channel:
        logger.error("TRIAGE_CHANNEL_ID not configured")
        return

    msg = client.chat_postMessage(
        channel=channel,
        text=f":mag: *業務問題回報*\n*系統*: `{project}`\n*回報人*: <@{user}>\n\n_開始訪談中..._",
    )
    thread_ts = msg["ts"]

    state.set(thread_ts, {
        "user": user,
        "project": project,
        "description": description,
        "session_id": None,
        "status": "running",
        "phase": "interview",
    })

    logger.info(f"Triage started by {user}: project={project}")

    # Load triage agent prompt
    agent_path = os.path.join(ATDD_HUB_PATH, "ports/triage-bot/profiles/triage-agent.md")
    agent_def = ""
    try:
        with open(agent_path) as f:
            agent_def = f.read()
    except FileNotFoundError:
        logger.warning(f"Triage agent not found: {agent_path}")

    project_path = get_project_path(project) or ""

    prompt = f"""{agent_def}

---

## 目前任務

**系統**: {project}
**代碼庫路徑**: {project_path}

**業務用戶的初始描述**:
{description}

---

請開始 **Round 1 訪談** — 提出第一個問題（選項按鈕方式）。
    """

    threading.Thread(
        target=_process_claude,
        args=(prompt, thread_ts, channel),
        daemon=True,
    ).start()


# ─────────────────────────────────────────────────
# Slack Events: Button clicks and thread replies
# ─────────────────────────────────────────────────


@app.action("q_option_.*")
def handle_question_option(ack, body, client):
    """Handle question option selection."""
    ack()

    thread_ts = body["container"]["thread_ts"]
    channel = body["channel"]["id"]
    conv = state.get(thread_ts) or {}

    if conv.get("status") != "waiting_answer":
        return

    # Extract option number from action_id
    action_id = body["actions"][0]["action_id"]
    match = re.search(r"q_option_(\d+)", action_id)
    if not match:
        return

    option_index = int(match.group(1))
    selected_value = body["actions"][0].get("value", "")

    logger.info(f"Option selected: {selected_value}")

    # Send confirmation of choice
    app.client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"已選擇: *{selected_value}*",
    )

    # Resume Claude with user's choice
    conv["status"] = "running"
    state.set(thread_ts, conv)

    prompt = f"用戶選擇了: {selected_value}\n\n請繼續進行下一步訪談或顯示最終摘要。"

    threading.Thread(
        target=_process_claude,
        args=(prompt, thread_ts, channel, conv.get("session_id")),
        daemon=True,
    ).start()


@app.action("confirm_triage")
def handle_confirm_triage(ack, body, client):
    """業務確認後，執行 Jira 立單。"""
    ack()

    thread_ts = body["container"]["thread_ts"]
    channel = body["channel"]["id"]
    conv = state.get(thread_ts) or {}

    if conv.get("status") != "waiting_confirmation":
        logger.warning(f"Unexpected status: {conv.get('status')}")
        return

    logger.info(f"Triage confirmed, starting Jira creation: {thread_ts}")

    # 進入 Phase 2: 代碼分析 + Jira 立單
    conv["phase"] = "triage_analysis"
    conv["status"] = "analyzing"
    state.set(thread_ts, conv)

    # Show processing message
    app.client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":gear: 正在分析代碼和建立 Jira 票...",
    )

    threading.Thread(
        target=_run_triage_and_create,
        args=(thread_ts, channel, conv),
        daemon=True,
    ).start()


@app.action("continue_triage")
def handle_continue_triage(ack, body, client):
    """業務選擇補充說明，回到訪談。"""
    ack()

    thread_ts = body["container"]["thread_ts"]
    channel = body["channel"]["id"]
    conv = state.get(thread_ts) or {}

    app.client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":pencil2: 請補充說明或回答更多問題...",
    )

    conv["status"] = "waiting_answer"
    conv["phase"] = "interview"
    state.set(thread_ts, conv)

    # Resume Claude for follow-up
    prompt = "用戶要補充說明。請詢問相關跟進問題或要求詳細說明。"

    threading.Thread(
        target=_process_claude,
        args=(prompt, thread_ts, channel, conv.get("session_id")),
        daemon=True,
    ).start()


@app.action("cancel_triage")
def handle_cancel_triage(ack, body, client):
    """業務取消。"""
    ack()

    thread_ts = body["container"]["thread_ts"]
    channel = body["channel"]["id"]

    app.client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":no_entry_sign: 已取消。如需回報問題，請使用 `/report` 命令。",
    )

    state.delete(thread_ts)


@app.event("app_mention")
def handle_app_mention(event, client):
    """Respond to mentions (fallback)."""
    thread_ts = event.get("thread_ts") or event["ts"]
    channel = event["channel"]

    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text="你好！請使用 `/report` 命令回報問題。",
    )


# ─────────────────────────────────────────────────
# Phase 2: Triage Analysis + Jira Creation
# ─────────────────────────────────────────────────


def _run_triage_and_create(thread_ts: str, channel: str, conv: dict):
    """Phase 2: 代碼分析 + Jira 立單。"""
    session_id = conv.get("session_id")
    project = conv.get("project", "")

    # Generate triage analysis prompt
    agent_path = os.path.join(ATDD_HUB_PATH, "ports/triage-bot/profiles/triage-agent.md")
    agent_def = ""
    try:
        with open(agent_path) as f:
            agent_def = f.read()
    except FileNotFoundError:
        logger.warning(f"Triage agent not found: {agent_path}")

    prompt = f"""{agent_def}

---

## Phase 2: 代碼分析 + Jira 準備

訪談已完成。現在你的任務是：

1. **整理訪談信息** — 從對話歷史中提取完整的問題描述、影響範圍、優先級判斷
2. **輸出結構化結果** — 按照下方格式輸出 TRIAGE_RESULT JSON

請以以下格式輸出最終結果，app.py 會自動解析建立 Jira 票：

```
TRIAGE_RESULT:
{{
  "summary": "一行摘要",
  "issue_type": "Bug | Enhancement",
  "priority": "P0 | P1 | P2 | P3",
  "priority_reason": "優先級理由",
  "affected_domain": "domain_name",
  "interview_summary": "完整訪談摘要",
  "steps_to_reproduce": ["步驟1", "步驟2"],
  "expected": "預期行為",
  "actual": "實際現象",
  "impact": "受影響範圍描述",
  "workaround": "暫時方案或空"
}}
```

開始輸出 TRIAGE_RESULT。
    """

    try:
        result = run_claude(prompt, session_id=session_id)

        if result["is_error"]:
            app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f":x: 分析失敗: {result['result'][:500]}",
            )
            conv["status"] = "waiting_answer"
            state.set(thread_ts, conv)
            return

        text = result["result"]

        # Parse TRIAGE_RESULT JSON
        match = re.search(r"TRIAGE_RESULT:\s*\{(.+?)\}", text, re.DOTALL)
        if not match:
            logger.error(f"TRIAGE_RESULT not found in: {text[:500]}")
            app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=":x: 無法解析分析結果，請稍後重試。",
            )
            conv["status"] = "waiting_answer"
            state.set(thread_ts, conv)
            return

        json_str = "{" + match.group(1) + "}"
        triage_data = json.loads(json_str)

        # Create Jira issue
        priority_map = {
            "P0": "Highest",
            "P1": "High",
            "P2": "Medium",
            "P3": "Low",
        }

        sections = {
            "problem": triage_data.get("interview_summary", conv.get("description", "")),
            "steps": triage_data.get("steps_to_reproduce", []),
            "expected": triage_data.get("expected", ""),
            "actual": triage_data.get("actual", ""),
            "impact": triage_data.get("impact", ""),
            "analysis": f"**優先級**: {triage_data.get('priority')} — {triage_data.get('priority_reason', '')}\n\n**受影響領域**: {triage_data.get('affected_domain', '')}",
        }

        issue = jira_client.create_issue(
            summary=triage_data.get("summary", ""),
            sections=sections,
            priority=priority_map.get(triage_data.get("priority", "P2"), "Medium"),
            labels=[triage_data.get("affected_domain", "")],
            project_key=None,
            issue_type=None,
        )

        # Notify business user
        app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":white_check_mark: *Jira 票已建立*\n"
                 f"*票號*: <{issue['url']}|{issue['key']}>\n"
                 f"*優先級*: {triage_data.get('priority', 'P2')}\n"
                 f"*受影響領域*: {triage_data.get('affected_domain', 'N/A')}\n\n"
                 f"PM 將在 24 小時內 review。謝謝你的回報！",
        )

        # Notify PM channel
        _notify_pm(channel, thread_ts, triage_data, issue)

        # Handle P0 urgency
        if triage_data.get("priority") == "P0":
            _notify_p0_urgency(thread_ts, issue)

        # Clean up
        state.delete(thread_ts)
        conv["status"] = "completed"
        state.set(thread_ts, conv)

        logger.info(f"Jira issue created: {issue['key']}")

    except Exception as e:
        logger.exception(f"Error in _run_triage_and_create: {e}")
        app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f":warning: 立單失敗: {str(e)[:300]}",
        )
        conv["status"] = "error"
        state.set(thread_ts, conv)


def _notify_pm(channel: str, thread_ts: str, triage_data: dict, issue: dict):
    """Notify PM channel about new triage ticket."""
    if not PM_CHANNEL_ID:
        logger.warning("PM_CHANNEL_ID not configured")
        return

    message = (
        f":bell: *新 Triage 票 — 需要 Review*\n"
        f"*票號*: <{issue['url']}|{issue['key']}>\n"
        f"*摘要*: {triage_data.get('summary', '')}\n"
        f"*優先級*: {triage_data.get('priority', 'P2')}\n"
        f"*受影響範圍*: {triage_data.get('impact', '')}\n"
        f"*優先級原因*: {triage_data.get('priority_reason', '')}"
    )

    try:
        app.client.chat_postMessage(channel=PM_CHANNEL_ID, text=message)
    except Exception as e:
        logger.error(f"Failed to notify PM: {e}")


def _notify_p0_urgency(thread_ts: str, issue: dict):
    """Send urgent P0 notification to PM and RD lead."""
    if not PM_CHANNEL_ID or not RD_LEAD_SLACK_USER_ID:
        return

    try:
        # DM PM
        app.client.chat_postMessage(
            channel=PM_CHANNEL_ID,
            text=f":rotating_light: *P0 緊急* — <{issue['url']}|{issue['key']}>\n"
                 f"請立即檢查並分配給 RD Team。",
        )

        # DM RD Lead
        app.client.chat_postMessage(
            channel=RD_LEAD_SLACK_USER_ID,
            text=f":rotating_light: *P0 緊急問題* — <{issue['url']}|{issue['key']}>\n"
                 f"業務已回報，PM 正在確認。",
        )
    except Exception as e:
        logger.error(f"Failed to send P0 urgent notification: {e}")


@app.event("app_home_opened")
def handle_app_home(event, client):
    """Render app home tab."""
    user = event["user"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":mag: Triage Bot"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "歡迎使用業務問題回報系統。"},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "報告問題"},
                    "action_id": "open_report_modal",
                    "style": "primary",
                },
            ],
        },
    ]

    try:
        client.views_publish(user_id=user, view={"type": "home", "blocks": blocks})
    except Exception as e:
        logger.error(f"Failed to publish app home: {e}")


@app.action("open_report_modal")
def handle_open_report_modal(ack, body, client):
    """Open /report modal from app home."""
    ack()
    handle_report_command(lambda: None, body, client)


@app.error
def custom_error_handler(error, body):
    logger.error(f"Error: {error}")
    logger.error(f"Request body: {body}")


def main():
    """Start the bot."""
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("⚡ Triage Bot started")
    handler.start()


if __name__ == "__main__":
    main()
