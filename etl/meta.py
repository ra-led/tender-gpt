from pathlib import Path
import aiohttp
import asyncio
import csv
import json
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re
from tqdm.asyncio import tqdm

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

CONCURRENCY_LIMIT = 20  # Adjust based on target server tolerance
RETRIES = 3
REQUEST_TIMEOUT = 30
FIELDS = ['tender_id',
 'url',
 'ets_name',
 'ets_adress',
 'end_datetime',
 'lots',
 'result_date',
 'customer']


async def fetch(session, url):
    for attempt in range(RETRIES):
        try:
            async with session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            if attempt == RETRIES - 1:
                print(f"Failed {url} after {RETRIES} attempts: {str(e)}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None


def parse_tender(html, tender_id, tender_url):
    main_soup = BeautifulSoup(html, 'html.parser')
    metadata = {'tender_id': tender_id, 'url': tender_url}
    
    # Наименование электронной площадки в информационно-телекоммуникационной сети «Интернет»
    metadata['ets_name'] = None
    ets_nane_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Наименование электронной площадки' in t)
    ets_nane_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Место подачи заявок' in t)
    if ets_nane_section_44:
        ets_nane_info = ets_nane_section_44.find_next_sibling('span', class_='section__info')
        if ets_nane_info:
            metadata['ets_name'] = ets_nane_info.get_text(strip=True)
    elif ets_nane_section_223:
        ets_nane_info = ets_nane_section_223.find_next_sibling('div', class_='common-text__value')
        if ets_nane_info:
            metadata['ets_name'] = ets_nane_info.get_text(strip=True)
    
    # Адрес электронной площадки в информационно-телекоммуникационной сети «Интернет»
    metadata['ets_adress'] = None
    ets_adress_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Адрес электронной площадки' in t)
    ets_adress_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Адрес электронной площадки' in t)
    if ets_adress_section_44:
        ets_adress_info = ets_adress_section_44.find_next_sibling('span', class_='section__info')
        if ets_adress_info:
            metadata['ets_adress'] = ets_adress_info.get_text(strip=True)
    elif ets_adress_section_223:
        ets_adress_info = ets_adress_section_223.find_next_sibling('div', class_='common-text__value')
        if ets_adress_info:
            metadata['ets_adress'] = ets_adress_info.get_text(strip=True)
            
    # Дата и время окончания срока подачи заявок
    metadata['end_datetime'] = None
    listen_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Дата и время окончания срока подачи заявок' in t)
    listen_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Дата и время окончания срока подачи заявок (по местному времени заказчика)' in t)
    if listen_section_44:
        listen_info = listen_section_44.find_next_sibling('span', class_='section__info')
        if listen_info:
            metadata['end_datetime'] = listen_info.get_text(strip=True)
    elif listen_section_223:
        listen_info = listen_section_223.find_next_sibling('div', class_='common-text__value')
        if listen_info:
            metadata['end_datetime'] = listen_info.get_text(strip=True)
            
    # Описание
    # metadata['description'] = None
    # listen_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Наименование объекта закупки' in t)
    # listen_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Наименование закупки' in t)
    # if listen_section_44:
    #     listen_info = listen_section_44.find_next_sibling('span', class_='section__info')
    #     if listen_info:
    #         metadata['description'] = listen_info.get_text(strip=True)
    # elif listen_section_223:
    #     listen_info = listen_section_223.find_next_sibling('div', class_='common-text__value')
    #     if listen_info:
    #         metadata['description'] = listen_info.get_text(strip=True)
            
    # Информация об объекте закупки: Наименование товара, работы, услуги (all positions names)
    metadata['lots'] = []
    all_items = []
    try:
        inf_block = main_soup.find('h2', string=lambda x: x and 'Информация об объекте закупки' in x)
        table = inf_block.find_next('table')
        for tr in table.find_all('tr'):
            if "display: none" in (tr.get("style") or ""):
                continue
            if tr.parent.name == 'thead':
                continue
            tds = tr.find_all('td')
            if len(tds) > 2:
                pos_name = ''.join(tds[2].find_all(string=True, recursive=False)).strip()
                if pos_name:
                    # Limit the name to before the first double newline or excessive detail
                    all_items.append(pos_name)
    except AttributeError:
        all_items = []
    metadata['lots'] = '\n'.join(all_items)
    
    # Дата подведения итогов
    metadata['result_date'] = None
    date_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Дата подведения итогов' in t)
    date_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Дата подведения итогов' in t)
    if date_section_44:
        date_info = date_section_44.find_next_sibling('span', class_='section__info')
        if date_info:
            metadata['result_date'] = date_info.get_text(strip=True)
    elif date_section_223:
        date_info = date_section_223.find_next_sibling('div', class_='common-text__value')
        if date_info:
            metadata['result_date'] = date_info.get_text(strip=True)
    
    # Место нахождения
    metadata['customer'] = None
    customer_section_44 = main_soup.find('span', class_='section__title', string=lambda t: t and 'Место нахождения' in t)
    customer_section_223 = main_soup.find('div', class_='common-text__title', string=lambda t: t and 'Место нахождения' in t)
    if customer_section_44:
        customer_info = customer_section_44.find_next_sibling('span', class_='section__info')
        if customer_info:
            metadata['customer'] = customer_info.get_text(strip=True)
    elif customer_section_223:
        customer_info = customer_section_223.find_next_sibling('div', class_='common-text__value')
        if customer_info:
            metadata['customer'] = customer_info.get_text(strip=True)
    return metadata


async def process_tender(session, semaphore, tender_id, fz, writer, orig_url=None):
    async with semaphore:
        start_time = time.time()
        
        # Build URL based on FZ type
        if fz == '223':
            search_url = f'https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString={tender_id}'
            html = await fetch(session, search_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                link = soup.select_one('div.registry-entry__header-mid__number a')
                url = f'https://zakupki.gov.ru{link["href"]}' if link else None
        else:
            url = f'https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={tender_id}'

        if not url:
            return
        
        if orig_url:
            url = orig_url

        # Fetch tender page
        html = await fetch(session, url)
        if not html:
            return False
        result = parse_tender(html, tender_id=tender_id, tender_url=url)
        
        # Write results immediately
        writer.writerow(result)
        # print(f"Processed {tender_id} in {time.time()-start_time:.2f}s")
        return True


async def main(input_csv, output_csv):
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    with open(input_csv, 'r') as infile:
        reader = reader = csv.DictReader(infile, delimiter=';')
        all_rows = list(reader)
        total_tasks = len(all_rows)

    with open(output_csv, 'a', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=FIELDS)
        if outfile.tell() == 0:
            writer.writeheader()

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=0)) as session:
            tasks = [
                process_tender(
                    session,
                    semaphore,
                    row['tender_id'],
                    row['fz'],
                    writer,
                    # orig_url=row['url']
                )
                for row in all_rows
            ]

            progress_bar = tqdm(total=total_tasks, desc="Processing Tenders", unit="tender")
            
            # Add cooldown management
            cooldown_counter = 0
            cooldown_interval = 50  # Adjust based on server tolerance
            cooldown_duration = 0.3  # Seconds
            
            for coro in asyncio.as_completed(tasks):
                await coro
                progress_bar.update(1)
                
                # Strategic cooldown
                cooldown_counter += 1
                if cooldown_counter % cooldown_interval == 0:
                    progress_bar.set_postfix_str("Cooldown...")
                    await asyncio.sleep(cooldown_duration)
                    progress_bar.set_postfix_str("")

            progress_bar.close()

if __name__ == '__main__':
    for input_csv in Path('.').glob('published_raw_*.csv'):
        publish_date = input_csv.with_suffix('').name.replace('published_raw_', '')
        print(publish_date)
        output_csv = f'metadata_{publish_date}.csv'
    
        asyncio.run(main(input_csv, output_csv))
