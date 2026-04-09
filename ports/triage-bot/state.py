"""Persistent conversation state (JSON file)."""

import json
import logging
import os
import threading

logger = logging.getLogger("state")

STATE_FILE = os.environ.get("STATE_FILE", os.path.expanduser("~/atdd-server/triage-conversations.json"))
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def get(thread_ts: str) -> dict | None:
    with _lock:
        data = _load()
        return data.get(thread_ts)


def set(thread_ts: str, conv: dict):
    with _lock:
        data = _load()
        data[thread_ts] = conv
        _save(data)


def delete(thread_ts: str):
    with _lock:
        data = _load()
        data.pop(thread_ts, None)
        _save(data)


def keys() -> list[str]:
    with _lock:
        return list(_load().keys())
