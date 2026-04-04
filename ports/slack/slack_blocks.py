"""Convert Claude output to Slack Block Kit."""


def action_buttons(show_confirm: bool = True) -> list[dict]:
    """Action buttons shown after each Bot reply.

    show_confirm: Only show Confirm BA when confidence >= 95%.
    """
    elements = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": ":mag: Analyze Code"},
            "action_id": "analyze_code",
        },
    ]

    if show_confirm:
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": ":white_check_mark: Confirm BA"},
            "style": "primary",
            "action_id": "confirm_ba",
        })

    elements.append({
        "type": "button",
        "text": {"type": "plain_text", "text": ":no_entry_sign: Cancel"},
        "style": "danger",
        "action_id": "cancel_task",
    })

    hint = "Reply to continue discussion, or click a button."
    if not show_confirm:
        hint = ":lock: Confirm BA unlocks at 95% confidence. Reply to continue."

    return [
        {"type": "divider"},
        {"type": "actions", "elements": elements},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": hint}]},
    ]


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
                label = opt.get("label", f"Option {j+1}")
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

    # Always append action buttons
    blocks.extend(action_buttons())
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
