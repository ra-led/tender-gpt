import glob
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import urllib.parse
import pandas as pd
from pathlib import Path
import json
from typing import Union, List, Tuple
from openai import OpenAI

GPT_CLIENT = OpenAI(
    api_key='sk-8KGtH7yH8nipxh9pOrgQn3IJLqxSdkBj',
    base_url='https://api.proxyapi.ru/openai/v1'
)


def classify_filenames(filenames: List[str]) -> Tuple[List[int], dict]:
    """
    Use OpenAI to classify filenames into document categories.
    Returns the indexes of files that belong to required categories and the full classification dict.
    """
    if not filenames:
        return [], {}
    
    prompt = """Classify each filename into one of these categories based on common naming patterns:
- Draft contract (DC): Проект контракта, ПК, Проект ГК, Контракт, Государственный контракт, договор, закупочная документация, ЗД, draft_contract
- Technical specifications (TS): ТЗ, Техническое задание, Приложение 1, Технические характеристики, specs, technical
- Description of the procurement object (DPO): Описание объекта закупки, ООЗ, Описание товара, предмет закупки, product_description
- Estimate documentation (ED): Смета, Пример сметы, сметная документация, расчет стоимости, estimate, budget
- Report (R): Технический отчет, Отчет экспертизы, other reports
- Market price (MP): Определение минимальной цены конктракта, Определение НМЦК, Определение начальной цены, Расчет НМЦК
- Nature care (NC): Охрана окружающей среды, ООС, ООС2, Природоохрана
- Bid template (B): Требования к содержанию и составу заявки, Инструкция по заполнению заяки на участие в аукционе
- Other (O): Anything that doesn't fit above categories

Respond with JSON where keys are the 0-based indexes and values are category abbreviations (DC, TS, DPO, ED, R, MP, NC, B, O).

Filenames to classify:
"""
    for idx, name in enumerate(filenames):
        prompt += f"{idx}: {name}\n"
    
    try:
        response = GPT_CLIENT.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "You classify tender documents. Use only DC, TS, DPO, ED, R, MP, NC, B, O. Respond with JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        classifications = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Classification error: {str(e)}")
        return list(range(len(filenames))), {}
    
    # Select required indexes (we expect at least ED, DC, TS, etc. adjust as needed)
    required_categories = {'DC', 'TS', 'DPO', 'ED'}
    found_categories = set()
    selected_indexes = []
    for idx_str, category in classifications.items():
        try:
            idx = int(idx_str)
            normalized_category = category.strip().upper()
            if normalized_category in required_categories:
                found_categories.add(normalized_category)
                selected_indexes.append(idx)
        except Exception:
            continue
    # Fallback: if too few required files were found, mark all files to be processed
    if len(found_categories) < 2:
        selected_indexes = list(range(len(filenames)))
    return selected_indexes, classifications


# -------------------- Downloader Functions --------------------
BASE_URL = "https://zakupki.gov.ru"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def sanitize_filename(name: str) -> str:
    if "; filename" in name:
        name = name[:name.find("; filename") - 1]
    return urllib.parse.unquote(name, encoding='utf-8', errors='replace')

