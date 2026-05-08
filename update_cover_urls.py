# import os
# import django

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
# django.setup()

# from recommender.models import Book

# for book in Book.objects.all():
#     if not book.cover_url:
#         if book.isbn:
#             book.cover_url = f"https://covers.openlibrary.org/b/isbn/{book.isbn}-L.jpg"
#         else:
#             title_for_url = book.title.replace(' ', '+')
#             book.cover_url = f"https://covers.openlibrary.org/b/title/{title_for_url}-L.jpg"
#         book.save()
#         print(f"Updated cover for: {book.title}")



import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
django.setup()

from recommender.models import Book
from django.db import transaction

# Get books without a cover URL
books_to_update = Book.objects.filter(cover_url__isnull=True) | Book.objects.filter(cover_url__exact='')

batch_size = 100  # process 100 books at a time
total = books_to_update.count()
print(f"Total books to update: {total}")

updated_count = 0
books_batch = []

for idx, book in enumerate(books_to_update, start=1):
    if book.isbn:
        book.cover_url = f"https://covers.openlibrary.org/b/isbn/{book.isbn}-L.jpg"
    else:
        title_for_url = book.title.replace(' ', '+').replace(':', '').replace('&', 'and')
        book.cover_url = f"https://covers.openlibrary.org/b/title/{title_for_url}-L.jpg"
    
    books_batch.append(book)
    
    if len(books_batch) >= batch_size:
        with transaction.atomic():
            Book.objects.bulk_update(books_batch, ['cover_url'])
        updated_count += len(books_batch)
        print(f"Updated {updated_count}/{total} books...")
        books_batch = []

# Update remaining books
if books_batch:
    with transaction.atomic():
        Book.objects.bulk_update(books_batch, ['cover_url'])
    updated_count += len(books_batch)
    print(f"Updated {updated_count}/{total} books...")

print("All cover URLs updated successfully!")
