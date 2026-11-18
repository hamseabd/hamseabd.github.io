"""Check every internal link in a built site: pages, assets, and #anchors.

Usage: python3 scripts/check_links.py <built dir> <base URL>
Exits 1 when any internal link has no file or anchor behind it.
External links are not fetched.
"""

import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from posixpath import dirname, join, normpath
from urllib.parse import unquote, urlsplit

LINK_ATTRIBUTES = ("href", "src", "poster")


@dataclass
class Page:
    links: list[str] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.page = Page()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if not value:
                continue
            if name in LINK_ATTRIBUTES:
                self.page.links.append(value)
            elif name == "srcset":
                self.page.links.extend(candidate.split()[0] for candidate in value.split(",") if candidate.strip())
            elif name == "id" or (name == "name" and tag == "a"):
                self.page.anchors.add(value)


def parse_page(html: str) -> Page:
    parser = _PageParser()
    parser.feed(html)
    return parser.page


def internal_target(url: str, page_path: str, base_url: str) -> tuple[str, str] | None:
    """Map a link to (path inside the site, fragment), or None when it leaves the site."""
    if url.startswith(base_url):
        url = "/" + url[len(base_url) :]
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        return None
    fragment = unquote(parts.fragment)
    path = unquote(parts.path)
    if not path:
        return page_path, fragment
    if path.startswith("/"):
        resolved = normpath(path)
    else:
        resolved = normpath(join("/", dirname(page_path), path))
    resolved = resolved.lstrip("/")
    if path.endswith("/") and resolved:
        resolved += "/"
    return resolved, fragment


def _target_file(root: Path, path: str) -> Path | None:
    candidate = root / path
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.is_file() else None


def broken_links(root: Path, base_url: str) -> tuple[int, list[tuple[str, str, str]]]:
    """Return (internal links checked, sorted [(page, link, reason)])."""
    pages = {str(path.relative_to(root)): parse_page(path.read_text(errors="replace")) for path in root.rglob("*.html")}
    checked = 0
    broken = []
    for page_path, page in pages.items():
        for link in page.links:
            target = internal_target(link, page_path, base_url)
            if target is None:
                continue
            checked += 1
            path, fragment = target
            file = _target_file(root, path)
            if file is None:
                broken.append((page_path, link, "no such file"))
            elif fragment and fragment not in pages.get(str(file.relative_to(root)), Page()).anchors:
                broken.append((page_path, link, "no such anchor"))
    return checked, sorted(broken)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__ or "")
        return 2
    root, base_url = Path(argv[1]), argv[2].rstrip("/") + "/"
    if not root.is_dir():
        sys.stderr.write(f"not a directory: {root}\n")
        return 2
    checked, broken = broken_links(root, base_url)
    for page, link, reason in broken:
        sys.stdout.write(f"BROKEN {page}: {link} ({reason})\n")
    sys.stdout.write(f"{checked} internal links checked, {len(broken)} broken\n")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
