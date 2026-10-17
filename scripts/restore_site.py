#!/usr/bin/env python3
"""Download archived URLs for a hostname from the Wayback Machine."""

import argparse
from collections import deque
import hashlib
import json
from html.parser import HTMLParser
from http.client import HTTPException
import posixpath
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urldefrag, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_URL = "https://web.archive.org/web"
USER_AGENT = "oldwebsites-restorer/1.0"
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def normalized_url(url: str) -> str:
    return urldefrag(url)[0]


def local_path(url: str) -> Path:
    parts = urlsplit(url)
    path = posixpath.normpath("/" + unquote(parts.path)).lstrip("/")
    if path in ("", ".") or parts.path.endswith("/"):
        path = posixpath.join(path, "index.html")
    elif not Path(path).suffix:
        path = posixpath.join(path, "index.html")
    if parts.query:
        suffix = Path(path).suffix
        path = f"{path[:-len(suffix)] if suffix else path}_{hashlib.sha256(parts.query.encode()).hexdigest()[:8]}{suffix}"
    return Path(parts.netloc) / Path(path)


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name.lower() in {"href", "src", "poster", "data-src", "action"}:
                self.references.append(value)
            elif name.lower() == "srcset":
                self.references.extend(item.strip().split()[0] for item in value.split(",") if item.strip())
            elif name.lower() == "style":
                self.references.extend(match.group(2) for match in CSS_URL.finditer(value))


def extract_references(content: bytes, content_type: str) -> list[str]:
    text = content.decode("utf-8", errors="replace")
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = ReferenceParser()
        parser.feed(text)
        references = parser.references
    elif content_type == "text/css":
        references = [match.group(2) for match in CSS_URL.finditer(text)]
    else:
        return []
    return [reference for reference in references if reference and not reference.startswith(("#", "data:", "javascript:", "mailto:", "tel:"))]


def rewrite_references(content: bytes, content_type: str, source_url: str, mapping: dict[str, str]) -> bytes:
    if not mapping:
        return content
    text = content.decode("utf-8", errors="replace")
    source_file = local_path(source_url)
    for original, target_file in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        relative = posixpath.relpath(target_file.as_posix(), source_file.parent.as_posix())
        text = text.replace(original, quote(relative, safe="/.:@-_%"))
    return text.encode("utf-8")


