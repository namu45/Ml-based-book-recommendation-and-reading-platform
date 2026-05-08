import os
import django
import requests
import time

# ===== Setup Django environment =====
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookwise.settings')
django.setup()

from recommender.models import Book

# ===== Open Library API function =====
def fetch_description(isbn):
    if not isbn:
        return None
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        key = f"ISBN:{isbn}"
        if key in data and 'description' in data[key]:
            desc = data[key]['description']
            # Description can be dict or string
            if isinstance(desc, dict):
                return desc.get('value', None)
            elif isinstance(desc, str):
                return desc
    except Exception as e:
        print(f"Error fetching ISBN {isbn}: {e}")
    return None

# ===== Update descriptions for all books =====
books = Book.objects.all()
total = books.count()
print(f"Total books: {total}")

for idx, book in enumerate(books, start=1):
    print(f"[{idx}/{total}] Processing: {book.title} (ISBN: {book.isbn})")
    
    # Fetch description
    desc = fetch_description(book.isbn)
    
    # If no description from API, use fallback
    if not desc:
        desc = "No description available."
    
    # Save to DB immediately
    book.description = desc
    book.save()
    
    # Optional: small delay to avoid overwhelming API
    time.sleep(0.1)

print("All books processed and saved.")
