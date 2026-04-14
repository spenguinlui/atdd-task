"""ATDD Server — Slack Bot (Phase 4 MVP + Triage feature)."""

import json
import logging
import os
import re
import threading

import yaml
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import re as _re
from claude_bridge import run_claude, pull_project, get_project_path
from slack_blocks import questions_to_blocks, result_to_blocks, action_buttons, triage_action_buttons
from ul_filter import apply_ul_filter
from git_sync import sync as git_sync
import api_client
import state
import jira_client


def _extract_confidence(text: str) -> float | None:
    """Extract confidence percentage from Claude's response."""
    patterns = [
        r'需求信心度[：:]\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
        r'信心度[達約為：:]\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
        r'信心度\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
    ]
    for pattern in patterns:
        match = _re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("atdd-bot")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

ATDD_HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))

# Triage feature configuration
TRIAGE_CHANNEL_ID = os.environ.get("TRIAGE_CHANNEL_ID", "")
PM_CHANNEL_ID = os.environ.get("PM_CHANNEL_ID", "")
RD_LEAD_SLACK_USER_ID = os.environ.get("RD_LEAD_SLACK_USER_ID", "")

# Thread locks (in-memory, only needed during runtime)
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
            text=":hourglass_flowing_sand: Processing...",
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
                text=f":x: Error: {result['result'][:500]}\n\nRetry by replying in this thread.",
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
                blocks=q_blocks, text="Please answer.",
            )
            return

        # Show action buttons
        # For triage flow: show triage-specific buttons; for feature/knowledge: show regular buttons
        conv["status"] = "waiting_confirmation" if conv.get("phase") == "interview" else "waiting_answer"
        state.set(thread_ts, conv)

        if conv.get("phase") == "interview":
            # Triage flow: show confirm/cancel buttons
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=triage_action_buttons(),
                text="訪談完成，請確認上面的信息。",
            )
        else:
            # Feature/Knowledge flow: show regular buttons
            confidence = _extract_confidence(text)
            show_confirm = confidence is not None and confidence >= 95.0

            if confidence is not None:
                conv["last_confidence"] = confidence
                logger.info(f"Confidence: {confidence}%, show_confirm={show_confirm}")

            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                blocks=action_buttons(show_confirm=show_confirm),
                text="Choose an action or reply to continue.",
            )

        # Auto sync any file changes to GitHub
        sync_err = git_sync(f"bot: {conv.get('type', 'feature')} — {conv.get('project', '?')}")
        if sync_err:
            logger.warning(f"Git sync failed: {sync_err}")

    except Exception as e:
        logger.exception(f"Error in _process_claude: {e}")
        conv["status"] = "waiting_answer"
        state.set(thread_ts, conv)
        try:
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":warning: Internal error: {str(e)[:300]}\n\nPlease retry by replying.",
            )
        except Exception:
            pass


# --- Slash Command: /feature ---


@app.command("/feature")
def handle_feature_command(ack, body, client):
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
            "callback_id": "feature_submit",
            "title": {"type": "plain_text", "text": "New Feature"},
            "submit": {"type": "plain_text", "text": "Start"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "project_block",
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select project"},
                        "options": project_options,
                        "action_id": "project_select",
                    },
                    "label": {"type": "plain_text", "text": "Project"},
                },
                {
                    "type": "input",
                    "block_id": "description_block",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Describe the feature or requirement..."},
                        "action_id": "description_input",
                    },
                    "label": {"type": "plain_text", "text": "Description"},
                },
            ],
        },
    )


