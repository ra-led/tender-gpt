import requests
import datetime
from urllib.parse import urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
import re
import csv
import os

RENAME_COLS = [
    ('Наименование закупки', 'description'),
    ('Классификация по ОКПД2', 'okpd2'),
    ('Наименование Заказчика', 'customer_name'),
    ('Дата размещения', 'public_date'),
    ('Начальная (максимальная) цена контракта', 'start_price'),
    ('Дата окончания подачи заявок', 'end_date'),
    ('Наименование лота', 'lot_name'),
]

OKER_MAP = {
    'OKER34': 'Уральский федеральный округ',
    'OKER38': 'Северо-Кавказский федеральный округ',
    'OKER35': 'Сибирский федеральный округ',
    'OKER30': 'Центральный федеральный округ',
    'OKER37': 'Южный федеральный округ',
    'OKER31': 'Северо-Западный федеральный округ',
    'OKER36': 'Дальневосточный федеральный округ',
    'OKER33': 'Приволжский федеральный округ'
}


def get_yesterday_date():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return yesterday.strftime("%d.%m.%Y")


def download_and_convert_chunks(publish_date_from=None, publish_date_to=None, customer_place=None):
    if publish_date_from is None or publish_date_to is None:
        yesterday = get_yesterday_date()
        publish_date_from = yesterday
        publish_date_to = yesterday

    base_params = {
        'morphology': 'on',
        'search-filter': '%D0%94%D0%B0%D1%82%D0%B5+%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F',
        'pageNumber': '1',
        'sortDirection': 'false',
        'recordsPerPage': '_10',
        'showLotsInfoHidden': 'false',
        'sortBy': 'UPDATE_DATE',
        'fz44': 'on',
        'fz223': 'on',
        'af': 'on',
        'currencyIdGeneral': '-1',
        'publishDateFrom': publish_date_from,
        'publishDateTo': publish_date_to,
    }
    if customer_place:
        base_params['customerPlace'] = customer_place

    search_url = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?" + urlencode(base_params)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'Referer': search_url
    }

    csv_params = {
        'placementCsv': 'true',
        'registryNumberCsv': 'true',
        'nameOrderCsv': 'true',
        'nameLotCsv': 'true',
        'maxContractPriceCsv': 'true',
        'currencyCodeCsv': 'true',
        'scopeOkpd2Csv': 'true',
        'customerNameCsv': 'true',
        'publishDateCsv': 'true',
        'endDateRequestCsv': 'true',
    }

    downloaded_files = []
    
    with requests.Session() as session:
        response = session.get(search_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        download_button = soup.find('a', class_='downLoad-search')
        if not download_button:
            raise ValueError("Download button not found.")
        
        total_count = int(re.search(r"'(\d+)'", download_button['onclick']).group(1))
        print(f"Total records: {total_count}")
        total_count = min(total_count, 5000)
        print(f"Get records: {total_count}")

        chunks = [(i, min(i+499, total_count)) for i in range(1, total_count+1, 500)]
        
        for idx, (start, end) in enumerate(chunks):
            params = base_params.copy()
            params.update(csv_params)
            params.update({'from': start, 'to': end})

            download_url = 'https://zakupki.gov.ru/epz/order/orderCsvSettings/download.html'
            response = session.get(download_url, params=params, headers=headers)
            response.raise_for_status()

            decoded_content = response.content.decode('cp1251')
            components = ['procurement', publish_date_from]
            if customer_place:
                components.append(customer_place)
            components.append(f'{start}-{end}')
            filename = '_'.join(components) + '.csv'
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(decoded_content)
                
            downloaded_files.append(filename)
            print(f"Downloaded and converted: {filename}")

    return downloaded_files, publish_date_from


def extract_oker_from_filename(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    parts = base.split('_')
    if len(parts) >= 4:
        return parts[2]
    return ''


def concatenate_files(file_list, output_filename):
    fieldnames = set()
    for filename in file_list:
        with open(filename, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile, delimiter=';')
            fieldnames.update(reader.fieldnames)
    
    fieldnames = list(fieldnames)
    new_columns = ['oker', 'fz', 'tender_id'] + [new_key for old_key, new_key in RENAME_COLS]
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    with open(output_filename, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        for filename in file_list:
            oker_code = extract_oker_from_filename(filename)
            with open(filename, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile, delimiter=';')
                for row in reader:
                    row['oker'] = oker_code
                    row['tender_id'] = re.sub(r'\D', '', row.get('Реестровый номер закупки', ''))
                    row['fz'] = re.sub(r'\D', '', row.get('Закупки по', ''))
                    for old_key, new_key in RENAME_COLS:
                        if old_key in row:
                            row[new_key] = row.pop(old_key)
                    writer.writerow(row)
    print(f"Combined file created: {output_filename}")


if __name__ == '__main__':
    all_downloaded_files = []
    for oker_code, region_name in OKER_MAP.items():
        print(f"Exporting data for region: {region_name}")
        downloaded_files, date_str = download_and_convert_chunks(customer_place=oker_code)
        all_downloaded_files.extend(downloaded_files)
    
    output_file = f'published_raw_{date_str}.csv'
    concatenate_files(all_downloaded_files, output_file)
    
    for f in all_downloaded_files:
        os.remove(f)
    print("Temporary files cleaned up")

    cmd = f"python export_diff.py {date_str}"
    print(f"Running diff: {cmd}")
    os.system(cmd)
