#!/usr/bin/env python3
# merge_books.py (resume-friendly)
# Safe Gutenberg -> DB linking script. Dry-run by default.
#
# Usage:
#   python merge_books.py                # dry-run preview
#   python merge_books.py --apply        # actually apply changes
#   python merge_books.py --apply --delete-duplicates
#   python merge_books.py --limit 1000 --cutoff 0.85
#
# Edit GUTENBERG_METADATA / GUTENBERG_FOLDER defaults below if needed.

import os
import csv
import re
import argparse
from difflib import get_close_matches, SequenceMatcher
from collections import defaultdict

# ---------- CONFIG defaults (override with CLI) ----------
DJANGO_SETTINGS_MODULE = "bookwise.settings"
GUTENBERG_METADATA = os.path.join(os.getcwd(), "datasets", "gutenberg_metadata.csv")
GUTENBERG_FOLDER = r"D:\bookwise_data\gutenberg_download"
DEFAULT_CUTOFF = 0.88
# --------------------------------------------------------

# CLI
parser = argparse.ArgumentParser(description="Link Gutenberg files to Book DB rows and optionally move ratings from duplicates.")
parser.add_argument("--apply", action="store_true", help="Apply changes to DB (default = dry-run).")
parser.add_argument("--delete-duplicates", action="store_true", help="Delete other duplicate Book rows after moving ratings (requires --apply).")
parser.add_argument("--cutoff", type=float, default=DEFAULT_CUTOFF, help="Fuzzy title match cutoff (0-1). Lower => more matches.")
parser.add_argument("--limit", type=int, default=0, help="Process only first N rows from metadata (0 = all).")
parser.add_argument("--metadata", default=GUTENBERG_METADATA, help="Path to Gutenberg metadata CSV.")
parser.add_argument("--folder", default=GUTENBERG_FOLDER, help="Path to folder with Gutenberg .txt files.")
parser.add_argument("--verbose", action="store_true", help="Verbose output.")
args = parser.parse_args()

DRY_RUN = not args.apply
DELETE_DUPS = args.delete_duplicates
FUZZY_CUTOFF = args.cutoff
PROCESS_LIMIT = args.limit
METADATA = args.metadata
GUTENBERG_FOLDER = args.folder
VERBOSE = args.verbose

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
import django
django.setup()

from django.db import transaction
from django.db.models import Count
from recommender.models import Book, UserBook

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)        # drop punctuation
    s = re.sub(r"\s+", " ", s)
    return s

def find_file_for_etext(folder: str, etext: str):
    """Try common filename forms for an etext number (e.g. '12345.txt', '012345.txt')."""
    if not etext:
        return None
    # try direct
    candidates = [f"{etext}.txt"]
    # try integer (removes leading zeros)
    try:
        candidates.append(f"{int(etext)}.txt")
    except Exception:
        pass
    # try padded (rare)
    try:
        candidates.append(f"{int(etext):06d}.txt")
    except Exception:
        pass
    for c in candidates:
        p = os.path.join(folder, c)
        if os.path.exists(p):
            return p
    return None

# Sanity checks
if not os.path.exists(METADATA):
    print("ERROR: metadata CSV not found:", METADATA)
    raise SystemExit(1)
if not os.path.isdir(GUTENBERG_FOLDER):
    print("ERROR: Gutenberg folder not found:", GUTENBERG_FOLDER)
    raise SystemExit(1)

# Preload DB books with userbook counts (performance)
print("Loading books from DB (with popularity counts)...")
books_qs = Book.objects.annotate(popularity=Count('userbook')).values('id', 'title', 'author', 'file_path', 'source', 'popularity')
books = list(books_qs)
print(f"Loaded {len(books)} books from DB.")

# Build normalized title -> list mapping
title_map = defaultdict(list)
norm_titles = []
for b in books:
    norm = normalize_text(b['title'] or "")
    title_map[norm].append(b)
    norm_titles.append(norm)

# Process CSV
matched = 0
fuzzy_used = 0
file_updates = 0
ratings_moved = 0
duplicate_targets = 0
unmatched = []

def author_similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def debug(msg):
    if VERBOSE:
        print(msg)

