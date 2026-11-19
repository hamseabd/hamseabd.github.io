"""Tests for check_links. Run: .venv/bin/python -m pytest scripts"""

from pathlib import Path

import pytest

from check_links import broken_links, internal_target, parse_page

BASE = "https://example.test/"


def build_site(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def test_parse_page_reads_unquoted_minified_attributes() -> None:
    page = parse_page("<a href=/posts/>x</a><link rel=icon href=https://example.test/favicon.ico>")
    assert page.links == ["/posts/", "https://example.test/favicon.ico"]


def test_parse_page_reads_src_and_every_srcset_candidate() -> None:
    page = parse_page('<img src="/a.png" srcset="/a-1x.png 1x, /a-2x.png 2x"><script src=/app.js></script>')
    assert page.links == ["/a.png", "/a-1x.png", "/a-2x.png", "/app.js"]


def test_parse_page_collects_ids_and_named_anchors() -> None:
    page = parse_page('<h2 id="why">Why</h2><a name=top></a>')
    assert page.anchors == {"why", "top"}


@pytest.mark.parametrize(
    "url",
    ["https://github.com/x", "//cdn.test/x.js", "mailto:a@b.c", "tel:1", "javascript:void(0)", "data:image/png;base64,AA"],
)
def test_link_that_leaves_the_site_is_not_internal(url: str) -> None:
    assert internal_target(url, "index.html", BASE) is None


def test_absolute_link_under_the_base_url_is_internal() -> None:
    assert internal_target("https://example.test/posts/a/#why", "index.html", BASE) == ("posts/a/", "why")


def test_root_relative_and_relative_links_resolve_from_the_page() -> None:
    assert internal_target("/resume.pdf", "posts/a/index.html", BASE) == ("resume.pdf", "")
    assert internal_target("../b/", "posts/a/index.html", BASE) == ("posts/b/", "")


def test_fragment_only_link_targets_its_own_page() -> None:
    assert internal_target("#top", "posts/a/index.html", BASE) == ("posts/a/index.html", "top")


def test_query_string_and_percent_encoding_are_dropped() -> None:
    assert internal_target("/a%20b.png?v=1", "index.html", BASE) == ("a b.png", "")


def test_clean_site_has_no_broken_links(tmp_path: Path) -> None:
    root = build_site(
        tmp_path,
        {
            "index.html": '<a href="/posts/">p</a><a href="/posts/#list">l</a><img src=/a.png>',
            "posts/index.html": '<ul id=list></ul><a href="https://example.test/">home</a>',
            "a.png": "",
        },
    )
    assert broken_links(root, BASE) == (4, [])


def test_missing_file_and_missing_anchor_are_reported_with_their_page(tmp_path: Path) -> None:
    root = build_site(
        tmp_path,
        {
            "index.html": '<a href="/search/">s</a><link rel=icon href=/favicon.ico><a href="/posts/#gone">g</a>',
            "posts/index.html": "<h1 id=here>x</h1>",
        },
    )
    _, broken = broken_links(root, BASE)
    assert broken == [
        ("index.html", "/favicon.ico", "no such file"),
        ("index.html", "/posts/#gone", "no such anchor"),
        ("index.html", "/search/", "no such file"),
    ]


def test_directory_without_an_index_page_is_broken(tmp_path: Path) -> None:
    root = build_site(tmp_path, {"index.html": '<a href="/empty/">e</a>', "empty/other.txt": ""})
    _, broken = broken_links(root, BASE)
    assert broken == [("index.html", "/empty/", "no such file")]
