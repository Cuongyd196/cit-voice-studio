import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps import pronunciation_settings as ps
from vieneu_utils.pronunciation import (
    DEFAULT_ENTRIES,
    PronunciationDict,
    apply_pronunciations,
    validate_entries,
)

AI = {"word": "AI", "reading": "ây ai"}
API = {"word": "API", "reading": "ây pi ai"}


# ---------------------------------------------------------------- thay thế chữ

def test_replaces_acronyms_and_prefers_longest():
    # API đứng sau AI trong danh sách vẫn phải thắng — không được ra "ây aiPI".
    assert apply_pronunciations("Gọi API và AI.", [AI, API]) == "Gọi ây pi ai và ây ai."


def test_whole_word_only():
    out = apply_pronunciations("OpenAI, AIDS, MAI, AI-based, (AI)", [AI])
    assert out == "OpenAI, AIDS, MAI, ây ai-based, (ây ai)"


def test_case_sensitive_by_default_keeps_vietnamese_ai():
    assert apply_pronunciations("Ai dùng AI?", [AI]) == "Ai dùng ây ai?"


def test_match_case_false_matches_any_case():
    entries = [{"word": "wifi", "reading": "oai phai", "match_case": False}]
    assert apply_pronunciations("Wifi, WIFI, wifi", entries) == "oai phai, oai phai, oai phai"


def test_word_with_punctuation_and_vietnamese_boundaries():
    entries = [{"word": "A.I.", "reading": "ây ai"}, {"word": "TP.HCM", "reading": "thành phố hồ chí minh"}]
    assert apply_pronunciations("A.I. ở TP.HCM", entries) == "ây ai ở thành phố hồ chí minh"
    # Chữ có dấu liền kề là một phần của từ -> không khớp.
    assert apply_pronunciations("ÂAI", [AI]) == "ÂAI"


def test_single_pass_does_not_rewrite_replacements():
    entries = [AI, {"word": "ai", "reading": "ai nào", "match_case": True}]
    assert apply_pronunciations("AI", entries) == "ây ai"


def test_emotion_tags_untouched():
    entries = [{"word": "cười", "reading": "CƯỜI TO"}]
    assert apply_pronunciations("[cười] tôi cười <|emotion_1|>", entries) == "[cười] tôi CƯỜI TO <|emotion_1|>"


def test_empty_dict_and_text_are_noops():
    assert PronunciationDict([]).apply("AI") == "AI"
    assert apply_pronunciations("", [AI]) == ""


@pytest.mark.parametrize(
    "entries",
    [
        [{"word": " ", "reading": "x"}],
        [{"word": "AI", "reading": "  "}],
        [AI, {"word": "AI", "reading": "ai"}],
        [{"word": "ai", "reading": "x", "match_case": False}, AI],
        [AI, {"word": "ai", "reading": "x", "match_case": False}],
        [{"word": "[cười]", "reading": "x"}],
        [{"word": "AI", "reading": "x", "match_case": "yes"}],
    ],
)
def test_invalid_entries_rejected(entries):
    with pytest.raises(ValueError):
        validate_entries(entries)


def test_same_word_different_case_allowed_when_both_case_sensitive():
    assert len(validate_entries([AI, {"word": "Ai", "reading": "ai"}])) == 2


def test_defaults_are_valid_and_read_in_vietnamese():
    d = PronunciationDict(validate_entries(DEFAULT_ENTRIES))
    assert d.apply("Học sinh nhận SGK tại KTX.") == "Học sinh nhận sách giáo khoa tại ký túc xá."


def test_default_abbreviations_are_ones_normalizer_spells_out():
    """Mỗi viết tắt Việt trong bộ mặc định phải là từ normalizer ĐỌC SAI (đánh vần),
    nếu không thì mục đó thừa — và làm ví dụ trên giao diện mất tác dụng."""
    from vieneu_utils.phonemize_text import _get_normalizer

    n = _get_normalizer()
    for e in DEFAULT_ENTRIES:
        before = n.normalize(f"{e['word']} mới")
        assert e["reading"] not in before, (e["word"], before)
        assert n.normalize(f"{e['reading']} mới") == f"{e['reading']} mới."


def test_readings_stay_vietnamese_after_normalizer():
    """Cách đọc phải ra chữ Việt, không bị bọc <en> như bản gốc."""
    from vieneu_utils.phonemize_text import _get_normalizer

    n = _get_normalizer()
    assert "<en>" in n.normalize("Dùng AI.")
    assert "<en>" not in n.normalize(apply_pronunciations("Dùng AI và API.", [AI, API]))


# ---------------------------------------------------------------- lưu trữ + API

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "dict_path", lambda: tmp_path / "pronunciation-dict.json")
    monkeypatch.setattr(ps, "_cache_key", None)
    app = FastAPI()
    app.include_router(ps.router)
    with TestClient(app) as c:
        yield c


