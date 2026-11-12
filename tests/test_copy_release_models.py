"""copy_release_models.py chỉ chép file của mô hình kèm sẵn, không chép cả cache."""
import copy_release_models as crm
from apps.model_catalog import BUNDLED_MODEL_ID, get


def _fake_cache(hub, *, skip=None, with_refs=True):
    """Cache HF giả: đủ file của mô hình kèm sẵn + rác (Kokoro, fp32, giọng nhân bản)."""
    for source in get(BUNDLED_MODEL_ID).sources:
        repo = crm.repo_dir(hub, source.repo)
        if with_refs:
            (repo / "refs").mkdir(parents=True, exist_ok=True)
            (repo / "refs" / "main").write_text("abc123")
        for rel in source.allow_patterns:
            if rel == skip:
                continue
            f = repo / "snapshots" / "abc123" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"x")
    junk = [
        crm.repo_dir(hub, "hexgrad/Kokoro-82M") / "snapshots" / "s" / "kokoro.pth",
        crm.repo_dir(hub, "pnnbao-ump/VieNeu-TTS-v3-Turbo") / "snapshots" / "abc123" / "onnx_update" / "vieneu_prefill.onnx",
        hub.parent.parent / "custom_voices_v3_turbo.json",
    ]
    for f in junk:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"junk")


def test_copies_only_bundled_files(tmp_path, monkeypatch):
    hub = tmp_path / "models" / "hf_cache" / "hub"
    _fake_cache(hub)
    monkeypatch.setattr(crm, "SOURCE_HUB", hub)
    dest = tmp_path / "dist" / "models"
    assert crm.main(["x", str(dest)]) == 0

    copied = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    expected = sum(len(s.allow_patterns) for s in get(BUNDLED_MODEL_ID).sources) + len(get(BUNDLED_MODEL_ID).sources) - 1
    # refs/main mỗi repo (V3 xuất hiện 2 nguồn nhưng một repo) + từng file trong danh sách
    assert len(copied) == expected
    assert not any("Kokoro" in p or "onnx_update" in p or "custom_voices" in p for p in copied)
    assert (crm.repo_dir(dest / "hf_cache" / "hub", "pnnbao-ump/VieNeu-TTS-v3-Turbo") / "refs" / "main").read_text() == "abc123"


def test_missing_file_fails_without_touching_dest(tmp_path, monkeypatch):
    hub = tmp_path / "models" / "hf_cache" / "hub"
    _fake_cache(hub, skip="speaker_encoder.onnx")
    monkeypatch.setattr(crm, "SOURCE_HUB", hub)
    dest = tmp_path / "dist" / "models"
    dest.mkdir(parents=True)
    (dest / "keep.txt").write_text("old")
    assert crm.main(["x", str(dest)]) == 1
    assert (dest / "keep.txt").exists()  # thiếu file thì không xoá bản cũ


def test_replaces_stale_destination(tmp_path, monkeypatch):
    hub = tmp_path / "models" / "hf_cache" / "hub"
    _fake_cache(hub)
    monkeypatch.setattr(crm, "SOURCE_HUB", hub)
    dest = tmp_path / "dist" / "models"
    (dest / "hf_cache" / "hub" / "models--hexgrad--Kokoro-82M").mkdir(parents=True)
    assert crm.main(["x", str(dest)]) == 0
    assert not (dest / "hf_cache" / "hub" / "models--hexgrad--Kokoro-82M").exists()


def test_cache_without_refs_main_uses_single_snapshot(tmp_path, monkeypatch):
    # Máy build CI sạch: fetch_models tải theo mã commit nên (trước đây) không có refs/main.
    hub = tmp_path / "models" / "hf_cache" / "hub"
    _fake_cache(hub, with_refs=False)
    monkeypatch.setattr(crm, "SOURCE_HUB", hub)
    dest = tmp_path / "dist" / "models"
    assert crm.main(["x", str(dest)]) == 0
    # Bản đóng gói vẫn có refs/main: app đọc offline theo "main".
    ref = crm.repo_dir(dest / "hf_cache" / "hub", "pnnbao-ump/VieNeu-TTS-v3-Turbo") / "refs" / "main"
    assert ref.read_text() == "abc123"


def test_several_snapshots_without_ref_is_an_error(tmp_path, monkeypatch):
    hub = tmp_path / "models" / "hf_cache" / "hub"
    _fake_cache(hub, with_refs=False)
    (crm.repo_dir(hub, "pnnbao-ump/VieNeu-TTS-v3-Turbo") / "snapshots" / "def456").mkdir()
    monkeypatch.setattr(crm, "SOURCE_HUB", hub)
    assert crm.main(["x", str(tmp_path / "dist" / "models")]) == 1


def test_fetch_models_pins_refs_main(tmp_path, monkeypatch):
    import fetch_models

    monkeypatch.setenv("HF_HOME", str(tmp_path))
    fetch_models.pin_main_refs({"pnnbao-ump/VieNeu-TTS-v3-Turbo": "abc123"})
    assert (tmp_path / "hub" / "models--pnnbao-ump--VieNeu-TTS-v3-Turbo" / "refs" / "main").read_text() == "abc123"
