# merge_books_resume.py
import os
import csv
import django
import re
from difflib import get_close_matches
from django.db.models import Count, Avg, Value
from django.db.models.functions import Coalesce

# ---------- CONFIG ----------
DJANGO_SETTINGS_MODULE = "bookwise.settings"
GUTENBERG_METADATA = os.path.join(os.getcwd(), "datasets", "gutenberg_metadata.csv")
GUTENBERG_FOLDER = r"D:\bookwise_data\gutenberg_download"
DRY_RUN = False           # Set False to actually apply changes
FUZZY_CUTOFF = 0.88      # strict-ish match
MAX_FUZZY_TRIES = 1
# ----------------------------

os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
django.setup()

from recommender.models import Book, UserBook

def normalize_title(t):
    if not t:
        return ""
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t

def find_file_for_etext(etext):
    if not etext:
        return None
    candidate = f"{etext}.txt"
    p = os.path.join(GUTENBERG_FOLDER, candidate)
    if os.path.exists(p):
        return p
    # try some other guesses
    for fmt in (f"{int(etext)}.txt", candidate):
        p = os.path.join(GUTENBERG_FOLDER, fmt)
        if os.path.exists(p):
            return p
    return None

# Build lookup of existing Book titles with file_path
books_qs = Book.objects.all().values('id', 'title', 'file_path', 'source')
title_to_books = {}
norm_titles_list = []
for b in books_qs:
    norm = normalize_title(b['title'] or "")
    title_to_books.setdefault(norm, []).append(b)
    norm_titles_list.append(norm)

print(f"Loaded {len(books_qs)} books from DB.")

# Load Gutenberg metadata
if not os.path.exists(GUTENBERG_METADATA):
    print("ERROR: Gutenberg metadata CSV not found:", GUTENBERG_METADATA)
    exit(1)
if not os.path.isdir(GUTENBERG_FOLDER):
    print("ERROR: Gutenberg folder not found:", GUTENBERG_FOLDER)
    exit(1)

with open(GUTENBERG_METADATA, encoding='utf-8') as f:
    reader = list(csv.DictReader(f))
total_books = len(reader)
print(f"Total Gutenberg metadata rows: {total_books}")

# Stats
matched_count = 0
file_updated_count = 0
fuzzy_used_count = 0
skipped_count = 0
unmatched = []

for i, row in enumerate(reader, start=1):
    title = (row.get('Title') or row.get('title') or "").strip()
    etext = row.get('Etext Number') or row.get('Etext') or row.get('ETextNumber') or row.get('Etext_Number') or row.get('etextno')
    if not title:
        continue

    norm = normalize_title(title)

    # Skip if any existing DB book already has a file_path
    existing_books_with_file = Book.objects.filter(title__iexact=title).exclude(file_path__isnull=True)
    if existing_books_with_file.exists():
        skipped_count += 1
        continue

    file_path = find_file_for_etext(etext)

    # Exact match in DB
    candidates = title_to_books.get(norm, [])
    target_book_obj = None
    match_type = None

    if candidates:
        target_book_obj = candidates[0]
        match_type = "exact"
    else:
        # Fuzzy match
        close = get_close_matches(norm, norm_titles_list, n=MAX_FUZZY_TRIES, cutoff=FUZZY_CUTOFF)
        if close:
            fuzzy_used_count += 1
            match_norm = close[0]
            cand_list = title_to_books.get(match_norm, [])
            if cand_list:
                target_book_obj = cand_list[0]
                match_type = f"fuzzy({FUZZY_CUTOFF})"

    if not target_book_obj:
        unmatched.append(title)
        continue

    matched_count += 1
    book_id = target_book_obj['id']
    will_update_file = file_path and not target_book_obj.get('file_path')

    if DRY_RUN:
        if will_update_file:
            print(f"[{i}/{total_books}] DRY: set file_path for book_id={book_id} -> {file_path}")
        continue

    # Apply updates
    book = Book.objects.get(id=book_id)
    if will_update_file:
        book.file_path = file_path
        book.save()
        file_updated_count += 1
        print(f"[{i}/{total_books}] Applied: set file_path for book_id={book_id}")

# Final summary
print("\n=== Summary ===")
print("DRY_RUN:", DRY_RUN)
print(f"Processed Gutenberg rows: {total_books}")
print(f"Matched books: {matched_count}")
print(f"Skipped (already has file): {skipped_count}")
print(f"File updates applied: {file_updated_count}")
print(f"Fuzzy matches used: {fuzzy_used_count}")
print(f"Unmatched titles: {len(unmatched)}")
if unmatched:
    print("Example unmatched (first 10):")
    for t in unmatched[:10]:
        print("  -", t)