@app.view("feature_submit")
def handle_feature_submit(ack, body, client):
    ack()
    user = body["user"]["id"]
    values = body["view"]["state"]["values"]
    project = values["project_block"]["project_select"]["selected_option"]["value"]
    description = values["description_block"]["description_input"]["value"]

    channel = os.environ.get("SLACK_CHANNEL_ID", "")
    if not channel:
        channel = body.get("view", {}).get("private_metadata", "")
    if not channel:
        logger.error("No channel ID configured. Set SLACK_CHANNEL_ID in .env")
        return

    msg = client.chat_postMessage(
        channel=channel,
        text=f":sparkles: *New Feature Request*\n*Project:* `{project}`\n*From:* <@{user}>\n\n{description}",
    )
    thread_ts = msg["ts"]

    state.set(thread_ts, {
        "user": user,
        "project": project,
        "session_id": None,
        "status": "running",
    })

    logger.info(f"Feature started by {user}: project={project}, desc={description[:60]}")

    # Load PM specist agent definition
    specist_path = os.path.join(ATDD_HUB_PATH, "profiles/pm/agents/specist-pm.md")
    specist_def = ""
    try:
        with open(specist_path) as f:
            specist_def = f.read()
    except FileNotFoundError:
        logger.warning(f"PM specist not found at {specist_path}, using inline prompt")

    if specist_def:
        prompt = (
            f"{specist_def}\n\n"
            f"---\n\n"
            f"## Current Task\n\n"
            f"Project: {project}\n"
            f"PM's request: {description}\n\n"
            f"Start with Phase 1 (Domain identification)."
        )
    else:
        prompt = (
            f"You are a PM-facing Specification Expert.\n"
            f"Project: {project}\n"
            f"Description: {description}\n\n"
            f"Read .claude/config/confidence/requirement.yml for the confidence assessment framework.\n"
            f"Follow the 7-dimension scoring strictly. Show the full score table after each round.\n"
            f"Do NOT ask about git branch or Jira.\n"
            f"Do NOT auto-complete — PM decides when BA is done.\n"
        )

    threading.Thread(
        target=_process_claude,
        args=(prompt, thread_ts, channel),
        daemon=True,
    ).start()


# --- Slash Command: /knowledge ---


@app.command("/knowledge")
def handle_knowledge_command(ack, body, client):
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
            "callback_id": "knowledge_submit",
            "title": {"type": "plain_text", "text": "Knowledge Discussion"},
            "submit": {"type": "plain_text", "text": "Start"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "project_block",
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Select project"},
                        "options": project_options,
                        "action_id": "project_select",
                    },
                    "label": {"type": "plain_text", "text": "Project"},
                },
                {
                    "type": "input",
                    "block_id": "topic_block",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What topic do you want to discuss?"},
                        "action_id": "topic_input",
                    },
                    "label": {"type": "plain_text", "text": "Topic"},
                },
            ],
        },
    )


