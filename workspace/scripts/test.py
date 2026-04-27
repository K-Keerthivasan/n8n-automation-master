from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re, json

CAT_RE = re.compile(r"^\s*(\d+)\s*:\s*(.+?)\s*$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")

def parse_categories_block(lines: List[str], start_i: int) -> Tuple[List[str], int]:
    cats = []
    i = start_i
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if ISO_RE.match(line):
            break
        m = CAT_RE.match(line)
        if not m:
            break
        cats.append(m.group(2).strip())
        i += 1
    return cats, i

def is_item_row(line: str) -> bool:
    # In your data, each item row is tab-separated and starts with creator name
    return "\t" in line and len(line.split("\t")) >= 8

def parse_n8n_rss_text(raw: str) -> List[Dict[str, Any]]:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [ln.rstrip("\n") for ln in raw.split("\n")]

    # Remove the header block (lines that are just field names)
    # We skip until we hit the first TSV "item row"
    i = 0
    while i < len(lines) and not is_item_row(lines[i].strip()):
        i += 1

    items: List[Dict[str, Any]] = []

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not is_item_row(line):
            i += 1
            continue

        cols = line.split("\t")

        item: Dict[str, Any] = {
            "creator": cols[0].strip() if len(cols) > 0 else None,
            "title": cols[1].strip() if len(cols) > 1 else None,
            "link": cols[2].strip() if len(cols) > 2 else None,
            "pubDate": cols[3].strip() if len(cols) > 3 else None,
            "dc:creator": cols[4].strip() if len(cols) > 4 else None,
            "comments": cols[5].strip() if len(cols) > 5 else None,
            "content": cols[6].strip() if len(cols) > 6 else None,
            "contentSnippet": cols[7].strip() if len(cols) > 7 else None,
            "guid": cols[8].strip() if len(cols) > 8 else None,
        }

        i += 1

        # Skip blanks
        while i < len(lines) and not lines[i].strip():
            i += 1

        # Categories
        cats, i = parse_categories_block(lines, i)
        item["categories"] = cats

        # Skip blanks
        while i < len(lines) and not lines[i].strip():
            i += 1

        # isoDate
        if i < len(lines) and ISO_RE.match(lines[i].strip()):
            item["isoDate"] = lines[i].strip()
            i += 1
        else:
            item["isoDate"] = None

        items.append(item)

    return items

if __name__ == "__main__":
    RAW_TEXT = """PASTE_YOUR_FULL_RAW_TEXT_HERE"""

    data = parse_n8n_rss_text(RAW_TEXT)

    # IMPORTANT: print the whole list as JSON so n8n captures all items
    print(json.dumps(data, ensure_ascii=False))