def save_stream(response, output_path: Path) -> None:
    temporary_path = output_path.with_name(output_path.name + ".part")
    try:
        with temporary_path.open("wb") as output_file:
            while chunk := response.read(1024 * 1024):
                output_file.write(chunk)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def find_snapshot(url: str, year: int | None) -> tuple[str, str]:
    params = {
        "url": url,
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original",
        "collapse": "digest",
    }
    if year is not None:
        params["from"] = f"{year}0101"
        params["to"] = f"{year}1231"
    else:
        params["from"] = "2000"

    query = urlencode(params, doseq=True)
    request = Request(f"{CDX_URL}?{query}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        rows = json.loads(response.read().decode("utf-8"))

    if len(rows) < 2:
        requested = f" in {year}" if year is not None else " from 2000 onward"
        raise ValueError(f"No archived HTML snapshot found for {url}{requested}.")

    return max(rows[1:], key=lambda row: row[0])


def find_archived_urls(hostname: str, year: int) -> dict[str, str]:
    params = {
        "url": hostname,
        "matchType": "domain",
        "output": "json",
        "from": str(year),
        "to": str(year),
        "filter": "statuscode:200",
        "fl": "timestamp,original",
        "collapse": "urlkey",
    }
    query = urlencode(params)
    request = Request(f"{CDX_URL}?{query}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        rows = json.loads(response.read().decode("utf-8"))

    archived_urls = {}
    for row in rows[1:]:
        timestamp, original_url = row[:2]
        parts = urlsplit(original_url)
        if parts.scheme in {"http", "https"} and parts.hostname and parts.hostname.lower() == hostname.lower():
            archived_urls[normalized_url(original_url)] = timestamp
    if not archived_urls:
        raise ValueError(f"No archived URLs found for {hostname} in {year}.")
    return archived_urls


def download_site(
    url: str,
    output: Path,
    timestamp: str,
    archived_urls: dict[str, str],
    max_files: int | None,
) -> tuple[int, int]:
    start_url = normalized_url(url)
    hostname = urlsplit(start_url).hostname
    if hostname is None:
        raise ValueError(f"Invalid website URL: {url}")
    pending = deque([(start_url, timestamp)])
    queued = {start_url}
    downloaded: set[str] = set()
    failed = 0

    for archived_url, archived_timestamp in archived_urls.items():
        if archived_url == start_url or (max_files is not None and len(queued) >= max_files):
            continue
        queued.add(archived_url)
        pending.append((archived_url, archived_timestamp))

    while pending and (max_files is None or len(downloaded) < max_files):
        original_url, capture_timestamp = pending.popleft()
        target = local_path(original_url)
        output_path = output / target
        output_path.parent.mkdir(parents=True, exist_ok=True)
        replay_url = f"{WAYBACK_URL}/{capture_timestamp}id_/{original_url}"
        request = Request(replay_url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=60) as response:
                content_type = response.headers.get_content_type()
                if content_type in {"text/html", "application/xhtml+xml", "text/css"}:
                    content = response.read()
                else:
                    save_stream(response, output_path)
                    content = None
        except (HTTPError, URLError, HTTPException, TimeoutError, OSError) as error:
            print(f"Skipping {original_url}: {error}", file=sys.stderr)
            failed += 1
            continue

        mapping: dict[str, Path] = {}
        if content is not None:
            for reference in extract_references(content, content_type):
                resolved = normalized_url(urljoin(original_url, reference))
                parts = urlsplit(resolved)
                if parts.scheme not in {"http", "https"} or parts.hostname is None or parts.hostname.lower() != hostname.lower():
                    continue
                mapping[reference] = local_path(resolved)
                if resolved not in queued and (max_files is None or len(queued) < max_files):
                    queued.add(resolved)
                    pending.append((resolved, archived_urls.get(resolved, timestamp)))
            output_path.write_bytes(rewrite_references(content, content_type, original_url, mapping))
        downloaded.add(original_url)
        print(f"Saved {original_url} -> {output_path}")

    return len(downloaded), failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Website URL to look up in the Wayback Machine")
    parser.add_argument("--output", type=Path, default=Path("recovered"), help="Directory for the downloaded site")
    parser.add_argument("--year", type=int, help="Use a capture from this year (2000 or later)")
    parser.add_argument("--max-files", type=int, help="Optional maximum number of pages and assets to download")
    args = parser.parse_args()

    if args.year is not None and args.year < 2000:
        parser.error("--year must be 2000 or later")
    if args.max_files is not None and args.max_files < 1:
        parser.error("--max-files must be at least 1")

    try:
        timestamp, original_url = find_snapshot(args.url, args.year)
        hostname = urlsplit(original_url).hostname
        if hostname is None:
            raise ValueError(f"Invalid website URL: {original_url}")
        archive_year = args.year or int(timestamp[:4])
        archived_urls = find_archived_urls(hostname, archive_year)
        print(f"Found {len(archived_urls)} archived URLs for {hostname} in {archive_year}.")
        count, failed = download_site(original_url, args.output, timestamp, archived_urls, args.max_files)
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as error:
        print(f"restore_site: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"restore_site: {error}", file=sys.stderr)
        return 1

    if count == 0:
        print("restore_site: no files could be downloaded", file=sys.stderr)
        return 1
    print(f"Downloaded {count} file(s) from the {archive_year} archive inventory into {args.output}; {failed} failed.")
    if args.max_files is not None and count >= args.max_files:
        print("Download limit reached; this copy may be incomplete.", file=sys.stderr)
        return 1
    if failed:
        print("One or more archived URLs failed; this copy is incomplete.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())