@app.view("knowledge_submit")
def handle_knowledge_submit(ack, body, client):
    ack()
    user = body["user"]["id"]
    values = body["view"]["state"]["values"]
    project = values["project_block"]["project_select"]["selected_option"]["value"]
    topic = values["topic_block"]["topic_input"]["value"]

    channel = os.environ.get("SLACK_CHANNEL_ID", "")
    if not channel:
        channel = body.get("view", {}).get("private_metadata", "")
    if not channel:
        logger.error("No channel ID configured. Set SLACK_CHANNEL_ID in .env")
        return

    msg = client.chat_postMessage(
        channel=channel,
        text=f":books: *Knowledge Discussion*\n*Project:* `{project}`\n*From:* <@{user}>\n\n{topic}",
    )
    thread_ts = msg["ts"]

    state.set(thread_ts, {
        "user": user,
        "project": project,
        "type": "knowledge",
        "session_id": None,
        "status": "running",
    })

    logger.info(f"Knowledge started by {user}: project={project}, topic={topic[:60]}")

    from claude_bridge import get_project_path
    project_path = get_project_path(project) or ""

    prompt = (
        f"You are a Knowledge Curator (curator agent). "
        f"The PM wants to discuss and enrich domain knowledge.\n\n"
        f"Project: {project}\n"
        f"Project codebase path: {project_path}\n"
        f"Topic: {topic}\n\n"
        f"Your workflow:\n"
        f"1. Read domains/{project}/domain-map.md to identify the relevant domain\n"
        f"2. Read domains/{project}/ul.md for terminology\n"
        f"3. Read domains/{project}/business-rules.md for existing rules\n"
        f"4. Read domains/{project}/strategic/{{Domain}}.md for domain knowledge\n"
        f"5. Read domains/{project}/tactical/{{Domain}}.md if exists\n"
        f"6. If project codebase is available, use Glob/Grep/Read to investigate code\n"
        f"7. After reading code, re-read ul.md and knowledge files to compare\n"
        f"8. Present audit report with clear separation:\n"
        f"   *:blue_book: 知識庫記載* — what knowledge files say\n"
        f"   *:computer: 程式碼現況* — what code actually does (in business terms)\n"
        f"   *:warning: 落差* — differences between knowledge and code\n"
        f"   *:question: 知識缺口* — gaps that need PM input\n"
        f"9. Ask PM clarification questions to fill knowledge gaps (one topic at a time)\n"
        f"10. After enough Q&A (3+ rounds), propose knowledge updates\n"
        f"11. Show the full proposed text for each file to be updated\n"
        f"12. Wait for PM confirmation before writing\n\n"
        f"Rules:\n"
        f"- Every knowledge item must have a source tag: [doc], [code], [user], [derived]\n"
        f"- [derived] must show reasoning chain\n"
        f"- Never use LLM general knowledge to fill gaps\n"
        f"- Mark uncertain items as [unconfirmed]\n"
        f"- Only modify files under domains/{project}/\n"
        f"- All writing needs PM's explicit confirmation\n\n"
        f"Language rules (CRITICAL — strictly enforced):\n"
        f"- BEFORE writing any report or reply to PM, you MUST:\n"
        f"  1. Read domains/{project}/ul.md\n"
        f"  2. For EVERY code concept you plan to mention, search ul.md for its Chinese name\n"
        f"  3. Replace the English code name with the Chinese term\n"
        f"- Example: if ul.md defines 'Entry' as '電費項目', you MUST write '電費項目' not 'Entry'\n"
        f"- Example: if ul.md defines 'ActualEntry' as '實際電費項目', write '實際電費項目' not 'ActualEntry'\n"
        f"- If a code concept has NO matching ul.md entry: '程式中有一個概念 `ClassName`，知識庫尚未定義對應名稱'\n"
        f"- NEVER use English class names, method names, or column names when a Chinese term exists in ul.md\n"
        f"- This applies to all output: audit reports, questions, proposals, everything\n\n"
        f"Slack format rules:\n"
        f"- Use *bold* not # headers\n"
        f"- Use bullet lists (•) not markdown tables\n"
        f"- No ASCII box drawing (┌──┐)\n"
        f"- No --- dividers\n\n"
        f"Start with step 1."
    )

    threading.Thread(
        target=_process_claude,
        args=(prompt, thread_ts, channel),
        daemon=True,
    ).start()


# --- Slash Command: /report (Triage feature) ---


