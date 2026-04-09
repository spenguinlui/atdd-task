"""Convert Claude output to Slack Block Kit (Triage Bot version)."""


def questions_to_blocks(questions: list[dict]) -> list[dict]:
    """Convert AskUserQuestion questions to Slack Block Kit blocks."""
    blocks = []
    single_question = len(questions) == 1 and questions[0].get("options")

    for i, q in enumerate(questions):
        header = q.get("header", "")
        question = q.get("question", "")
        options = q.get("options", [])

        if header:
            blocks.append({
                "type": "header",
                "text": {"type": "plain_text", "text": header},
            })

        if question:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": question},
            })

        if options and single_question:
            elements = []
            for j, opt in enumerate(options):
                label = opt.get("label", f"選項 {j+1}")
                elements.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": label[:75]},
                    "action_id": f"q_option_{j}",
                    "value": label,
                })
            blocks.append({"type": "actions", "elements": elements})

            desc_lines = [f"• *{o.get('label', '')}*: {o.get('description', '')}"
                          for o in options if o.get("description")]
            if desc_lines:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "\n".join(desc_lines)}],
                })
        elif options:
            opt_text = "\n".join(
                f"{j+1}. *{o.get('label', '')}* — {o.get('description', '')}"
                for j, o in enumerate(options)
            )
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": opt_text},
            })

        if i < len(questions) - 1:
            blocks.append({"type": "divider"})

    return blocks


def result_to_blocks(text: str) -> list[dict]:
    """Convert Claude result text to Slack blocks."""
    if not text:
        return []

    chunks = [text[i:i+2900] for i in range(0, len(text), 2900)]
    blocks = []
    for chunk in chunks:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": chunk},
        })
    return blocks


def triage_action_buttons() -> list[dict]:
    """Action buttons shown after triage interview."""
    return [
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 確認立單"},
                    "action_id": "confirm_triage",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📝 補充說明"},
                    "action_id": "continue_triage",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 取消"},
                    "style": "danger",
                    "action_id": "cancel_triage",
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "確認後將自動建立 Jira 票，並通知 PM review。"}
            ],
        },
    ]
