"""Vote across document summaries written by different models.

This is the reconciliation agent from `doc_reconciliationAgent.ipynb`.
Each model writes a JSON file with the same document name. Fields are compared
after empty answers are ignored:

- **consensus** — every model that answered gave the same value
- **majority_vote** — at least two models agreed, and they beat the others
- **first_available** — a tie, or only one model answered; the earliest model
  in ``model_order`` wins
- **all_empty** — nobody answered

The first name in ``model_order`` is the tie-breaker, matching the notebook.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .. import config


def flatten_json(data: Any, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten nested dicts. Lists stay as a single value."""
    items: dict = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
            if isinstance(value, dict):
                items.update(flatten_json(value, new_key, sep))
            else:
                items[new_key] = value
    elif parent_key:
        items[parent_key] = data
    return items


def normalize_value(value: Any):
    """Make formatting differences compare as equal. Empty values become None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def choose_reconciled_value(values_by_model: dict, model_order: list[str]):
    """Pick one value and the rule that picked it.

    Returns ``(value, method)``. ``value`` is the original (not normalised)
    object from the winning model.
    """
    entries = []
    for model_name in model_order:
        if model_name not in values_by_model:
            continue
        raw = values_by_model[model_name]
        norm = normalize_value(raw)
        if norm is not None:
            entries.append((model_name, raw, norm))

    if not entries:
        return None, "all_empty"

    counts = Counter(entry[2] for entry in entries)
    winner_norm, winner_count = counts.most_common(1)[0]
    if len(counts) == 1:
        method = "consensus"
    elif winner_count > 1:
        method = "majority_vote"
    else:
        method = "first_available"

    for model_name in model_order:
        for entry_model, raw, norm in entries:
            if entry_model == model_name and norm == winner_norm:
                return raw, method
    return entries[0][1], method


def discover_summary_dirs(application_root: Path) -> list[str]:
    """Folder names that start with ``document_summaries_`` and are not reconciled."""
    found = set()
    root = Path(application_root)
    if not root.is_dir():
        return []
    for applicant in root.iterdir():
        if not applicant.is_dir():
            continue
        for sub in applicant.iterdir():
            name = sub.name
            if (sub.is_dir() and name.startswith(config.DOCUMENT_SUMMARIES_PREFIX)
                    and "reconciled" not in name):
                found.add(name)
    return sorted(found)


def reconcile_document(payloads_by_model: dict[str, dict], model_order: list[str]) -> dict:
    """Reconcile one document's model payloads into fields plus provenance."""
    flattened = {
        model: flatten_json(payload)
        for model, payload in payloads_by_model.items()
        if isinstance(payload, dict)
    }
    if not flattened:
        return {"reconciled_fields": {}, "field_provenance": {}}

    all_fields = sorted(set().union(*(set(d) for d in flattened.values())))
    reconciled = {}
    provenance = {}
    for field_name in all_fields:
        values = {
            model: flattened[model].get(field_name)
            for model in model_order
            if model in flattened
        }
        value, method = choose_reconciled_value(values, model_order)
        reconciled[field_name] = value
        provenance[field_name] = {
            "resolution_method": method,
            "values_by_model": values,
        }
    return {"reconciled_fields": reconciled, "field_provenance": provenance}


def reconcile_applicant(applicant_dir: Path, model_dirs: list[str] | None = None) -> list[Path]:
    """Write one reconciled JSON per document into the reconciled folder.

    Returns the paths that were written.
    """
    applicant_dir = Path(applicant_dir)
    if model_dirs is None:
        model_dirs = discover_summary_dirs(applicant_dir.parent)
    written: list[Path] = []
    out_dir = applicant_dir / config.RECONCILED_SUMMARIES_DIR
    # Collect document name -> {model_dir: payload}
    by_doc: dict[str, dict] = {}
    for model_dir in model_dirs:
        source = applicant_dir / model_dir
        if not source.is_dir():
            continue
        for path in sorted(source.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                by_doc.setdefault(path.name, {})[model_dir] = payload

    if not by_doc:
        return written
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc_name, payloads in by_doc.items():
        body = reconcile_document(payloads, model_dirs)
        result = {
            "_meta": {
                "applicant": applicant_dir.name,
                "document": doc_name,
                "source_models": list(payloads),
                "total_fields": len(body["reconciled_fields"]),
            },
            **body,
        }
        dest = out_dir / doc_name
        dest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(dest)
    return written