@app.command("/report")
def handle_report_command(ack, body, client):
    """業務用戶問題回報命令。"""
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
    """業務提交問題報告，開始 Triage 訪談。"""
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

    # Load triage agent
    agent_path = os.path.join(ATDD_HUB_PATH, "profiles/business/agents/triage-agent.md")
    agent_def = ""
    try:
        with open(agent_path) as f:
            agent_def = f.read()
    except FileNotFoundError:
        logger.warning(f"Triage agent not found: {agent_path}")

    prompt = f"""{agent_def}

---

## 目前任務

**系統**: {project}

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


# --- Triage Action Handlers ---


@app.action("confirm_triage")
def handle_confirm_triage(ack, body, client):
    """業務確認後，執行 Jira 立單。"""
    ack()

    thread_ts = body["container"]["thread_ts"]
    channel = body["channel"]["id"]
    conv = state.get(thread_ts) or {}

    if conv.get("status") != "waiting_confirmation":
        return

    logger.info(f"Triage confirmed, starting Jira creation: {thread_ts}")

    # Phase 2: 代碼分析 + Jira 立單
    conv["phase"] = "triage_analysis"
    conv["status"] = "analyzing"
    state.set(thread_ts, conv)

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
    """業務補充說明。"""
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


def _run_triage_and_create(thread_ts: str, channel: str, conv: dict):
    """Phase 2: 代碼分析 + Jira 立單。"""
    session_id = conv.get("session_id")
    project = conv.get("project", "")

    # 生成 triage 分析 prompt
    agent_path = os.path.join(ATDD_HUB_PATH, "profiles/business/agents/triage-agent.md")
    agent_def = ""
    try:
        with open(agent_path) as f:
            agent_def = f.read()
    except FileNotFoundError:
        logger.warning(f"Triage agent not found: {agent_path}")

    prompt = f"""{agent_def}

---

## Phase 2: Jira 準備

訪談已完成。現在請整理訪談信息，輸出結構化結果。

按照 TRIAGE_RESULT 格式輸出最終結果（app.py 會自動解析建立 Jira 票）。

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
            labels=[triage_data.get("affected_domain", "")] if triage_data.get("affected_domain") else None,
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
        if PM_CHANNEL_ID:
            app.client.chat_postMessage(
                channel=PM_CHANNEL_ID,
                text=f":bell: *新 Triage 票 — 需要 Review*\n"
                     f"*票號*: <{issue['url']}|{issue['key']}>\n"
                     f"*摘要*: {triage_data.get('summary', '')}\n"
                     f"*優先級*: {triage_data.get('priority', 'P2')}\n"
                     f"*受影響範圍*: {triage_data.get('impact', '')}\n"
                     f"*優先級原因*: {triage_data.get('priority_reason', '')}",
            )

        # Handle P0 urgency
        if triage_data.get("priority") == "P0" and RD_LEAD_SLACK_USER_ID:
            try:
                app.client.chat_postMessage(
                    channel=RD_LEAD_SLACK_USER_ID,
                    text=f":rotating_light: *P0 緊急問題* — <{issue['url']}|{issue['key']}>\n"
                         f"業務已回報，PM 正在確認。",
                )
            except Exception as e:
                logger.error(f"Failed to DM RD Lead: {e}")

        # Clean up
        state.delete(thread_ts)
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


# --- App Home Tab ---


@app.event("app_home_opened")
def handle_app_home(event, client):
    """Render the App Home tab with action buttons."""
    user = event["user"]

    # Get recent conversations for this user
    recent = []
    for ts in state.keys():
        conv = state.get(ts)
        if conv and conv.get("user") == user:
            project = conv.get("project", "?")
            status = conv.get("status", "?")
            confidence = conv.get("last_confidence")
            conf_str = f" ({confidence:.0f}%)" if confidence else ""
            conv_type = conv.get("type", "feature")
            emoji = ":sparkles:" if conv_type != "knowledge" else ":books:"
            recent.append(f"{emoji} `{project}` — {status}{conf_str}")

    recent_text = "\n".join(recent[-5:]) if recent else "_No recent conversations_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "ATDD Bot"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Welcome! Start a new conversation or check recent activity.",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":rocket: New Feature"},
                    "style": "primary",
                    "action_id": "home_new_feature",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":books: Knowledge Discussion"},
                    "action_id": "home_new_knowledge",
                },
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Recent conversations:*\n{recent_text}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "You can also type `/feature` or `/knowledge` in any channel.",
                }
            ],
        },
    ]

    client.views_publish(
        user_id=user,
        view={"type": "home", "blocks": blocks},
    )


@app.action("home_new_feature")
def handle_home_feature(ack, body, client):
    """Open feature modal from Home tab."""
    ack()
    handle_feature_command(ack=lambda: None, body=body, client=client)


