import numpy as np
import pytest
from vieneu.utils import _linear_overlap_add, extract_speech_ids
from vieneu_utils.core_utils import (
    split_text_into_chunks,
    split_into_sentences,
    pack_sentences_into_chunks,
    join_audio_chunks,
)

# --- Text Utils Tests ---

def test_split_text_into_chunks():
    text = "Đây là một câu ngắn. Đây là một câu dài hơn một chút để kiểm tra xem nó có bị chia ra không nếu chúng ta đặt giới hạn ký tự thấp."
    chunks = split_text_into_chunks(text, max_chars=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50

def test_split_text_paragraphs():
    text = "Đoạn 1.\n\nĐoạn 2."
    chunks = split_text_into_chunks(text, max_chars=100)
    assert len(chunks) == 2
    assert "Đoạn 1" in chunks[0]
    assert "Đoạn 2" in chunks[1]

# --- Sentence splitting (quote-aware) ---

def test_split_into_sentences_basic():
    assert split_into_sentences("Câu một. Câu hai! Câu ba?") == [
        "Câu một.", "Câu hai!", "Câu ba?",
    ]

def test_split_into_sentences_keeps_quoted_question_together():
    """Dấu .!? trong trích dẫn KHÔNG phải ranh giới câu."""
    text = 'Có phải ý anh là, kiểu như: "Rồi sao nữa? Đến bao giờ?", đúng không anh?'
    assert split_into_sentences(text) == [text]

def test_split_into_sentences_brackets():
    assert split_into_sentences("Cái đó (tôi nghĩ vậy. chắc thế) là đúng. Xong.") == [
        "Cái đó (tôi nghĩ vậy. chắc thế) là đúng.", "Xong.",
    ]

def test_split_into_sentences_unbalanced_quote_falls_back():
    """Một dấu nháy lạc không được nuốt phần còn lại thành một câu khổng lồ."""
    assert split_into_sentences('Câu một. Câu hai lệch " ở đây. Câu ba.') == [
        "Câu một.", 'Câu hai lệch " ở đây.', "Câu ba.",
    ]

def test_split_into_sentences_apostrophe_is_not_a_quote():
    assert split_into_sentences("He said don't worry. Then he left.") == [
        "He said don't worry.", "Then he left.",
    ]

def test_split_into_sentences_decimal_not_split():
    """`.` không theo sau bởi khoảng trắng thì không phải ranh giới câu."""
    assert split_into_sentences("Giá 3.5 triệu. Lúc 8.30 sáng.") == [
        "Giá 3.5 triệu.", "Lúc 8.30 sáng.",
    ]

def test_split_into_sentences_repeated_punct():
    assert split_into_sentences("Câu một... Câu hai?! Câu ba.") == [
        "Câu một...", "Câu hai?!", "Câu ba.",
    ]

# --- Packing ---

def test_pack_sentences_respects_max_chars():
    sents = ["A" * 30 + ".", "B" * 30 + ".", "C" * 30 + "."]
    chunks = pack_sentences_into_chunks(sents, max_chars=70)
    assert all(len(c) <= 70 for c in chunks)
    assert "".join(chunks).count("A") == 30

def test_pack_sentences_splits_oversized_sentence_at_commas():
    sent = "phần một, " + "x" * 40 + ", phần hai, " + "y" * 40 + "."
    chunks = pack_sentences_into_chunks([sent], max_chars=60)
    assert len(chunks) > 1
    assert all(len(c) <= 60 for c in chunks)

# --- Cắt cưỡng bức theo từ: ưu tiên từ nối ---

def test_forced_word_cut_prefers_connector():
    """Mảnh không dấu câu dài quá trần: cắt TRƯỚC từ nối, không chặt sát trần."""
    sent = "x" * 18 + " yy và " + "z" * 18 + " ww"
    chunks = pack_sentences_into_chunks([sent], max_chars=40)
    assert chunks == ["x" * 18 + " yy", "và " + "z" * 18 + " ww"]

def test_forced_word_cut_does_not_split_inside_connector_pair():
    """"sau khi" là MỘT từ nối: cắt trước cả cặp, không bao giờ "sau | khi"."""
    sent = "x" * 18 + " yy sau khi " + "z" * 14
    chunks = pack_sentences_into_chunks([sent], max_chars=30)
    assert chunks == ["x" * 18 + " yy", "sau khi " + "z" * 14]

def test_forced_word_cut_no_dangling_connector_before_pair():
    """"và sau đó": cắt phải lùi về trước "và", không bỏ rơi "và" cuối mảnh trái."""
    sent = "x" * 20 + " và sau đó " + "z" * 20
    chunks = pack_sentences_into_chunks([sent], max_chars=32)
    assert chunks == ["x" * 20, "và sau đó " + "z" * 20]

def test_forced_word_cut_never_splits_pair_even_without_natural_cut():
    """Từ nối quá gần đầu (dưới min_left) -> cắt sát trần, nhưng vẫn không được
    lọt giữa cặp chồng lấn kiểu "cho | đến khi"."""
    from vieneu_utils.core_utils import _tokenize_keep_en, _conn_key, _CONN_PAIRS
    sent = ("cho đến khi " * 30).strip()
    chunks = pack_sentences_into_chunks([sent], max_chars=40)
    assert " ".join(chunks).split() == sent.split()
    for left, right in zip(chunks, chunks[1:]):
        lt, rt = _tokenize_keep_en(left), _tokenize_keep_en(right)
        assert (_conn_key(lt[-1]), _conn_key(rt[0])) not in _CONN_PAIRS

def test_forced_word_cut_connector_too_early_is_ignored():
    """Từ nối làm mảnh trái < max_chars//2 thì bỏ qua, cắt sát trần như cũ."""
    sent = "x" * 10 + " và " + "y" * 30
    chunks = pack_sentences_into_chunks([sent], max_chars=40)
    assert chunks[0] == "x" * 10 + " và"

def test_forced_word_cut_no_connector_falls_back():
    """Không có từ nối: giữ nguyên hành vi cắt theo từ, không mất chữ."""
    words = ["a" * 15, "b" * 15, "c" * 15, "d" * 15]
    sent = " ".join(words)
    chunks = pack_sentences_into_chunks([sent], max_chars=35)
    assert all(len(c) <= 35 for c in chunks)
    assert " ".join(chunks).split() == words

def test_forced_word_cut_keeps_en_token_intact():
    sent = "x" * 30 + " và <en>hello world</en> " + "y" * 20
    chunks = pack_sentences_into_chunks([sent], max_chars=40)
    assert any("<en>hello world</en>" in c for c in chunks)
    assert not any("<en>hello" in c and "world</en>" not in c for c in chunks)

def test_chunking_cuts_at_sentence_boundary_not_mid_quote():
    """Regression: cắt ở ranh giới câu, không đẻ ra mảnh vụn mở đầu bằng dấu phẩy."""
    text = (
        "Nghe anh chia sẻ mà em thấy như đang nói trúng tim đen của chính mình và "
        "rất nhiều bạn bè xung quanh vậy. Có phải ý anh là cái cảm giác khi mình "
        "đạt được KPI, hoàn thành một mục tiêu to tát, nhận được những lời khen "
        "ngợi từ sếp hay đồng nghiệp, nhưng thay vì thấy hạnh phúc thì trong lòng "
        'lại trống rỗng, kiểu như: "Rồi sao nữa? Mình phải tiếp tục vòng quay này '
        'đến bao giờ?", đúng không anh?'
    )
    assert len(text) > 384
    chunks = split_text_into_chunks(text, max_chars=384)
    assert len(chunks) == 2
    assert chunks[0].endswith("xung quanh vậy.")
    assert chunks[1].startswith("Có phải ý anh")
    assert not any(c.lstrip().startswith(",") for c in chunks)

# --- Audio Utils Tests ---

def test_linear_overlap_add():
    # Create two overlapping frames
    frame_len = 100
    stride = 50
    frame1 = np.ones(frame_len, dtype=np.float32)
    frame2 = np.ones(frame_len, dtype=np.float32)

    frames = [frame1, frame2]
    out = _linear_overlap_add(frames, stride)

    # Total length should be stride * (len(frames) - 1) + frame_len = 50 * 1 + 100 = 150
    assert out.shape == (150,)
    assert np.any(out != 0)
    # With all ones and linear OLA, the result should be close to 1.0 where it overlaps
    assert np.allclose(out[50:100], 1.0)

def test_linear_overlap_add_empty():
    assert _linear_overlap_add([], 50).shape == (0,)

def test_join_audio_chunks_simple():
    chunks = [np.ones(100), np.zeros(100)]
    joined = join_audio_chunks(chunks, sr=16000)
    assert joined.shape == (200,)
    assert np.array_equal(joined[:100], np.ones(100))
    assert np.array_equal(joined[100:], np.zeros(100))

def test_join_audio_chunks_silence():
    chunks = [np.ones(100), np.ones(100)]
    sr = 16000
    silence_p = 0.1 # 0.1s * 16000 = 1600 samples
    joined = join_audio_chunks(chunks, sr=sr, silence_p=silence_p)
    assert joined.shape == (100 + 1600 + 100,)
    assert np.all(joined[100:1700] == 0)

def test_join_audio_chunks_crossfade():
    chunks = [np.ones(1000), np.zeros(1000)]
    sr = 16000
    crossfade_p = 0.01 # 0.01s * 16000 = 160 samples
    joined = join_audio_chunks(chunks, sr=sr, crossfade_p=crossfade_p)
    # Length should be 1000 + 1000 - 160 = 1840
    assert joined.shape == (1840,)
    assert joined[0] == 1.0
    assert joined[-1] == 0.0
    # Mid-point of crossfade should be 0.5
    assert np.allclose(joined[1000 - 80], 0.5, atol=0.01)

def test_join_audio_chunks_empty():
    assert join_audio_chunks([], 16000).shape == (0,)

def test_join_audio_chunks_single():
    chunk = np.ones(100)
    assert np.array_equal(join_audio_chunks([chunk], 16000), chunk)

def test_extract_speech_ids():
    codes_str = "<|speech_100|><|speech_101|><|speech_102|>"
    assert extract_speech_ids(codes_str) == [100, 101, 102]
    assert extract_speech_ids("no speech here") == []
    assert extract_speech_ids("<|speech_abc|>") == []

# --- Gộp chunk vụn (v3) ---

from vieneu_utils.phonemize_text import _merge_short_chunks
from vieneu_utils.core_utils import _FRAME_CAP_SLACK, max_expected_frames

LONG_A = "Đây là một chunk đủ dài để không bao giờ bị coi là vụn chút nào."
LONG_B = "Còn đây là một chunk dài khác cũng vượt xa ngưỡng tối thiểu rồi."


def test_merge_short_chunks_tiny_line_merges_into_next():
    """Dòng tiêu đề 1-2 từ dính vào nội dung theo sau, ranh giới para biến mất."""
    chunks, gaps = _merge_short_chunks(["Chương một.", LONG_A], ["para"], 20)
    assert chunks == [f"Chương một. {LONG_A}"]
    assert gaps == []


def test_merge_short_chunks_prefers_non_para_boundary():
    """Có lựa chọn thì gộp qua ranh giới KHÔNG phải ngắt đoạn."""
    chunks, gaps = _merge_short_chunks(
        [LONG_A, "Ừ.", LONG_B], ["sentence", "para"], 20
    )
    assert chunks == [f"{LONG_A} Ừ.", LONG_B]
    assert gaps == ["para"]


def test_merge_short_chunks_tie_prefers_right():
    chunks, gaps = _merge_short_chunks(
        [LONG_A, "Ừ.", LONG_A], ["para", "para"], 20
    )
    assert chunks == [LONG_A, f"Ừ. {LONG_A}"]
    assert gaps == ["para"]


def test_merge_short_chunks_cascades_until_big_enough():
    chunks, gaps = _merge_short_chunks(
        ["Một.", "Hai.", "Ba."], ["sentence", "sentence"], 20
    )
    assert chunks == ["Một. Hai. Ba."]
    assert gaps == []


def test_merge_short_chunks_leaves_long_chunks_alone():
    chunks, gaps = _merge_short_chunks([LONG_A, LONG_B], ["para"], 20)
    assert chunks == [LONG_A, LONG_B]
    assert gaps == ["para"]


def test_merge_short_chunks_single_chunk_untouched():
    chunks, gaps = _merge_short_chunks(["Ừ."], [], 20)
    assert chunks == ["Ừ."]


def test_merge_short_chunks_emotion_token_does_not_count_as_text():
    """`<|emotion_3|> Dạ.` dài 17 ký tự nhưng chỉ có 1 từ thật -> vẫn là vụn."""
    chunks, _ = _merge_short_chunks(["<|emotion_3|> Dạ.", LONG_A], ["para"], 20)
    assert chunks == [f"<|emotion_3|> Dạ. {LONG_A}"]

# --- Trần frame theo độ dài phoneme ---

def test_max_expected_frames_monotonic_and_bounded():
    # > 4 tiếng: ra khỏi vùng trần theo số tiếng (SYLLABLE_CAP_MAX_SYL), dùng công thức.
    short = max_expected_frames("aaa bbb ccc ddd eee")
    long = max_expected_frames("aaa bbb ccc " * 30)
    assert _FRAME_CAP_SLACK < short < long
    # Chunk dài hết cỡ (max_chars=256 -> phoneme ~300+) phải vượt default 300
    # để trần không bao giờ bó chunk bình thường.
    assert long > 300


def test_max_expected_frames_single_word_hard_cap():
    """Một từ duy nhất -> chặn cứng ~1 giây (13 frame @ 12.5 fps)."""
    from vieneu_utils.core_utils import SINGLE_WORD_MAX_FRAMES
    assert max_expected_frames("tʃˈaː2w.") == SINGLE_WORD_MAX_FRAMES
    assert max_expected_frames("") == SINGLE_WORD_MAX_FRAMES
    # Hai từ -> quay lại công thức tuyến tính.
    assert max_expected_frames("tʃˈaː2w bˈaː6n.") > SINGLE_WORD_MAX_FRAMES
    # Emotion cue tốn frame thật (cười/thở dài) -> không áp chặn cứng.
    assert max_expected_frames("<|emotion_1|>tʃˈaː2w.") > SINGLE_WORD_MAX_FRAMES
    # "Từ" dài bất thường (normalize dính) -> công thức thường lo.
    assert max_expected_frames("a" * 30) > SINGLE_WORD_MAX_FRAMES


def test_max_expected_frames_ignores_markup():
    assert max_expected_frames("<en>abc def</en>") == max_expected_frames("abc def")
    assert max_expected_frames("<en>ab cd</en> ef") == max_expected_frames("ab cd ef")