def test_defaults_when_no_file(client):
    body = client.get("/api/pronunciations").json()
    assert [e["word"] for e in body["entries"]] == [e["word"] for e in DEFAULT_ENTRIES]
    assert ps.apply("KTX") == "ký túc xá"
    assert not ps.dict_path().exists()


def test_save_then_apply(client):
    r = client.put("/api/pronunciations", json={"entries": [API]})
    assert r.status_code == 200
    assert r.json()["entries"] == [{**API, "match_case": True}]
    saved = json.loads(ps.dict_path().read_text(encoding="utf-8"))
    assert saved["entries"][0]["reading"] == "ây pi ai"  # UTF-8, không escape
    assert ps.apply("AI và API") == "AI và ây pi ai"


def test_empty_list_disables_everything(client):
    assert client.put("/api/pronunciations", json={"entries": []}).status_code == 200
    assert ps.apply("AI") == "AI"


def test_invalid_save_rejected_and_file_kept(client):
    client.put("/api/pronunciations", json={"entries": [AI]})
    r = client.put("/api/pronunciations", json={"entries": [AI, AI]})
    assert r.status_code == 400
    assert "trùng" in r.json()["detail"]
    assert ps.apply("AI") == "ây ai"


def test_manual_file_edit_picked_up(client):
    client.put("/api/pronunciations", json={"entries": [AI]})
    path = ps.dict_path()
    path.write_text(json.dumps({"entries": [{"word": "AI", "reading": "a i"}]}), encoding="utf-8")
    import os
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert ps.apply("AI") == "a i"


def test_corrupt_file_falls_back_to_defaults_without_overwriting(client):
    ps.dict_path().write_text("{broken", encoding="utf-8")
    assert ps.apply("SGK") == "sách giáo khoa"
    assert ps.dict_path().read_text(encoding="utf-8") == "{broken"


def test_write_failure_reports_500_and_keeps_previous(client, monkeypatch):
    client.put("/api/pronunciations", json={"entries": [AI]})
    monkeypatch.setattr(ps.os, "replace", lambda *_: (_ for _ in ()).throw(PermissionError()))
    assert client.put("/api/pronunciations", json={"entries": [API]}).status_code == 500
    assert ps.apply("AI") == "ây ai"
    assert list(ps.dict_path().parent.glob("*.tmp")) == []


def test_preview_with_draft_and_saved(client):
    client.put("/api/pronunciations", json={"entries": [AI]})
    assert client.post("/api/pronunciations/preview", json={"text": "API"}).json()["text"] == "API"
    r = client.post("/api/pronunciations/preview", json={"text": "API", "entries": [API]})
    assert r.json()["text"] == "ây pi ai"
    bad = client.post("/api/pronunciations/preview", json={"text": "x", "entries": [AI, AI]})
    assert bad.status_code == 400


# ---------------------------------------------------------------- web_stream

@pytest.fixture
def ws_client(tmp_path, monkeypatch):
    import numpy as np
    from unittest.mock import Mock

    from apps import web_stream as ws

    monkeypatch.setattr(ps, "dict_path", lambda: tmp_path / "pronunciation-dict.json")
    monkeypatch.setattr(ps, "_cache_key", None)
    engine = Mock()
    engine.sample_rate = 48000
    engine.infer.return_value = np.zeros(4800, dtype=np.float32)
    engine.infer_stream.return_value = iter([np.zeros(480, dtype=np.float32)])
    monkeypatch.setattr(ws, "vieneu", engine)
    monkeypatch.setattr(ws, "current_model_info", {"sample_rate": 48000})
    with TestClient(ws.app) as c:
        yield c, engine


def test_generate_applies_dict(ws_client):
    c, engine = ws_client
    assert c.post("/api/tts/generate", json={"text": "Về KTX"}).status_code == 200
    assert engine.infer.call_args.args[0] == "Về ký túc xá"


def test_generate_can_skip_dict_for_preview_playback(ws_client):
    c, engine = ws_client
    r = c.post("/api/tts/generate", json={"text": "ây ai", "use_pronunciation_dict": False})
    assert r.status_code == 200
    assert engine.infer.call_args.args[0] == "ây ai"


def test_stream_and_conversation_apply_dict(ws_client):
    c, engine = ws_client
    assert c.get("/stream", params={"text": "KTX"}).status_code == 200
    assert engine.infer_stream.call_args.args[0] == "ký túc xá"
    r = c.post("/api/tts/conversation", json={"turns": [{"speaker": "A", "text": "Mua SGK"}]})
    assert r.status_code == 200
    assert engine.infer.call_args.args[0] == "Mua sách giáo khoa"
