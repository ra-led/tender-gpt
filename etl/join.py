from pathlib import Path
import pandas as pd

# Process each published_raw file
for input_csv in Path('.').glob('published_raw_*.csv'):
    publish_date = input_csv.with_suffix('').name.replace('published_raw_', '')
    print(f"Processing date: {publish_date}")
    
    # Define corresponding metadata file
    output_csv = f'metadata_{publish_date}.csv'
    
    if not Path(output_csv).exists():
        print(f"Metadata file {output_csv} not found, skipping")
        continue
    
    # Load both dataframes
    df_raw = pd.read_csv(input_csv, delimiter=';', dtype={'tender_id': str})
    df_meta = pd.read_csv(output_csv, dtype={'tender_id': str})
    
    # Check uniqueness of tender_id in both tables
    raw_duplicates = df_raw['tender_id'].duplicated().sum()
    meta_duplicates = df_meta['tender_id'].duplicated().sum()
    
    if raw_duplicates > 0:
        print(f"Warning: {raw_duplicates} duplicate tender_id values in {input_csv.name}")
        # Optionally drop duplicates - uncomment if you want to keep first occurrence
        df_raw = df_raw.drop_duplicates(subset=['tender_id'], keep='first')
    
    if meta_duplicates > 0:
        print(f"Warning: {meta_duplicates} duplicate tender_id values in {output_csv}")
        # Optionally drop duplicates - uncomment if you want to keep first occurrence
        df_meta = df_meta.drop_duplicates(subset=['tender_id'], keep='first')
    
    # Perform the join
    try:
        merged_df = pd.merge(
            df_raw,
            df_meta,
            on='tender_id',
            how='inner',  # Use 'left' to keep all raw records even without metadata
            validate='one_to_one'  # This will raise error if not 1:1 relationship
        )
        
        # Save the merged result
        merged_filename = f'merged_{publish_date}.csv'
        merged_df.to_csv(merged_filename, index=False)
        print(f"Merged data saved to {merged_filename} ({len(merged_df)} records)")
        
    except pd.errors.MergeError as e:
        print(f"Error merging files for {publish_date}: {str(e)}")
        continue