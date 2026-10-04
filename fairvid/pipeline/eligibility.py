"""Helpers for the knowledge-base eligibility checker.

The Colab notebook `Admission_Eligibility_Checker_using_KB.ipynb` sends a filled
prompt to Gemini. The pieces below do not call a model. They prepare the same
inputs the notebook prepares: study level, markdown summaries, country codes,
and the filled prompt. A cloud call can sit on top of ``fill_prompt`` later.
"""

import json
import re
from pathlib import Path

from .. import config

_JSON_FENCE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
_COUNTRY = re.compile(r'"country_code"\s*:\s*"([A-Z]{2,3})"')


def extract_json_from_response(response_text: str | None):
    """Pull a JSON object out of a model reply.

    Returns ``(ok, payload)``. When parsing fails, ``payload`` keeps the raw
    text so the caller can still write an audit file, matching the notebook.
    """
    if not response_text:
        return False, {"raw_response": response_text, "parse_status": "empty_response"}
    match = _JSON_FENCE.search(response_text)
    candidate = match.group(1).strip() if match else response_text.strip()
    try:
        return True, json.loads(candidate)
    except json.JSONDecodeError:
        return False, {"raw_response": response_text, "parse_status": "non_json_response"}


def normalize_awards_abbr(value) -> str:
    """Map a free-text award label to ``Master`` or ``Bachelor``."""
    if "master" in str(value or "Bachelor").strip().lower():
        return "Master"
    return "Bachelor"


def read_awards_abbr(applicant_dir: Path) -> str:
    """Read ``awards_abbr`` from ``short_application_info.json``. Default Bachelor."""
    info_path = Path(applicant_dir) / config.SHORT_APPLICATION_INFO
    if not info_path.is_file():
        return "Bachelor"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "Bachelor"
    return normalize_awards_abbr(info.get("awards_abbr", "Bachelor"))


def read_summary_markdown(applicant_dir: Path) -> tuple[str, list[Path]]:
    """Concatenate ``document_summaries*.md`` files in the applicant folder."""
    files = sorted(
        p for p in Path(applicant_dir).glob("*.md")
        if p.name.startswith("document_summaries")
    )
    parts = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            text = f"[Could not read file: {exc}]"
        parts.append(f"# {path.name}\n{text}")
    return "\n\n---\n\n".join(parts), files


def extract_country_codes(markdown: str) -> list[str]:
    """Unique ISO-like codes from ``"country_code": "XX"`` snippets, sorted."""
    return sorted(set(_COUNTRY.findall(markdown or "")))


def filter_country_rules(intl_data: dict, country_codes: list[str]) -> str:
    """Keep only the country rules the documents mentioned. JSON string."""
    if not country_codes:
        return json.dumps(
            {"note": "No country_code values found in applicant documents. "
             "No country-specific rules applied."},
            ensure_ascii=False, indent=2,
        )
    found = {}
    missing = []
    for code in country_codes:
        if code in intl_data:
            found[code] = intl_data[code]
        else:
            missing.append(code)
    result = {}
    if found:
        result["country_requirements"] = found
    if missing:
        result["not_found_country_codes"] = {
            code: "NOT FOUND: No specific requirements data available for this country code."
            for code in missing
        }
    return json.dumps(result, ensure_ascii=False, indent=2)


def fill_prompt(template: str, *, application_info: str, student_info: str,
                precheck_results: str, rules_kb: str, country_rule_kb: str,
                applicant_document_info: str, rules_placeholder: str) -> str:
    """Replace the notebook's ``{{PLACEHOLDER}}`` tokens."""
    replacements = {
        "{{APPLICATION_INFO}}": application_info,
        "{{STUDENT_INFO}}": student_info,
        "{{PRECHECK_RESULTS}}": precheck_results,
        "{{COUNTRY_RULE}}": country_rule_kb,
        "{{APPLICANT_DOCUMENT_INFO}}": applicant_document_info,
        rules_placeholder: rules_kb,
    }
    prompt = template
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    return prompt


def eligibility_payload(*, awards_abbr: str, application_root: str,
                        source_markdown_files: list[str],
                        detected_country_codes: list[str],
                        parsed_ok: bool, content) -> dict:
    """Shape the JSON file the eligibility notebook writes."""
    if parsed_ok and isinstance(content, dict):
        content.setdefault("awards_abbr", awards_abbr)
        content.setdefault("source_markdown_files", source_markdown_files)
        content.setdefault("application_root", application_root)
        content.setdefault("detected_country_codes", detected_country_codes)
        return content
    return {
        "awards_abbr": awards_abbr,
        "application_root": application_root,
        "source_markdown_files": source_markdown_files,
        "detected_country_codes": detected_country_codes,
        "response": content,
    }
