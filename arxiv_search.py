#!/usr/bin/env python3
"""
arxiv_search.py — minimal arXiv API search client.

Outputs JSON Lines (one JSON object per paper) containing:
  - title
  - published (ISO 8601 string from <published>)
  - url (abstract page URL)
  - abstract

Docs:
  - Query endpoint: http://export.arxiv.org/api/query
  - Params: search_query, id_list, start, max_results, sortBy, sortOrder
  - Be nice when paging (sleep between requests)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

import requests
import feedparser
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


ARXIV_API_URL = "http://export.arxiv.org/api/query"

# arXiv docs note max_results is limited (large queries should be sliced).
# We'll enforce conservative safety: max_results per request <= 2000, total <= 30000.
MAX_RESULTS_PER_REQUEST = 2000
MAX_TOTAL_RESULTS = 30000


@dataclass(frozen=True)
class ArxivRecord:
    title: str
    published: str
    url: str
    abstract: str

    def to_json(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "published": self.published,
            "url": self.url,
            "abstract": self.abstract,
        }


def _clean_ws(s: str) -> str:
    # Collapse whitespace and trim.
    return " ".join((s or "").split()).strip()


def _wrap_text_as_lines(text: str, width: int = 80) -> List[str]:
    """Wrap text to specified width and return as list of lines for readable JSON."""
    if not text:
        return []
    return textwrap.wrap(text, width=width)


def build_query_url(
    *,
    search_query: Optional[str],
    id_list: Optional[List[str]],
    start: int,
    max_results: int,
    sort_by: Optional[str],
    sort_order: Optional[str],
) -> str:
    params: Dict[str, Any] = {
        "start": start,
        "max_results": max_results,
    }
    if search_query:
        params["search_query"] = search_query
    if id_list:
        params["id_list"] = ",".join(id_list)
    if sort_by:
        params["sortBy"] = sort_by
    if sort_order:
        params["sortOrder"] = sort_order

    return f"{ARXIV_API_URL}?{urlencode(params)}"


def fetch_feed(url: str, *, timeout_s: int = 30, user_agent: str = "arxiv_search.py/1.0") -> feedparser.FeedParserDict:
    # arXiv returns Atom (XML). feedparser handles parsing.
    headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def parse_records(feed: feedparser.FeedParserDict) -> List[ArxivRecord]:
    records: List[ArxivRecord] = []
    for entry in feed.entries:
        # Entry metadata per arXiv Atom output:
        # - <title> is entry.title
        # - <published> is entry.published
        # - <summary> is entry.summary
        # - <id> is the abstract URL (e.g., http://arxiv.org/abs/...)
        title = _clean_ws(getattr(entry, "title", ""))
        published = _clean_ws(getattr(entry, "published", ""))

        # Prefer the <id> as the canonical abstract URL; fallback to alternate link if needed.
        url = _clean_ws(getattr(entry, "id", ""))
        if not url:
            for link in getattr(entry, "links", []) or []:
                if (link.get("rel") == "alternate") and link.get("href"):
                    url = _clean_ws(link["href"])
                    break

        abstract = _clean_ws(getattr(entry, "summary", ""))

        # Skip empty entries defensively.
        if title or url or abstract or published:
            records.append(ArxivRecord(title=title, published=published, url=url, abstract=abstract))
    return records


def generate_summary(abstract: str, client: OpenAI) -> str:
    """Send an abstract to GPT-5.2 and get a plain-English summary."""
    if not abstract.strip():
        return "No abstract available."
    response = client.responses.create(
        model="gpt-5.2",
        input=[{
            "role": "user",
            "content": (
                "Read the following scientific abstract and write a short, "
                "plain English explanation of what the paper is about. "
                "Keep it to 2-3 sentences, avoiding jargon:\n\n"
                f"{abstract}"
            ),
        }],
    )
    return response.output_text.strip()


def summarize_records(records: List[ArxivRecord]) -> List[str]:
    """Generate plain-English summaries for a list of ArxivRecords.

    Returns a list of summary strings aligned by index with *records*.
    Individual failures produce a fallback string so one bad call
    doesn't crash the entire run.
    """
    client = OpenAI()
    summaries: List[str] = []
    total = len(records)
    for i, rec in enumerate(records, 1):
        print(f"  Generating summary {i}/{total}...", file=sys.stderr)
        try:
            summaries.append(generate_summary(rec.abstract, client))
        except Exception as exc:
            print(f"  Warning: summary failed for record {i}: {exc}", file=sys.stderr)
            summaries.append("Summary unavailable.")
    return summaries


def _format_record_for_output(
    rec: ArxivRecord,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a record with wrapped abstract for readable output."""
    out: Dict[str, Any] = {
        "title": rec.title,
        "published": rec.published,
        "url": rec.url,
        "abstract": _wrap_text_as_lines(rec.abstract, width=80),
    }
    if summary is not None:
        out["plain_english_summary"] = _wrap_text_as_lines(summary, width=80)
    return out


