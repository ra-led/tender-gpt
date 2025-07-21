import csv
import os
import shutil
import sys

def main(date_str):
    raw_file    = f'published_raw_{date_str}.csv'
    master_file = f'master_published_{date_str}.csv'
    new_file    = f'new_published_{date_str}.csv'

    if not os.path.exists(raw_file):
        print(f"[!] raw file not found: {raw_file}")
        sys.exit(1)

    # 1) read the freshly exported CSV
    with open(raw_file, newline='', encoding='utf-8') as f_raw:
        raw_reader = csv.DictReader(f_raw, delimiter=';')
        raw_rows   = list(raw_reader)
        fieldnames = raw_reader.fieldnames

    # 2) collect all tender_id already in master (if it exists)
    seen_ids = set()
    if os.path.exists(master_file):
        with open(master_file, newline='', encoding='utf-8') as f_master:
            master_reader = csv.DictReader(f_master, delimiter=';')
            for r in master_reader:
                seen_ids.add(r['tender_id'])

    # 3) pick out just the new ones
    new_rows = [r for r in raw_rows if r['tender_id'] not in seen_ids]
    print(f"[i] Found {len(new_rows)} new rows (out of {len(raw_rows)} total)")

    # 4) write them to new_published_{date_str}.csv
    with open(new_file, 'w', newline='', encoding='utf-8') as f_new:
        writer = csv.DictWriter(f_new, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(new_rows)
    print(f"[+] Wrote new rows to {new_file}")

    # 5) update the master: copy raw → master
    shutil.copyfile(raw_file, master_file)
    print(f"[+] Master updated: {master_file}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python diff_published.py <DD.MM.YYYY>")
        sys.exit(1)
    main(sys.argv[1])