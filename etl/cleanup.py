import os
import re
from pathlib import Path
from datetime import datetime
import shutil

def archive_files():
    # Get current directory
    current_dir = Path('.')
    
    # Pattern to extract date from filenames (format like "28.05.2025")
    date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    
    # Process each item in the directory
    for item in current_dir.iterdir():
        if item.name == 'archive':  # Skip the archive directory itself
            continue
            
        # Try to extract date from filename
        date_match = date_pattern.search(item.name)
        
        if date_match:
            date_str = date_match.group(1)
        else:
            # For directories/files without date, skip or handle differently
            if item.name in ['docs_clean', 'docs_refined', 'docs_md', 'docs_raw', 'summary']:
                # These don't have dates, so we'll use today's date
                date_str = datetime.now().strftime('%d.%m.%Y')
            else:
                continue  # skip files that don't match our patterns
        
        # Create archive directory for this date if it doesn't exist
        archive_dir = current_dir / 'archive' / date_str
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Move the file/directory
        try:
            target_path = archive_dir / item.name
            if item.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)  # remove if exists
                shutil.move(str(item), str(target_path))
            else:
                shutil.move(str(item), str(target_path))
            print(f"Moved {item.name} to {archive_dir}/")
        except Exception as e:
            print(f"Failed to move {item.name}: {e}")

if __name__ == "__main__":
    archive_files()