def _get_daily_dir(base_dir: str) -> Path:
    """Return today's date-based subdirectory, creating it if needed."""
    today = datetime.now().strftime("%Y-%m-%d")
    daily_dir = Path(base_dir) / "searches" / today
    daily_dir.mkdir(parents=True, exist_ok=True)
    return daily_dir


def _build_output(
    records: List[ArxivRecord],
    *,
    search_query: Optional[str],
    id_list: Optional[List[str]],
    max_results: int,
    start: int,
    sort_by: Optional[str],
    sort_order: Optional[str],
    summaries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build the full output dict with query parameters and results."""
    results = []
    for i, rec in enumerate(records):
        summary = summaries[i] if summaries else None
        results.append(_format_record_for_output(rec, summary=summary))

    return {
        "query_parameters": {
            "search_query": search_query,
            "id_list": id_list,
            "max_results": max_results,
            "start": start,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        "search_metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_results": len(records),
        },
        "results": results,
    }


def save_search_results(
    records: List[ArxivRecord],
    *,
    search_query: Optional[str],
    id_list: Optional[List[str]],
    max_results: int,
    start: int,
    sort_by: Optional[str],
    sort_order: Optional[str],
    summaries: Optional[List[str]] = None,
    output_dir: str = ".",
) -> str:
    """
    Save search results to a timestamped JSON file inside today's date folder.
    
    Returns the path to the created file.
    """
    daily_dir = _get_daily_dir(output_dir)
    timestamp = datetime.now().strftime("%H-%M-%S")
    filename = f"arxiv_search_{timestamp}.json"
    filepath = daily_dir / filename

    output = _build_output(
        records,
        search_query=search_query,
        id_list=id_list,
        max_results=max_results,
        start=start,
        sort_by=sort_by,
        sort_order=sort_order,
        summaries=summaries,
    )
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    return str(filepath)


def iter_search(
    *,
    search_query: Optional[str],
    id_list: Optional[List[str]],
    max_total: int,
    start: int,
    chunk_size: int,
    sort_by: Optional[str],
    sort_order: Optional[str],
    delay_s: float,
    timeout_s: int,
    user_agent: str,
) -> Iterable[ArxivRecord]:
    remaining = max_total
    current_start = start

    while remaining > 0:
        this_chunk = min(chunk_size, remaining)
        url = build_query_url(
            search_query=search_query,
            id_list=id_list,
            start=current_start,
            max_results=this_chunk,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        feed = fetch_feed(url, timeout_s=timeout_s, user_agent=user_agent)

        # If arXiv returns an error feed, feedparser may still parse it.
        # A simple heuristic: if there are no entries, stop.
        records = parse_records(feed)
        if not records:
            break

        for r in records:
            yield r

        # Stop early if fewer results returned than requested.
        if len(records) < this_chunk:
            break

        remaining -= this_chunk
        current_start += this_chunk

        if remaining > 0 and delay_s > 0:
            time.sleep(delay_s)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Search arXiv API and output title, published date, URL, abstract (JSONL).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    q = p.add_mutually_exclusive_group(required=True)
    q.add_argument(
        "--search-query",
        help='arXiv API search_query string (e.g., \'all:electron AND cat:cs.LG\')',
    )
    q.add_argument(
        "--id-list",
        help="Comma-separated arXiv IDs to fetch (e.g., '1707.08567,hep-th/9901001v2')",
    )

    p.add_argument("--start", type=int, default=0, help="0-based start index for paging")
    p.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Total number of results to retrieve across all pages",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=200,
        help="Results per request (paging size)",
    )

    p.add_argument(
        "--sort-by",
        choices=["relevance", "lastUpdatedDate", "submittedDate"],
        default=None,
        help="Sort criterion (optional)",
    )
    p.add_argument(
        "--sort-order",
        choices=["ascending", "descending"],
        default=None,
        help="Sort order (optional)",
    )

    p.add_argument(
        "--delay-seconds",
        type=float,
        default=3.0,
        help="Delay between paged requests (set to 0 to disable)",
    )
    p.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout")
    p.add_argument(
        "--user-agent",
        default="arxiv_search.py/1.0 (+https://example.com; mailto:you@example.com)",
        help="User-Agent header (put a real contact URL/email in here for good citizenship)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output file path (if not specified, auto-generates timestamped file)",
    )
    p.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save auto-generated output files",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Print raw JSONL to stdout instead of saving to file",
    )
    p.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip GPT-powered plain-English summary generation (requires OPENAI_API_KEY)",
    )

    args = p.parse_args(argv)

    # Validate/enforce safe limits consistent with arXiv guidance.
    if args.start < 0:
        p.error("--start must be >= 0")

    if args.max_results < 0:
        p.error("--max-results must be >= 0")

    if args.max_results > MAX_TOTAL_RESULTS:
        p.error(f"--max-results too large; must be <= {MAX_TOTAL_RESULTS}")

    if args.chunk_size <= 0:
        p.error("--chunk-size must be > 0")

    if args.chunk_size > MAX_RESULTS_PER_REQUEST:
        p.error(f"--chunk-size too large; must be <= {MAX_RESULTS_PER_REQUEST}")

    config_marker = Path(__file__).resolve().parent / ".configured"
    if not config_marker.exists():
        print(
            "Error: workspace has not been configured.\n"
            "Run 'python configure.py' before searching. See README for details.",
            file=sys.stderr,
        )
        return 1

    search_query = args.search_query
    id_list = None
    if args.id_list:
        id_list = [s.strip() for s in args.id_list.split(",") if s.strip()]

    # Collect all records
    print(f"Searching arXiv...", file=sys.stderr)
    records: List[ArxivRecord] = list(iter_search(
        search_query=search_query,
        id_list=id_list,
        max_total=args.max_results,
        start=args.start,
        chunk_size=args.chunk_size,
        sort_by=args.sort_by,
        sort_order=args.sort_order,
        delay_s=args.delay_seconds,
        timeout_s=args.timeout_seconds,
        user_agent=args.user_agent,
    ))

    # Generate plain-English summaries unless opted out.
    summaries: Optional[List[str]] = None
    if not args.no_summarize and records:
        print(f"\nGenerating plain-English summaries with GPT-5.2...", file=sys.stderr)
        summaries = summarize_records(records)

    if args.stdout:
        for rec_idx, rec in enumerate(records):
            obj = rec.to_json()
            if summaries is not None:
                obj["plain_english_summary"] = summaries[rec_idx]
            print(json.dumps(obj, ensure_ascii=False))
    else:
        query_kwargs = dict(
            search_query=search_query,
            id_list=id_list,
            max_results=args.max_results,
            start=args.start,
            sort_by=args.sort_by,
            sort_order=args.sort_order,
        )
        if args.output:
            output = _build_output(records, **query_kwargs, summaries=summaries)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            filepath = args.output
        else:
            filepath = save_search_results(
                records, **query_kwargs, summaries=summaries, output_dir=args.output_dir,
            )
        
        # Print summary to terminal
        print(f"\nSearch complete!", file=sys.stderr)
        print(f"  Results found: {len(records)}", file=sys.stderr)
        print(f"  Saved to: {filepath}", file=sys.stderr)
        
        if records:
            print(f"\nFirst 5 results:", file=sys.stderr)
            for i, rec in enumerate(records[:5], 1):
                # Truncate title if too long
                title = rec.title[:80] + "..." if len(rec.title) > 80 else rec.title
                print(f"  {i}. {title}", file=sys.stderr)
                print(f"     Published: {rec.published[:10] if rec.published else 'N/A'}", file=sys.stderr)
            if len(records) > 5:
                print(f"  ... and {len(records) - 5} more", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
