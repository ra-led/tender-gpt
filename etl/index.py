import os
import csv
import sys
from meilisearch import Client
from pathlib import Path
from datetime import datetime

# 1) Setup client & index
MEILI_URL = os.getenv('MEILI_URL', 'http://0.0.0.0:7700')
MEILI_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')
meili = Client(MEILI_URL, MEILI_KEY)

INDEX_NAME = "tenders"
tenders_index = meili.index(INDEX_NAME)

# assume textual fields are searchable (by default).
# choose subset of fields you need for filters / faceting / sorting:
COLS = {
    'customer',
    'customer_name',
    'description',
    'end_date',
    'end_datetime',
    'ets_adress',
    'ets_name',
    'fz',
    'lot_name',
    'lots',
    'oker',
    'okpd2',
    'public_date',
    'result_date',
    'start_price',
    'tender_id',
    'url'
}
FILTERABLE = [
    'tender_id', 'oker', 'fz', 'okpd2', 'customer_name',
    'public_date','end_date','result_date','start_price'
]
SORTABLE = ['public_date','end_date','result_date','start_price']

# Declare which fields are dates, floats, etc.
DATE_FIELDS = {'public_date', 'end_date', 'result_date'}
FLOAT_FIELDS = {'start_price'}
# Everything else we leave as string

def normalize_row(row: dict) -> dict:
    """
    Convert row values to proper types:
    - Dates to ISO strings
    - Floats to float
    """
    doc = {}
    for key, val in row.items():
        if key not in COLS:
            continue
        val = val.strip()

        if key in DATE_FIELDS:
            # your format is 'DD.MM.YYYY'
            try:
                dt = datetime.strptime(val, '%d.%m.%Y')
                doc[key] = dt.date().isoformat()
            except ValueError:
                doc[key] = val  # fallback
        elif key in FLOAT_FIELDS:
            try:
                doc[key] = float(val.replace(',', '').replace(' ', ''))
            except ValueError:
                doc[key] = None
        else:
            doc[key] = val if val else ''
    return doc

if __name__ == '__main__':
    maxInt = sys.maxsize
    while True:
        try:
            csv.field_size_limit(maxInt)
            break
        except OverflowError:
            maxInt = int(maxInt / 10)
    
    docs = []
    for csv_file in Path('.').glob('merged_*.csv'):
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc = normalize_row(row)
                doc['tender_id'] = row['tender_id']  # ensure unique key is set
                docs.append(doc)
        if not docs:
            print("⚠️ No rows found to index.")
            exit(1)

    # 2) Configure index settings:
    #    make sure any field you want to filter or sort on is declared filterable / sortable
    all_fields = list(docs[0].keys())

    print("Updating index settings…")
    tenders_index.update_filterable_attributes(FILTERABLE)
    tenders_index.update_sortable_attributes(SORTABLE)

    # 3) Bulk upload
    print(f"Indexing {len(docs)} documents…")
    batch_size = 15000
    for i in range(0, len(docs), batch_size):
        result = tenders_index.add_documents(docs[i: i + batch_size], primary_key='tender_id')
        print("✅ Done:", result)
