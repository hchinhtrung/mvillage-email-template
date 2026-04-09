import pandas as pd
from datetime import datetime, timedelta

def process_file():
    print("Loading file...")
    df = pd.read_csv('booking_import_results.csv')
    print(f"Loaded {len(df)} rows.")

    start_date = datetime(2026, 8, 3)

    def generate_dates(group):
        n = len(group)
        checkins = [start_date + timedelta(days=i) for i in range(n)]
        checkouts = [start_date + timedelta(days=i+1) for i in range(n)]
        
        # assign values to the existing chunk
        group['check in'] = [d.strftime('%m/%d/%Y') for d in checkins]
        group['check out'] = [d.strftime('%m/%d/%Y') for d in checkouts]
        return group

    print("Generating dates...")
    df = df.groupby('row id', group_keys=False).apply(generate_dates)
    
    print("Saving file...")
    # use native windows/mac style line endings might be handled, index false
    df.to_csv('booking_import_results_fake_dates.csv', index=False, date_format='%m/%d/%Y')
    print("Done")

process_file()
