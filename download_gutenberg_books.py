import os
import csv
import requests
from time import sleep

# Folder to save .txt files
gutenberg_folder = os.path.join(os.getcwd(), "datasets", "gutenberg_download")
os.makedirs(gutenberg_folder, exist_ok=True)

# Metadata CSV
metadata_csv = os.path.join(os.getcwd(), "datasets", "gutenberg_metadata.csv")

with open(metadata_csv, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        filename = row.get('filename')
        gutenberg_id = row.get('gutenberg_id')  # Make sure your CSV has Gutenberg ID column
        if not filename or not gutenberg_id:
            continue

        file_path = os.path.join(gutenberg_folder, filename)

        # Skip if file already exists
        if os.path.exists(file_path):
            continue

        # Gutenberg plain text URL
        url = f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-0.txt"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(file_path, 'w', encoding='utf-8') as f_out:
                    f_out.write(response.text)
                print(f"Downloaded: {filename}")
            else:
                print(f"Failed to download: {filename}")
        except Exception as e:
            print(f"Error downloading {filename}: {e}")

        sleep(1)  # polite delay
