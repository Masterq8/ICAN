from __future__ import annotations

import pytest
from pydantic import ValidationError

from ican.retrieval.schema import SearchFilters, SearchRequest


def test_search_request_strips_query_and_accepts_safe_filters():
    request = SearchRequest(
        query="  Swin-T window size  ",
        collection="swin_v1",
        filters=SearchFilters(source_types=["config"], path_prefixes=["configs/swin/"]),
    )

    assert request.query == "Swin-T window size"
    assert request.limit == 5


@pytest.mark.parametrize(
    "prefix", ["../x", "C:/x", "\\\\server\\x", "configs\\swin", "", "/etc"]
)
def test_search_filters_reject_unsafe_path_prefix(prefix):
    with pytest.raises(ValidationError):
        SearchFilters(path_prefixes=[prefix])


@pytest.mark.parametrize("value", ["", " " * 10, "x" * 4097])
def test_search_request_rejects_blank_or_oversized_query(value):
    with pytest.raises(ValidationError):
        SearchRequest(query=value, collection="swin_v1")


@pytest.mark.parametrize("limit", [0, 21])
def test_search_request_rejects_out_of_range_limit(limit):
    with pytest.raises(ValidationError):
        SearchRequest(query="x", collection="swin_v1", limit=limit)