@app.action("home_new_knowledge")
def handle_home_knowledge(ack, body, client):
    """Open knowledge modal from Home tab."""
    ack()
    handle_knowledge_command(ack=lambda: None, body=body, client=client)


# --- Event Handlers ---


@app.event("app_mention")
def handle_mention(event, say):
    user = event["user"]
    text = _strip_mention(event.get("text", ""))
    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]

    if state.get(thread_ts):
        _handle_reply(user, text, channel, thread_ts)
        return

    say(text="Please use `/feature` to start a new requirement.", thread_ts=thread_ts)


@app.event("message")
def handle_message(event, say):
    if event.get("bot_id"):
        return
    thread_ts = event.get("thread_ts")
    if thread_ts and state.get(thread_ts):
        _handle_reply(event["user"], event.get("text", ""), event["channel"], thread_ts)


def _handle_reply(user: str, text: str, channel: str, thread_ts: str):
    conv = state.get(thread_ts)
    if not conv:
        return

    lock = _get_lock(thread_ts)
    if not lock.acquire(blocking=False):
        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=":hourglass: Still processing, please wait...",
        )
        return

    try:
        if conv.get("status") == "running":
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=":hourglass: Still processing, please wait...",
            )
            return

        if conv.get("status") == "completed":
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text="This conversation is complete. Use `/feature` to start a new one.",
            )
            return

        conv["status"] = "running"
        state.set(thread_ts, conv)
        session_id = conv.get("session_id")

        logger.info(f"Resume session {session_id} with reply: {text[:80]}")

        threading.Thread(
            target=_run_and_release,
            args=(text, thread_ts, channel, session_id, lock),
            daemon=True,
        ).start()
        return
    except Exception:
        lock.release()
        raise


def _run_and_release(prompt, thread_ts, channel, session_id, lock):
    try:
        _process_claude(prompt, thread_ts, channel, session_id)
    finally:
        lock.release()


def _sync_task_to_api(task_filepath: str, project: str):
    """Sync a task JSON file to the API (Phase 2 dual-write)."""
    try:
        import json as _json
        with open(task_filepath) as f:
            data = _json.load(f)

        task_type = data.get("type", "feature")
        description = data.get("description", "")
        domain = data.get("domain")
        task_id = data.get("id")

        result = api_client.create_task(
            project=project,
            task_type=task_type,
            description=description,
            domain=domain,
            metadata={"source": "slack-bot", "original_id": task_id},
        )
        if result:
            logger.info(f"Task synced to API: {task_id}")
        else:
            logger.warning(f"Failed to sync task to API: {task_id}")
    except Exception as e:
        # Non-fatal: API sync is best-effort during dual-write phase
        logger.warning(f"API sync error: {e}")


