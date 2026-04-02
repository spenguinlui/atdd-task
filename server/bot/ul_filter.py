"""Post-processing filter: replace English code names with ul.md Chinese terms.

Runs AFTER Claude responds, BEFORE sending to Slack.
Ensures PM always sees business language, not code names.
"""

import logging
import os
import re
from functools import lru_cache

logger = logging.getLogger("ul-filter")

ATDD_HUB_PATH = os.environ.get("ATDD_HUB_PATH", os.path.expanduser("~/atdd-hub"))


@lru_cache(maxsize=16)
def _load_ul_mapping(project: str) -> dict[str, str]:
    """Load English→Chinese term mapping from ul.md.

    Parses entries like:
        ### ActualEntry (用戶認列收支)
        **中文**: 用戶認列收支
    """
    ul_path = os.path.join(ATDD_HUB_PATH, f"domains/{project}/ul.md")
    mapping = {}

    try:
        with open(ul_path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        logger.warning(f"ul.md not found: {ul_path}")
        return mapping

    # Pattern 1: ### EnglishName (中文名稱)
    for match in re.finditer(r"^### (\w+)\s*[（(](.+?)[）)]", content, re.MULTILINE):
        eng = match.group(1)
        chn = match.group(2).strip()
        mapping[eng] = chn

    # Pattern 2: **中文**: 中文名稱 (more authoritative if present)
    current_eng = None
    for line in content.split("\n"):
        h3_match = re.match(r"^### (\w+)", line)
        if h3_match:
            current_eng = h3_match.group(1)
        zh_match = re.match(r"\*\*中文\*\*:\s*(.+)", line)
        if zh_match and current_eng:
            mapping[current_eng] = zh_match.group(1).strip()

    logger.info(f"Loaded {len(mapping)} UL terms for {project}")
    return mapping


def _build_code_pattern(mapping: dict[str, str]) -> re.Pattern | None:
    """Build regex to match English terms that should be replaced."""
    if not mapping:
        return None

    # Sort by length descending so longer terms match first
    # e.g. "ActualEntry" before "Entry"
    terms = sorted(mapping.keys(), key=len, reverse=True)

    # Match terms that appear as:
    # - standalone word
    # - in backticks: `ActualEntry`
    # - in snake_case context: actual_entry (won't match, only PascalCase)
    # Only match PascalCase terms (class names), not lowercase
    pascal_terms = [t for t in terms if t[0].isupper()]

    if not pascal_terms:
        return None

    pattern = r'`?(' + '|'.join(re.escape(t) for t in pascal_terms) + r')`?'
    return re.compile(pattern)


def apply_ul_filter(text: str, project: str) -> str:
    """Replace English code names with Chinese business terms from ul.md.

    Also strips backticks around replaced terms and removes code-heavy lines.
    """
    if not text or not project:
        return text

    mapping = _load_ul_mapping(project)
    if not mapping:
        return text

    pattern = _build_code_pattern(mapping)
    if not pattern:
        return text

    def replacer(match):
        full = match.group(0)
        term = match.group(1)
        if term in mapping:
            return mapping[term]
        return full

    result = pattern.sub(replacer, text)

    # Also replace snake_case versions of known terms
    # e.g. actual_entry → 用戶認列收支
    for eng, chn in mapping.items():
        # Convert PascalCase to snake_case
        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', eng).lower()
        if snake != eng.lower() and len(snake) > 3:
            # Replace `snake_case` (in backticks)
            result = result.replace(f"`{snake}`", chn)
            # Replace standalone snake_case only if surrounded by non-word chars
            result = re.sub(
                rf'(?<![a-zA-Z_]){re.escape(snake)}(?![a-zA-Z_])',
                chn,
                result
            )

    return result


def clear_cache():
    """Clear the UL mapping cache (call when knowledge files are updated)."""
    _load_ul_mapping.cache_clear()
