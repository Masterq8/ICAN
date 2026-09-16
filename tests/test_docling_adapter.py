from types import SimpleNamespace

from docling_core.types.doc import BoundingBox, CoordOrigin

from ican.ingestion.docling_adapter import adapt_document


def provenance(page, start, end, box):
    return SimpleNamespace(
        page_no=page,
        charspan=(start, end),
        bbox=BoundingBox(
            l=box[0], t=box[1], r=box[2], b=box[3], coord_origin=CoordOrigin.BOTTOMLEFT
        ),
    )


class Document:
    def __init__(self, item, fail_page=None):
        self.pages = {
            p: SimpleNamespace(size=SimpleNamespace(width=600, height=800))
            for p in (1, 2)
        }
        self.item, self.fail_page = item, fail_page

    def iterate_items(self, page_no=None):
        if self.fail_page is not None and page_no == self.fail_page:
            raise ValueError("page-local failure")
        if page_no is None or any(p.page_no == page_no for p in self.item.prov):
            yield self.item, 0


def item(prov):
    return SimpleNamespace(
        orig="first page second page",
        text="first page second page",
        self_ref="#/texts/0",
        label=SimpleNamespace(value="text"),
        prov=prov,
    )


def test_cross_page_text_uses_character_provenance():
    doc = Document(
        item(
            [
                provenance(1, 0, 10, [10, 700, 150, 680]),
                provenance(2, 11, 22, [20, 700, 180, 680]),
            ]
        )
    )
    units, issues = adapt_document(
        doc, source_id="p", relative_path="p.pdf", version="v"
    )
    assert not issues
    assert [u.text for u in units] == ["first page", "second page"]
    assert units[0].structures[0].bbox == [10, 100, 150, 120]


def test_same_page_multiple_boxes_are_retained():
    doc = Document(
        item(
            [
                provenance(1, 0, 10, [10, 700, 150, 680]),
                provenance(1, 11, 22, [20, 600, 180, 580]),
            ]
        )
    )
    units, _ = adapt_document(doc, source_id="p", relative_path="p.pdf", version="v")
    span = units[0].structures[0]
    assert len(span.metadata["provenance_bboxes"]) == 2
    assert span.bbox == [10, 100, 180, 220]


def test_page_failure_preserves_earlier_pages():
    doc = Document(
        item(
            [
                provenance(1, 0, 10, [10, 700, 150, 680]),
                provenance(2, 11, 22, [20, 700, 180, 680]),
            ]
        ),
        fail_page=2,
    )
    units, issues = adapt_document(
        doc, source_id="p", relative_path="p.pdf", version="v"
    )
    assert len(units) == 1 and units[0].page == 1
    assert issues[0]["code"] == "pdf_page_failed" and issues[0]["page"] == 2


def test_missing_and_orphan_provenance_are_reported():
    for prov, code in [
        ([], "missing_provenance"),
        ([provenance(3, 0, 10, [10, 700, 150, 680])], "orphan_provenance"),
    ]:
        doc = Document(item(prov))
        _, issues = adapt_document(
            doc, source_id="p", relative_path="p.pdf", version="v"
        )
        assert issues[0]["code"] == code