def _confirm_ba_and_upload(prompt, thread_ts, channel, session_id, lock):
    """Run confirm BA, then upload BA file and show Task ID."""
    try:
        _process_claude(prompt, thread_ts, channel, session_id)

        conv = state.get(thread_ts) or {}
        project = conv.get("project", "")

        # Find newly created BA files
        import glob as globmod
        ba_pattern = os.path.join(ATDD_HUB_PATH, f"requirements/{project}/*-ba.md")
        ba_files = sorted(globmod.glob(ba_pattern), key=os.path.getmtime, reverse=True)

        if ba_files:
            ba_path = ba_files[0]  # Most recent
            ba_filename = os.path.basename(ba_path)

            try:
                app.client.files_upload_v2(
                    channel=channel,
                    thread_ts=thread_ts,
                    file=ba_path,
                    filename=ba_filename,
                    title=f"BA Report: {ba_filename}",
                    initial_comment=":page_facing_up: BA Report",
                )
                logger.info(f"Uploaded BA file: {ba_path}")
            except Exception as e:
                logger.error(f"Failed to upload BA: {e}")
                # Fallback: post content as text
                try:
                    with open(ba_path) as f:
                        content = f.read()
                    _send_long_message(channel, thread_ts, f"*BA Report:*\n\n{content}")
                except Exception:
                    pass

        # Extract Task ID and sync to API
        task_id_pattern = os.path.join(ATDD_HUB_PATH, f"tasks/{project}/active/*.json")
        task_files = sorted(globmod.glob(task_id_pattern), key=os.path.getmtime, reverse=True)
        if task_files:
            task_filename = os.path.basename(task_files[0])
            task_id = task_filename.replace(".json", "")
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":label: *Task ID:* `{task_id}`\n\nDev can pick up this task with `git pull`.",
            )

            # Sync task to API (Phase 2: dual-write)
            _sync_task_to_api(task_files[0], project)

        # Git sync — push BA + requirement + task JSON to GitHub
        sync_err = git_sync(f"bot: BA confirmed — {conv.get('project', '?')}")
        if sync_err:
            logger.warning(f"Git sync failed: {sync_err}")
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":warning: Git sync failed: {sync_err}",
            )
        else:
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=":white_check_mark: Changes pushed to GitHub. Dev can `git pull` now.",
            )

        # Mark conversation as completed
        conv["status"] = "completed"
        conv.pop("pending_action", None)
        state.set(thread_ts, conv)

    finally:
        lock.release()


# --- Action Buttons ---


@app.action("analyze_code")
def handle_analyze_code(ack, body):
    ack()
    channel = body["channel"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    user = body["user"]["id"]

    logger.info(f"Analyze Code clicked by {user}, thread_ts={thread_ts}")

    conv = state.get(thread_ts)
    if not conv:
        logger.info(f"No conversation for {thread_ts}")
        return

    lock = _get_lock(thread_ts)
    if not lock.acquire(blocking=False):
        logger.info("Analyze Code: lock not acquired")
        return

    try:
        if conv.get("status") != "waiting_answer":
            logger.info(f"Analyze Code: skipped, status={conv.get('status')}")
            return

        conv["status"] = "running"
        state.set(thread_ts, conv)
        project = conv.get("project", "")

        pull_err = pull_project(project)
        if pull_err:
            app.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=f":warning: git pull failed: {pull_err}\nAnalyzing with current version...",
            )

        project_path = get_project_path(project)
        path_hint = f"The project codebase is at: {project_path}" if project_path else ""

        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=f":mag: Analyzing `{project}` codebase (latest pulled)...",
        )

        session_id = conv.get("session_id")
        prompt = (
            f"Step 1: Re-read domains/{project}/ul.md to refresh the ubiquitous language.\n\n"
            f"Step 2: Summarize what we've established so far from the knowledge files "
            f"and our discussion.\n\n"
            f"Step 3: Analyze the codebase for project '{project}'. {path_hint} "
            f"Focus only on code directly related to our topic — do not read unrelated files.\n\n"
            f"Step 4: Re-read the relevant domain knowledge files:\n"
            f"- domains/{project}/strategic/{{Domain}}.md\n"
            f"- domains/{project}/business-rules.md\n"
            f"Compare code findings against knowledge files.\n\n"
            f"Step 5: Report to PM using this structure (use Slack format, no tables):\n\n"
            f"*:blue_book: 知識庫記載*\n"
            f"• summarize what the knowledge files say about this topic\n\n"
            f"*:computer: 程式碼現況*\n"
            f"• describe what the code actually does\n"
            f"• CRITICAL: for every code concept, search ul.md for its Chinese name and use it\n"
            f"• e.g. if ul.md says Entry='電費項目', write '電費項目' not 'Entry'\n"
            f"• ONLY use `ClassName` if ul.md has no matching entry, and explicitly say '知識庫尚未定義'\n\n"
            f"*:warning: 落差*\n"
            f"• list any differences between knowledge and code (or '無落差' if consistent)\n\n"
            f"*:dart: 對本次需求的影響*\n"
            f"• how this affects our requirement discussion\n\n"
            f"Then continue our requirement discussion."
        )

        threading.Thread(
            target=_run_and_release,
            args=(prompt, thread_ts, channel, session_id, lock),
            daemon=True,
        ).start()
    except Exception:
        lock.release()
        raise


