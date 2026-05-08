import sys
import os
import csv
import time

# ===== Add project root to Python path =====
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ===== Setup Django =====
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookwise.settings')
import django
django.setup()

from recommender.models import Book

# ===== Metadata CSV =====
METADATA_FILE = os.path.join(os.getcwd(), "datasets", "gutenberg_metadata.csv")

# ===== Read metadata into a dictionary =====
metadata_map = {}
with open(METADATA_FILE, encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f)
    for row in reader:
        etext = row.get('Etext Number')
        metadata_map[etext] = {
            "title": row.get("Title") or "",
            "author": row.get("Authors") or "",
            "issued": row.get("Issued") or "",
            "subjects": [s.strip() for s in (row.get("Subjects") or "").split(";") if s.strip()],
        }

# ===== Human-friendly, professional description generator =====
def generate_description(book, metadata=None):
    """
    Returns a professional, natural-sounding description for a book.
    Author always comes from DB.
    Subjects cleaned and limited to 5. Issued date included if available.
    """
    title = book.title
    author = book.author or "Unknown Author"

    # Issued date only if available in metadata
    issued = metadata.get("issued") if metadata and metadata.get("issued") else None

    # Subjects: take up to 5 and clean '--'
    subjects = []
    if metadata and metadata.get("subjects"):
        for s in metadata["subjects"][:5]:
            if "--" in s:
                parts = [p.strip() for p in s.split("--")]
                s = f"{parts[1]}: {parts[0]}" if len(parts) == 2 else s
            subjects.append(s)

    # Start description
    desc = f"'{title}' is a book by {author}"
    if issued:
        desc += f", published on {issued}"
    desc += "."

    # Add subjects naturally
    if subjects:
        if len(subjects) == 1:
            desc += f" It explores themes of {subjects[0]}."
        else:
            desc += " It explores themes such as " + ", ".join(subjects[:-1]) + f", and {subjects[-1]}."

    return desc


# ===== Update all books (overwrite existing descriptions) =====
books = Book.objects.all()
total = books.count()
print(f"Total books to process: {total}")

# Optional: resume from last processed book
start_index = 0

for idx, book in enumerate(books[start_index:], start=start_index + 1):
    print(f"[{idx}/{total}] Processing: {book.title}")

    # Match metadata by title
    meta = None
    for data in metadata_map.values():
        if data['title'].lower() == book.title.lower():
            meta = data
            break

    if not meta:
        meta = {"title": book.title, "author": "", "issued": "", "subjects": []}

    # Generate enhanced description
    book.description = generate_description(book, meta)
    book.save(update_fields=['description'])

    # Tiny delay for safe stopping/resuming
    time.sleep(0.01)

print("✅ All book descriptions updated with professional blurbs!")