def download_file(url: str, target_folder: Union[str, Path]) -> Union[Path, None]:
    try:
        with requests.get(url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            filename = None
            if "content-disposition" in r.headers:
                cd = r.headers["content-disposition"]
                parts = cd.split("filename=")
                if len(parts) > 1:
                    filename = parts[1].strip(' "')
            if not filename:
                filename = Path(urllib.parse.urlparse(url).path).name
                if not filename or filename == '/':
                    filename = "document.bin"
            filename = sanitize_filename(filename)
            filepath = Path(target_folder) / filename
            counter = 1
            while filepath.exists():
                stem = filepath.stem
                suffix = filepath.suffix
                filepath = filepath.with_name(f"{stem}_{counter}{suffix}")
                counter += 1
            total_size = int(r.headers.get('content-length', 0))
            with open(filepath, 'wb') as f, tqdm(
                desc=filename, total=total_size, unit='B', unit_scale=True, unit_divisor=1024
            ) as bar:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bar.update(len(chunk))
            return filepath
    except Exception as e:
        print(f"Failed to download {url}: {str(e)}")
        return None


def get_tender_docs(tender_url: str, output_folder: Union[str, Path], tender_id = None) -> None:
    """
    Process a single tender: download metadata and files.
    If the tender folder already exists, skip processing.
    """
    tender_folder = Path(output_folder) / f"tender_{tender_id}"
    if tender_folder.exists():
        print(f"Tender {tender_id} already processed. Skipping.")
        return
    tender_folder.mkdir(parents=True, exist_ok=True)
        
    # Process documents
    docs_url = tender_url.replace('common-info.html', 'documents.html')
    try:
        response = requests.get(docs_url, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"Error retrieving docs page for {tender_url}: {str(e)}")
        return
    soup = BeautifulSoup(response.text, 'html.parser')
    docs_block_44 = soup.find('div', class_='blockFilesTabDocs')
    docs_block_223 = soup.find('div', class_='attachment__text', string='Прикрепленные файлы')
    if docs_block_44:
        doc_links = docs_block_44.find_all('a', href=True)
    elif docs_block_223:
        attachments_div = docs_block_223.find_next_sibling('div', class_='attachment__value')
        doc_links = []
        if attachments_div:
            doc_links = [
                a
                for a in attachments_div.find_all('a', href=True) 
                if '/download/download.html' in a['href']
            ]
    if not doc_links:
        print(f"No document links found for tender {tender_id}")
        return
    print(f"Processing tender {tender_id}...")
    
    # Extract filenames and links (skip links with 'signview')
    filenames = [link.text.strip() for link in doc_links if 'signview' not in link['href']]
    filelinks = [link['href'] for link in doc_links if 'signview' not in link['href']]
    # print("Found document filenames:", filenames)
    
    required_indexes, _ = classify_filenames(filenames)
    filelinks = [filelinks[idx] for idx in required_indexes]
    
    for file_url in filelinks:
        if not file_url.startswith('http'):
            file_url = urllib.parse.urljoin(BASE_URL, file_url)
        download_file(file_url, tender_folder)


def extract_tender_id(url: str) -> str:
    """Try to pull a tender identifier from the URL query string."""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for key in ("tenderId", "id", "ref", "purchaseNoticeId"):
        if key in qs:
            return qs[key][0]
    # fallback: use the path’s last segment
    return Path(urllib.parse.urlparse(url).path).stem


def process_csv(path: Path, output_root: Path):
    """
    path: match_{date}_{client_id}_{template_id}.csv
    output_root: where to put docs/
    """
    # parse date, client_id, template_id from filename
    # expects: match_2024-06-15_12345_678.csv
    parts = path.stem.split("_", 3)
    if len(parts) != 4 or parts[0] != "match":
        print(f"Skipping unexpected filename: {path.name}")
        return

    _, date, client_id, template_id = parts
    dest_folder = output_root / date / client_id / template_id
    dest_folder.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(path, dtype={'tender_id': str})
    # you must have a column with the URL – adjust name as needed
    url_col = "tender_url" if "tender_url" in df.columns else "url"
    id_col = "tender_id" if "tender_id" in df.columns else None

    for idx, row in df.iterrows():
        url = row[url_col]
        tid = row[id_col] if id_col else None
        if not tid:
            tid = extract_tender_id(url)
        try:
            get_tender_docs(url, dest_folder, tender_id=tid)
        except Exception as e:
            print(f"[{path.name} row {idx}] Error processing {url}: {e}")


def main():
    input_folder=Path(".")
    output_root=Path("docs_raw")

    pattern = str(input_folder / "match_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No match_*.csv files found in", input_folder)
        return

    for f in files:
        process_csv(Path(f), output_root)


if __name__ == "__main__":
    main()