@app.action("confirm_ba")
def handle_confirm_ba(ack, body):
    ack()
    channel = body["channel"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    user = body["user"]["id"]

    logger.info(f"Confirm BA clicked by {user}, thread_ts={thread_ts}")

    conv = state.get(thread_ts)
    if not conv:
        logger.info(f"No conversation for {thread_ts}, known={state.keys()}")
        return

    lock = _get_lock(thread_ts)
    if not lock.acquire(blocking=False):
        logger.info("Confirm BA: lock not acquired")
        return

    try:
        logger.info(f"Confirm BA: status={conv.get('status')}")
        if conv.get("status") != "waiting_answer":
            logger.info(f"Confirm BA: skipped, status={conv.get('status')}")
            return

        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=":white_check_mark: BA confirmed. Generating documents...",
        )

        conv["status"] = "running"
        conv["pending_action"] = "confirm_ba"
        state.set(thread_ts, conv)
        session_id = conv.get("session_id")

        prompt = (
            "The PM has confirmed the BA is complete. "
            "Please finalize and write the requirement document and BA report. "
            "Create the task JSON with status 'pending_dev'. "
            "After writing files, output ONLY the task ID in this exact format:\n"
            "TASK_ID: {the uuid}\n"
            "Do not output file paths."
        )

        threading.Thread(
            target=_confirm_ba_and_upload,
            args=(prompt, thread_ts, channel, session_id, lock),
            daemon=True,
        ).start()
    except Exception:
        lock.release()
        raise


@app.action("cancel_task")
def handle_cancel(ack, body):
    ack()
    channel = body["channel"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]

    conv = state.get(thread_ts)
    if conv:
        conv["status"] = "completed"
        state.set(thread_ts, conv)

    app.client.chat_postMessage(
        channel=channel, thread_ts=thread_ts,
        text=":no_entry_sign: Task cancelled.",
    )


@app.action(re.compile(r"^q_option_\d+$"))
def handle_option_click(ack, body):
    ack()
    action = body["actions"][0]
    selected_value = action["value"]
    channel = body["channel"]["id"]
    thread_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    user = body["user"]["id"]

    conv = state.get(thread_ts)
    if not conv:
        return

    lock = _get_lock(thread_ts)
    if not lock.acquire(blocking=False):
        return

    try:
        if conv.get("status") != "waiting_answer":
            return

        logger.info(f"Option selected: {selected_value} by {user}")

        app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=f":white_check_mark: Selected: *{selected_value}*",
        )

        conv["status"] = "running"
        state.set(thread_ts, conv)
        session_id = conv.get("session_id")

        threading.Thread(
            target=_run_and_release,
            args=(selected_value, thread_ts, channel, session_id, lock),
            daemon=True,
        ).start()
        return
    except Exception:
        lock.release()
        raise


# --- Startup ---

if __name__ == "__main__":
    logger.info(f"ATDD Hub: {ATDD_HUB_PATH}")
    logger.info(f"API: {api_client.API_BASE_URL} (reachable={api_client.health()})")
    logger.info(f"Claude model: {os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-6')}")
    logger.info(f"Projects: {_load_projects()}")
    logger.info(f"Active conversations: {len(state.keys())}")

    # Fix stuck "running" states from previous crashes
    for ts in state.keys():
        conv = state.get(ts)
        if conv and conv.get("status") == "running":
            conv["status"] = "waiting_answer"
            state.set(ts, conv)
            logger.info(f"Fixed stuck conversation: {ts}")

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("ATDD Bot starting (Socket Mode)...")
    handler.start()
