import os
import sys
import json
import shutil
import argparse
from pathlib import Path
import py7zr
import zipfile, rarfile, psutil, subprocess, signal
from openai import OpenAI
from typing import List, Tuple, Union

from docs import classify_filenames

GPT_CLIENT = OpenAI(
    api_key='sk-8KGtH7yH8nipxh9pOrgQn3IJLqxSdkBj',
    base_url='https://api.proxyapi.ru/openai/v1'
)


# -------------------- Processing / Conversion Functions --------------------
def kill_libreoffice():
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if any(x in proc.info['name'] for x in ['soffice', 'libreoffice']):
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def doc_to_docx_unoconv(input_path: str, output_path: str):
    try:
        proc = subprocess.Popen(
            ["unoconv", "-f", "docx", "-o", output_path, input_path],
            start_new_session=True
        )
        proc.wait(timeout=90)
        # print(f"Converted {input_path} to {output_path}")
    except subprocess.CalledProcessError:
        print(f"Error converting {input_path}")
    except Exception as ex:
        print(f"Timeout converting {input_path}, killing processes...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        kill_libreoffice()
        print(f"Error converting {input_path}: {str(ex)}")


def extract_archives(dir_path: Union[str, Path]):
    """Recursively extract ZIP, RAR, and 7Z archives found in dir_path."""
    dir_path = Path(dir_path)
    while True:
        archives_found = False
        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                lower_file = file.lower()
                if lower_file.endswith('.zip'):
                    try:
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(root)
                        os.remove(file_path)
                        archives_found = True
                    except Exception as e:
                        print(f"Error extracting ZIP {file_path}: {str(e)}")
                elif lower_file.endswith('.rar'):
                    try:
                        rf = rarfile.RarFile(file_path)
                        rf.extractall(root)
                        rf.close()
                        os.remove(file_path)
                        archives_found = True
                    except Exception as e:
                        print(f"Error extracting RAR {file_path}: {str(e)}")
                elif lower_file.endswith('.7z'):
                    try:
                        with py7zr.SevenZipFile(file_path, mode='r') as archive:
                            archive.extractall(path=root)
                        os.remove(file_path)
                        archives_found = True
                    except Exception as e:
                        print(f"Error extracting 7Z {file_path}: {str(e)}")
        if not archives_found:
            break


def remove_duplicates(dir_path: Union[str, Path], priority_order: List[str]):
    print("\nRemoving duplicate files...")
    dir_path = Path(dir_path)
    for root, _, files in os.walk(dir_path):
        grouped_files = {}
        for file in files:
            name, ext = os.path.splitext(file)
            ext = ext.lower()
            grouped_files.setdefault(name, []).append((ext, os.path.join(root, file)))
        for name, file_list in grouped_files.items():
            file_list.sort(key=lambda x: priority_order.index(x[0]) if x[0] in priority_order else len(priority_order))
            for ext, file_path in file_list[1:]:
                print(f"Deleting duplicate: {file_path}")
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {str(e)}")

def fix_filename(name: str, from_enc='cp437', to_enc='cp866') -> str:
    try:
        return name.encode(from_enc).decode(to_enc)
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name

def process_directory(dir_path: Union[str, Path], convert_files: bool = False, priority_order: List[str] = None):
    """
    Process a tender folder: extract archives, convert .doc to .docx, remove duplicates,
    and, if flagged, convert files to PDF.
    """
    if priority_order is None:
        priority_order = ['.xlsx', '.docx', '.pdf']
    dir_path = Path(dir_path)
    print("Extracting archives...")
    extract_archives(dir_path)
    print("\nConverting .doc files to .docx via unoconv...")
    for doc_path in dir_path.rglob('*.doc'):
        doc_to_docx_unoconv(doc_path.absolute().as_posix(),
                            doc_path.with_suffix('.docx').absolute().as_posix())
    print("\nConverting .odt files to .docx via unoconv...")
    for doc_path in dir_path.rglob('*.odt'):
        doc_to_docx_unoconv(doc_path.absolute().as_posix(),
                            doc_path.with_suffix('.docx').absolute().as_posix())
    print("\nConverting .rtf files to .docx via unoconv...")
    for doc_path in dir_path.rglob('*.rtf'):
        doc_to_docx_unoconv(doc_path.absolute().as_posix(),
                            doc_path.with_suffix('.docx').absolute().as_posix())
    print("\nRemoving duplicate files...")
    remove_duplicates(dir_path, priority_order)
    if convert_files:
        print("\nConverting files to PDF...")
        supported_ext = ('.docx', '.doc', '.xls', '.xlsx', '.rtf')
        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = Path(file).suffix.lower()
                if ext in supported_ext:
                    pdf_path = os.path.join(root, Path(file).stem + '.pdf')
                    if os.path.exists(pdf_path):
                        try:
                            os.remove(pdf_path)
                        except Exception as e:
                            print(f"Error deleting old PDF {pdf_path}: {str(e)}")
                    print(f"Converting: {file_path}")
                    try:
                        subprocess.run([
                            'libreoffice', '--headless', '--convert-to', 'pdf',
                            '--outdir', root, file_path
                        ], check=True, capture_output=True)
                    except subprocess.CalledProcessError as e:
                        print(f"Error converting {file_path}: {e.stderr.decode()}")

def prepare_conversion_dir(tender_dir: Path):
    """Prepare directory structure for conversion."""
    (tender_dir / 'to_convert').mkdir(exist_ok=True)
    (tender_dir / 'common').mkdir(exist_ok=True)
    (tender_dir / 'ed').mkdir(exist_ok=True)
    for ext in ['*.pdf', '*.docx', '*.xlsx']:
        for file_path in list(tender_dir.rglob(ext)):
            relative_path = file_path.relative_to(tender_dir)
            fixed_name = fix_filename(str(relative_path).replace('/', '_'))
            shutil.copy(file_path, tender_dir / 'to_convert' / fixed_name)

# ——————————————————————————————————————

def process_one_folder(src: Path, dst: Path):
    """
    src: .../docs_raw/YYYY-MM-DD/client_id/template_id
    dst: .../docs_clean/YYYY-MM-DD/client_id/template_id
    """
    # Mirror structure
    (dst / 'ed').mkdir(parents=True, exist_ok=True)
    (dst / 'common').mkdir(parents=True, exist_ok=True)
    # Work in a temp area
    work = dst / 'work'
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(src, work)
    
    # 1) Extract, convert, dedupe
    process_directory(work, convert_files=False)
    
    # 2) Prepare for classification
    prepare_conversion_dir(work)
    to_convert = list((work / 'to_convert').glob('*'))
    filenames = [f.name for f in to_convert]
    if not filenames:
        print(f"  → skipping {src}, nothing to convert")
        return
    
    # 3) Classify
    sel_idxs, classes = classify_filenames(filenames)
    
    # 4) Split into ed / common
    for idx, fpath in enumerate(to_convert):
        cat = classes.get(str(idx), 'O').upper()
        if idx in sel_idxs and cat == 'ED':
            dest = dst / 'ed' / fpath.name
        else:
            dest = dst / 'common' / fpath.name
        shutil.move(str(fpath), dest)

    # done, clean up work
    shutil.rmtree(work)

def main():
    raw_root = Path('docs_raw')
    clean_root = Path('docs_clean')

    # Walk date / client / template
    for date_dir in sorted(raw_root.iterdir()):
        if not date_dir.is_dir(): continue
        for client_dir in sorted(date_dir.iterdir()):
            if not client_dir.is_dir(): continue
            for tpl_dir in sorted(client_dir.iterdir()):
                if not tpl_dir.is_dir(): continue
                for tender_dir in sorted(tpl_dir.iterdir()):
                    if not tender_dir.is_dir(): continue

                    src = tender_dir
                    rel = src.relative_to(raw_root)
                    dst = clean_root / rel
                    print(f"Processing {src} → {dst}")
                    dst.mkdir(parents=True, exist_ok=True)
                    try:
                        process_one_folder(src, dst)
                    except Exception as e:
                        print(f"  ERROR on {src}: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()