with open(METADATA, encoding='utf-8', errors='ignore') as fh:
    reader = csv.DictReader(fh)
    for idx, row in enumerate(reader, start=1):
        if PROCESS_LIMIT and idx > PROCESS_LIMIT:
            break

        title = (row.get('Title') or row.get('title') or "").strip()
        author = (row.get('Authors') or row.get('Author') or row.get('authors') or "").strip()
        etext = (row.get('Etext Number') or row.get('Etext') or row.get('ETextNumber') or row.get('etextno') or "").strip()
        plain_text_field = row.get('Plain Text UTF-8') or row.get('Plain Text') or row.get('PlainTextUTF8') or ""

        if not title:
            continue

        norm = normalize_text(title)

        # --- RESUME LOGIC ---
        # Skip any book that already has a file_path
        existing_books_with_file = Book.objects.filter(title__iexact=title).exclude(file_path__isnull=True)
        if existing_books_with_file.exists():
            debug(f"[{idx}] Skipped (already has file_path): {title}")
            continue

        file_path = None
        # 1) try find file by etext
        if etext:
            file_path = find_file_for_etext(GUTENBERG_FOLDER, etext)
        # 2) try plain_text_field filename if available
        if not file_path and plain_text_field:
            candidate = os.path.basename(plain_text_field).strip()
            p = os.path.join(GUTENBERG_FOLDER, candidate)
            if os.path.exists(p):
                file_path = p

        # 3) match DB books by normalized title
        candidates = title_map.get(norm, [])
        chosen_book = None
        match_type = None

        if candidates:
            # if only one candidate use it
            if len(candidates) == 1:
                chosen_book = candidates[0]
                match_type = "exact"
            else:
                # prefer one with file_path already, else the one with highest popularity
                chosen_book = None
                for c in candidates:
                    if c.get('file_path'):
                        chosen_book = c
                        match_type = "exact_existing_file"
                        break
                if not chosen_book:
                    chosen_book = max(candidates, key=lambda x: x.get('popularity', 0))
                    match_type = "exact_best_popularity"
        else:
            # fuzzy title matching using difflib
            close = get_close_matches(norm, norm_titles, n=3, cutoff=FUZZY_CUTOFF)
            if close:
                fuzzy_used += 1
                best_choice = None
                best_score = -1.0
                for cn in close:
                    cands = title_map.get(cn, [])
                    for c in cands:
                        s_title = SequenceMatcher(None, norm, cn).ratio()
                        s_author = author_similarity(author, c.get('author') or "")
                        score = s_title + (0.2 * s_author)
                        if score > best_score:
                            best_score = score
                            best_choice = c
                if best_choice:
                    chosen_book = best_choice
                    match_type = f"fuzzy(score={best_score:.2f})"

        if not chosen_book:
            unmatched.append(title)
            debug(f"[{idx}] UNMATCHED: {title}")
            continue

        matched += 1
        book_id = chosen_book['id']
        other_books_qs = Book.objects.filter(title__iexact=title).exclude(id=book_id)

        # Print planned action
        print(f"[{idx}] Matched: '{title[:80]}' -> book_id={book_id} (match={match_type}) file_found={'YES' if file_path else 'NO'} other_duplicates={other_books_qs.count()}")

        if DRY_RUN:
            if file_path and not chosen_book.get('file_path'):
                print(f"    DRY: would set file_path -> {file_path}")
            if other_books_qs.exists():
                print(f"    DRY: would move UserBook rows from {other_books_qs.count()} duplicate(s) -> book_id={book_id}")
            continue

        # APPLY (transactional)
        with transaction.atomic():
            # update file_path if missing
            book_obj = Book.objects.get(id=book_id)
            if file_path and not book_obj.file_path:
                book_obj.file_path = file_path
                book_obj.save(update_fields=['file_path'])
                file_updates += 1
                print(f"    APPLIED: set file_path for book id={book_id}")

            # move UserBook rows from other_books to chosen book
            moved_total = 0
            for ob in other_books_qs:
                moved = UserBook.objects.filter(book=ob).update(book_id=book_id)
                if moved:
                    ratings_moved += moved
                    moved_total += moved
                    print(f"    APPLIED: moved {moved} UserBook rows from book id={ob.id} -> {book_id}")
                # optionally delete ob (only if flag set)
                if DELETE_DUPS:
                    ob.delete()
                    duplicate_targets += 1
                    print(f"    APPLIED: deleted duplicate Book id={ob.id}")

# SUMMARY
print("\n=== SUMMARY ===")
print("DRY_RUN:", DRY_RUN)
print("Total matched rows:", matched)
print("Unmatched rows:", len(unmatched))
print("Fuzzy matches used:", fuzzy_used)
print("File updates applied:" if not DRY_RUN else "File updates (would apply):", file_updates)
print("Ratings moved applied:" if not DRY_RUN else "Ratings moved (would apply):", ratings_moved)
if DELETE_DUPS:
    print("Duplicate Book rows deleted (applied):", duplicate_targets)
if unmatched:
    print("\nSample unmatched titles (first 10):")
    for t in unmatched[:10]:
        print(" -", t)
