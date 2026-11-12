import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from vieneu_utils.docx_extract import MAX_XML_BYTES, DocxError, extract_docx

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def make_docx(body: str, pages: int | None = None, document: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        if document:
            z.writestr("word/document.xml", f'<w:document {NS}><w:body>{body}</w:body></w:document>')
        if pages is not None:
            z.writestr(
                "docProps/app.xml",
                '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                f"<Pages>{pages}</Pages></Properties>",
            )
    return buf.getvalue()


def p(*runs: str) -> str:
    return "<w:p>" + "".join(runs) + "</w:p>"


def r(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def test_paragraphs_keep_word_boundaries():
    # Word hay tách một câu thành nhiều run (đổi định dạng giữa chừng).
    text, _ = extract_docx(make_docx(p(r("Học sinh "), r("nhận"), r(" SGK.")) + p(r("Đoạn hai."))))
    assert text == "Học sinh nhận SGK.\n\nĐoạn hai."


def test_empty_paragraphs_and_extra_spaces_dropped():
    text, _ = extract_docx(make_docx(p() + p(r("  Một   hai  ")) + p(r("   "))))
    assert text == "Một hai"


def test_tab_break_and_hyperlink():
    body = p(
        r("A"), "<w:r><w:tab/></w:r>", r("B"), "<w:r><w:br/></w:r>",
        '<w:hyperlink><w:r><w:t>liên kết</w:t></w:r></w:hyperlink>',
    )
    assert extract_docx(make_docx(body))[0] == "A B\nliên kết"


def test_tracked_changes_keep_insert_drop_delete():
    body = p(
        r("Giữ "),
        "<w:ins><w:r><w:t>chèn</w:t></w:r></w:ins>",
        "<w:del><w:r><w:delText>xoá</w:delText></w:r></w:del>",
    )
    assert extract_docx(make_docx(body))[0] == "Giữ chèn"


def test_textbox_skipped():
    body = p(
        r("Chính văn"),
        "<w:r><w:drawing><w:txbxContent>" + p(r("hộp chữ")) + "</w:txbxContent></w:drawing></w:r>",
    )
    assert extract_docx(make_docx(body))[0] == "Chính văn"


def test_table_rows_and_nested_table_not_duplicated():
    inner = "<w:tbl><w:tr><w:tc>" + p(r("lồng")) + "</w:tc></w:tr></w:tbl>"
    table = (
        "<w:tbl>"
        "<w:tr><w:tc>" + p(r("Tên")) + "</w:tc><w:tc>" + p(r("Tuổi")) + "</w:tc></w:tr>"
        "<w:tr><w:tc>" + p(r("An")) + inner + "</w:tc><w:tc>" + p(r("20")) + "</w:tc></w:tr>"
        "</w:tbl>"
    )
    text, _ = extract_docx(make_docx(p(r("Trước")) + table + p(r("Sau"))))
    assert text == "Trước\n\nTên, Tuổi\n\nAn lồng, 20\n\nSau"


def test_content_control():
    body = "<w:sdt><w:sdtContent>" + p(r("Trong khung")) + "</w:sdtContent></w:sdt>"
    assert extract_docx(make_docx(body))[0] == "Trong khung"


def test_page_count_from_app_xml():
    assert extract_docx(make_docx(p(r("x")), pages=7))[1] == 7
    assert extract_docx(make_docx(p(r("x"))))[1] == 0


@pytest.mark.parametrize(
    "data",
    [b"not a zip", make_docx("", document=False)],
)
def test_invalid_files_raise_vietnamese_error(data):
    with pytest.raises(DocxError):
        extract_docx(data)


def test_oversized_document_rejected(monkeypatch):
    import vieneu_utils.docx_extract as m

    monkeypatch.setattr(m, "MAX_XML_BYTES", 10)
    with pytest.raises(DocxError, match="quá lớn"):
        extract_docx(make_docx(p(r("dài hơn mười byte"))))
    assert MAX_XML_BYTES > 10


# ---------------------------------------------------------------- endpoint

@pytest.fixture
def client():
    from apps import web_stream as ws

    with TestClient(ws.app) as c:
        yield c


def upload(client, name, data):
    return client.post("/api/pdf/extract", files={"file": (name, data)})


def test_endpoint_docx(client):
    res = upload(client, "Bài học.DOCX", make_docx(p(r("Xin chào.")) + p(r("Tạm biệt.")), pages=2))
    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "Xin chào.\n\nTạm biệt."
    assert body["page_count"] == 2
    assert body["filename"] == "Bài học.DOCX"


def test_endpoint_doc_explains_how_to_convert(client):
    res = upload(client, "cu.doc", b"\xd0\xcf\x11\xe0")
    assert res.status_code == 415
    assert ".docx" in res.json()["detail"]


def test_endpoint_bad_or_empty_docx(client):
    assert upload(client, "hong.docx", b"xyz").status_code == 400
    empty = upload(client, "trong.docx", make_docx(p()))
    assert empty.status_code == 400
    assert "không có chữ" in empty.json()["detail"]
