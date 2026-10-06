"""Checks that the Python agents keep the contracts from the Colab notebooks."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fairvid.pipeline.audio_affect import analyze_audio
from fairvid.pipeline.behaviour_video import _smiling
from fairvid.pipeline.eligibility import (
    extract_country_codes,
    extract_json_from_response,
    fill_prompt,
    normalize_awards_abbr,
    read_awards_abbr,
)
from fairvid.pipeline.explain import counterfactual
from fairvid.pipeline.fusion import FEATURE_NAMES
from fairvid.pipeline.grader import audit_transcript, grade_transcript
from fairvid.pipeline.pages import concatenate_pages, document_id, group_page_files
from fairvid.pipeline.reconcile import choose_reconciled_value, reconcile_document
from fairvid.pipeline.scoring import ScoreModel
from fairvid.pipeline.vlm import ollama_available


def test_page_groups_keep_document_identity():
    files = [
        "/tmp/Passport.pdf (page 2).txt",
        "/tmp/Passport.pdf (page 1).txt",
        "/tmp/Diploma.txt",
    ]
    grouped = group_page_files(files)
    assert document_id(files[0]) == "Passport.pdf"
    assert set(grouped) == {"Passport.pdf", "Diploma"}
    assert len(grouped["Passport.pdf"]) == 2


def test_pages_concatenate_in_page_order():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        first = folder / "Form.pdf (page 1).txt"
        second = folder / "Form.pdf (page 2).txt"
        first.write_text("page-one", encoding="utf-8")
        second.write_text("page-two", encoding="utf-8")
        text = concatenate_pages([str(second), str(first)])
    assert text == "page-one\npage-two"


def test_reconciliation_vote_rules():
    order = ["model_a", "model_b", "model_c"]
    value, method = choose_reconciled_value(
        {"model_a": "TR", "model_b": "TR", "model_c": " TR "}, order)
    assert value == "TR" and method == "consensus"

    value, method = choose_reconciled_value(
        {"model_a": "BA", "model_b": "MA", "model_c": "MA"}, order)
    assert value == "MA" and method == "majority_vote"

    value, method = choose_reconciled_value(
        {"model_a": "BA", "model_b": "MA", "model_c": ""}, order)
    assert value == "BA" and method == "first_available"

    value, method = choose_reconciled_value(
        {"model_a": None, "model_b": "  "}, order)
    assert value is None and method == "all_empty"


def test_reconcile_document_keeps_provenance():
    body = reconcile_document(
        {
            "model_a": {"country_code": "TR", "nested": {"gpa": "3.5"}},
            "model_b": {"country_code": "TR", "nested": {"gpa": "3.4"}},
        },
        ["model_a", "model_b"],
    )
    assert body["reconciled_fields"]["country_code"] == "TR"
    assert body["field_provenance"]["country_code"]["resolution_method"] == "consensus"
    assert body["field_provenance"]["nested.gpa"]["resolution_method"] == "first_available"
    assert body["reconciled_fields"]["nested.gpa"] == "3.5"


def test_eligibility_helpers():
    ok, payload = extract_json_from_response('```json\n{"eligible": true}\n```')
    assert ok and payload["eligible"] is True
    ok, payload = extract_json_from_response("not json")
    assert not ok and payload["parse_status"] == "non_json_response"
    assert normalize_awards_abbr("Master's degree") == "Master"
    assert normalize_awards_abbr("BSc") == "Bachelor"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        info = folder / "short_application_info.json"
        info.write_text('{"awards_abbr": "Master of Science"}', encoding="utf-8")
        assert read_awards_abbr(folder) == "Master"
    codes = extract_country_codes('{"country_code": "TR"} {"country_code": "TR"} {"country_code": "DE"}')
    assert codes == ["DE", "TR"]
    filled = fill_prompt(
        "Rules {{BACHELOR_RULES}} docs {{APPLICANT_DOCUMENT_INFO}}",
        application_info="", student_info="", precheck_results="",
        rules_kb="RULES", country_rule_kb="",
        applicant_document_info="DOCS", rules_placeholder="{{BACHELOR_RULES}}",
    )
    assert filled == "Rules RULES docs DOCS"


def test_keyword_grader_scores_random_speech_as_if_it_were_strong():
    """The offline stand-in never reads the question, so gibberish looks fluent."""
    question = "Explain the difference between a microcontroller and a microprocessor."
    random_speech = "purple orbit kettle marble violin horizon cactus pebble lantern quartz"
    grade = grade_transcript(question, random_speech)
    assert grade["metrics"]["relevance_score"] >= 8
    assert grade["overall_score"] >= 70


def test_live_auditor_uses_the_model_judgement_not_the_keyword_score():
    question = "Explain the difference between a microcontroller and a microprocessor."
    random_speech = "purple orbit kettle marble violin horizon cactus pebble lantern quartz"

    def fake_model(prompt):
        assert question in prompt and random_speech in prompt
        return "gemma3:4b", (
            '{"overall_score": 12, "executive_summary": "Does not answer the question.",'
            ' "ai_script_detection": {"is_likely_reading_llm_text": false,'
            ' "suspicion_score": 5, "flags": [], "reasoning": "Not a script."},'
            ' "metrics": {"relevance_score": 1, "clarity_score": 2, "structure_score": 2}}'
        )

    grade = audit_transcript(question, random_speech, generate=fake_model)
    assert grade["backend"] == "ollama"
    assert grade["overall_score"] == 12
    assert grade["metrics"]["relevance_score"] == 1


def test_empty_smile_is_a_pair_of_floats():
    assert _smiling({}) == (0.0, 0.0)
    assert _smiling({"mouthSmileLeft": [], "mouthSmileRight": []}) == (0.0, 0.0)
    _avg, freq = _smiling({"mouthSmileLeft": [0.0, 0.9], "mouthSmileRight": [0.0, 0.9]})
    assert freq == 50.0


def test_audio_affect_skips_cleanly_without_librosa():
    import builtins
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "librosa" or name.startswith("librosa."):
            raise ImportError("librosa is not installed")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", blocked):
        result = analyze_audio("interview.wav", emotions=False)
    assert result["ok"] is False
    assert result["backend"] == "unavailable"
    assert result["tempo_bpm"] is None


def test_counterfactual_does_not_edit_gpa():
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, len(FEATURE_NAMES)))
    y = (X[:, FEATURE_NAMES.index("interview_overall_mean")] > 0).astype(int)
    scaler = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=200).fit(scaler.transform(X), y)
    idx = np.arange(len(y))
    sm = ScoreModel(clf, scaler, list(FEATURE_NAMES), X, X, y, y, idx, idx)
    x = np.zeros(len(FEATURE_NAMES))
    x[FEATURE_NAMES.index("gpa")] = 3.2
    out = counterfactual(sm, x, target=1, max_iter=30)
    assert "gpa" not in out["changes_in_original_units"]
    smile_i = FEATURE_NAMES.index("behaviour_smile")
    if "behaviour_smile" in out["changes_in_original_units"]:
        new_smile = x[smile_i] + out["changes_in_original_units"]["behaviour_smile"]
        assert 0.0 <= new_smile <= 100.0


def test_ollama_probe_is_false_when_the_server_is_down():
    # The old probe returned True even when the model list was empty.
    if ollama_available() is False:
        assert ollama_available("gemma3:12b") is False
