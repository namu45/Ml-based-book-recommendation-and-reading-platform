import csv
import os
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
django.setup()

from recommender.models import Book

# Paths
gutenberg_folder = r"D:\bookwise_data\gutenberg_download"   # folder with 1.txt, 2.txt, ...
metadata_csv = r"C:\Users\HP\bookwise_project\datasets\gutenberg_metadata.csv"  # CSV file

# Check paths
if not os.path.exists(gutenberg_folder):
    print(f"Gutenberg folder not found: {gutenberg_folder}")
    exit()

if not os.path.exists(metadata_csv):
    print(f"Metadata CSV not found: {metadata_csv}")
    exit()

# List all txt files in folder sorted (1.txt, 2.txt, 3.txt, ...)
all_files = sorted([f for f in os.listdir(gutenberg_folder) if f.endswith('.txt')])

# Read CSV and load books
with open(metadata_csv, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for idx, row in enumerate(reader):
        # Stop if no more files available
        if idx >= len(all_files):
            break

        # Get title and author from CSV
        title = row.get('Title') or "Unknown Title"
        author = row.get('Authors') or "Unknown Author"

        # Assign filename from folder order
        filename = all_files[idx]
        file_path = os.path.join(gutenberg_folder, filename)

        # Avoid duplicates
        if Book.objects.filter(title=title, source='GUT').exists():
            print(f"Skipping duplicate: {title}")
            continue

        # Save book
        try:
            book = Book(
                title=title,
                author=author,
                file_path=file_path,
                source='GUT'
            )
            book.full_clean()  # checks for any model validation errors
            book.save()
            print(f"Loaded: {title}")
        except Exception as e:
            print(f"Error saving {title}: {e}")

print("All Gutenberg books processed successfully!")
