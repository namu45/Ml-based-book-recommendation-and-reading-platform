import os
import django
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
django.setup()

from recommender.models import Book
from django.core.files.base import ContentFile

def download_and_save(book):
    try:
        if book.isbn:
            url = f"https://covers.openlibrary.org/b/isbn/{book.isbn}-M.jpg"
        else:
            title = book.title.replace(" ", "+").replace(":", "")
            url = f"https://covers.openlibrary.org/b/title/{title}-M.jpg"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            filename = f"{book.id}.jpg"
            book.cover_image.save(filename, ContentFile(response.content), save=True)
            return f"Saved cover for: {book.title}"
        else:
            return f"No cover found for: {book.title}"
    except Exception as e:
        return f"Error for {book.title}: {e}"

books = Book.objects.filter(cover_image__isnull=True)
print(f"Books to process: {books.count()}")

with ThreadPoolExecutor(max_workers=20) as executor:  # 20 parallel downloads
    futures = [executor.submit(download_and_save, book) for book in books]
    for future in as_completed(futures):
        print(future.result())

print("✅ All done")
