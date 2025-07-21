import os
import re
import json
import glob
import csv
from meilisearch import Client
from pathlib import Path
from collections import defaultdict

# CONFIG
CONFIG_PATH = "config.json"
MEILI_URL    = os.getenv("MEILI_URL", "http://0.0.0.0:7700")
MEILI_KEY    = os.getenv("MEILI_MASTER_KEY", "masterKey")
MEILI_INDEX  = "tenders"
# load your Russian stop-words for highlight-threshold
with open("russian.txt", encoding="utf-8") as f:
    STOPWORDS = set([w.strip().lower() for w in f if w.strip()])
    

def date_from_filename(filename):
    # expects 'merged_dd.mm.yyyy.csv'
    date_part = Path(filename).stem.split("_",1)[1]  # '20.05.2025'
    # convert to '2025-05-20'
    day, month, year = date_part.split(".")
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


# ----------------------------------------------------------------
def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def should_keep_document(highlight: str, threshold_percent: float = 70.0) -> bool:
    """
    Returns True if any <em>…</em> chunk in the highlight covers at least
    `threshold_percent` of its word.  Filters out matches on pure stopwords.
    """
    pattern = re.compile(r'(\w*)<em>(.*?)</em>(\w*)', re.UNICODE)
    for m in pattern.finditer(highlight):
        pre, hl, post = m.group(1), m.group(2), m.group(3)
        word = (pre + hl + post).lower()
        if not word or hl.lower() in STOPWORDS:
            continue
        coverage = (len(hl) / len(word)) * 100
        if coverage >= threshold_percent:
            return True
    return False

def collect_hits(index, terms, meili_filter, batch_size=10000):
    """
    For each term in `terms`, runs a Meili search with the given
    filter and returns two maps:
      docs_map:    tender_id -> full hit (all fields + _formatted)
      highlights:  tender_id -> list of raw formatted snippets
    """
    index.update_typo_tolerance({
        "minWordSizeForTypos": {"oneTypo": 5, "twoTypos": 8}
    })
    docs_map    = {}
    highlights  = defaultdict(list)

    for term in filter(None, terms):
        # if term is all-caps we wrap in quotes to force phrase match
        q = f'"{term}"' if term.isupper() else term
        resp = index.search(
            q,
            {
                "limit": batch_size,
                "matchingStrategy": "all",
                "filter": meili_filter,
                "attributesToRetrieve": ["*"],
                "attributesToHighlight": ["*"]
            }
        )
        for hit in resp.get("hits", []):
            tid = hit["tender_id"]
            docs_map[tid] = hit
            fmt = hit.get("_formatted", {})
            # collect any field that actually contains <em>…</em>
            for v in fmt.values():
                if "<em>" in v:
                    highlights[tid].append(v)
    return docs_map, highlights


def collect_hits_stopwords(index, stopwords, meili_filter, batch_size=10000):
    """
    For each stopword/phrase, runs an exact phrase search with maximum precision (no typo).
    Returns set of matching tender_ids to exclude.
    """
    index.update_typo_tolerance({
        "enabled": False
    })
    exclude_ids = set()
    for sw in filter(None, stopwords):
        # Wrap with quotes for exact phrase matching.
        q = f'"{sw}"'
        resp = index.search(
            q,
            {
                "limit": batch_size,
                "attributesToRetrieve": ["*"],
                "matchingStrategy": "last",   # for exact phrase; use "all" if not supported
                "filter": meili_filter
            }
        )
        for hit in resp.get("hits", []):
            exclude_ids.add(hit["tender_id"])
    return exclude_ids

# ----------------------------------------------------------------
def process_client(client, index, date_tag, publish_date):
    cid       = client["client_id"]
    tmpl      = client["template_id"]
    keywords  = [k.strip() for k in client.get("keywords","").split(",")]
    stopwords = [s.strip() for s in client.get("stopwords","").split(",")]
    fz44      = client.get("fz44", False)
    fz223     = client.get("fz223", False)
    min_p     = client.get("min_price")
    max_p     = client.get("max_price")

    # BUILD FILTER EXPR
    filters = []
    # date filtering
    filters.append(f'public_date = "{publish_date}"')
    # FZ filtering
    fz_allowed = []
    if fz44:  fz_allowed.append('"44"')
    if fz223: fz_allowed.append('"223"')
    if fz_allowed:
        filters.append(f"fz IN [{','.join(fz_allowed)}]")
    # price filtering
    if min_p is not None:
        filters.append(f"start_price >= {min_p}")
    if max_p is not None:
        filters.append(f"start_price <= {max_p}")
    meili_filter = " AND ".join(filters) if filters else ""

    # COLLECT INCLUDE/EXCLUDE from Meili
    include_docs, include_hl = collect_hits(index, keywords, meili_filter)
    # Use strict exact search for stopwords!
    exclude_ids = collect_hits_stopwords(index, stopwords, meili_filter)

    # FINAL TENDER IDS
    kept_ids = []
    for tid, snippets in include_hl.items():
        if tid in exclude_ids:
            continue
        # must have at least one snippet passing your threshold
        if any(should_keep_document(s) for s in snippets):
            kept_ids.append(tid)

    # PREPARE CSV
    if not kept_ids:
        print(f" → client={cid} tmpl={tmpl}: no results")
        return

    # All docs have same keys – take from the first one
    first_doc = include_docs[kept_ids[0]]
    # we remove the Meili-internal fields `_formatted` from output
    header = [k for k in first_doc.keys() if k != "_formatted"]
    header.append("highlight")

    out_name = f"client_data_{date_tag}_{cid}_{tmpl}.csv"
    with open(out_name, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=header)
        writer.writeheader()

        for tid in kept_ids:
            doc = include_docs[tid].copy()
            snippets = include_hl[tid]
            doc["highlight"] = " | ".join(snippets)
            # drop internal
            doc.pop("_formatted", None)
            writer.writerow(doc)

    print(f" → client={cid} tmpl={tmpl}: wrote {len(kept_ids)} rows to {out_name}")

# ----------------------------------------------------------------
def main():
    # load config
    if not Path(CONFIG_PATH).exists():
        raise FileNotFoundError(f"{CONFIG_PATH} not found")
    cfg = load_config(CONFIG_PATH)

    # connect / init index
    meili = Client(MEILI_URL, MEILI_KEY)
    idx   = meili.index(MEILI_INDEX)
    idx.update_stop_words(list(STOPWORDS))

    # process each merged file’s date tag
    merged = glob.glob("merged_*.csv")
    if not merged:
        print("No merged_*.csv files found.")
        return

    for path in merged:
        date_tag = Path(path).stem.split("_",1)[1]
        publish_date = date_from_filename(path)
        print(f"=== processing date={date_tag} ===")
        for client in cfg.get("clients", []):
            process_client(client, idx, date_tag, publish_date)

if __name__ == "__main__":
    main()
