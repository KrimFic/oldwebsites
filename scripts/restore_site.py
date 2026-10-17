#!/usr/bin/env python3
"""Save a Wayback Machine replay of a site's archived HTML page."""

import argparse
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_URL = "https://web.archive.org/web"
USER_AGENT = "oldwebsites-restorer/1.0"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Website URL to look up in the Wayback Machine")
    parser.add_argument("--output", type=Path, default=Path("recovered/index.html"))
    parser.add_argument("--year", type=int, help="Use a capture from this year (2000 or later)")
    args = parser.parse_args()

    if args.year is not None and args.year < 2000:
        parser.error("--year must be 2000 or later")

    try:
        timestamp, original_url = find_snapshot(args.url, args.year)
        replay_url = f"{WAYBACK_URL}/{timestamp}/{original_url}"
        request = Request(replay_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=60) as response:
            page = response.read()

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(page)
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as error:
        print(f"restore_site: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"restore_site: {error}", file=sys.stderr)
        return 1

    print(f"Saved {original_url} ({timestamp}) to {args.output}")
    print("This replay may load assets from web.archive.org and requires an internet connection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())