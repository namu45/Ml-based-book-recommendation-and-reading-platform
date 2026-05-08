import csv
import os
import django

# Setup Django environment first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
django.setup()

from django.contrib.auth.models import User
from recommender.models import Book, UserBook

# Path to dataset
ratings_csv = os.path.join(os.getcwd(), "datasets", "BX-Book-Ratings.csv")

# Function to get or create a user
def get_or_create_user(user_id, user_cache={}):
    if user_id in user_cache:
        return user_cache[user_id]
    username = f"user_{user_id}"
    user, created = User.objects.get_or_create(username=username)
    user_cache[user_id] = user
    return user

# Parameters for bulk saving
batch_size = 1000
user_books_batch = []
saved_count = 0
processed_count = 0
user_cache = {}

# Read BX ratings CSV
with open(ratings_csv, encoding='latin-1') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        user_id = row.get('User-ID')
        isbn = row.get('ISBN')
        rating = row.get('Book-Rating')

        if not user_id or not isbn or rating is None:
            continue

        # Get book by ISBN
        try:
            book = Book.objects.get(isbn=isbn)
        except Book.DoesNotExist:
            continue  # skip if book not found

        # Get or create user
        user = get_or_create_user(user_id, user_cache)

        # Avoid duplicate entries
        if UserBook.objects.filter(user=user, book=book).exists():
            continue

        # Prepare UserBook object for bulk save
        user_books_batch.append(UserBook(
            user=user,
            book=book,
            rating=int(rating),
            status='read'
        ))

        processed_count += 1

        # Bulk save every batch_size
        if len(user_books_batch) >= batch_size:
            UserBook.objects.bulk_create(user_books_batch)
            saved_count += len(user_books_batch)
            print(f"Processed {processed_count} rows, saved {saved_count} ratings so far...")
            user_books_batch = []

# Save any remaining entries
if user_books_batch:
    UserBook.objects.bulk_create(user_books_batch)
    saved_count += len(user_books_batch)
    print(f"Processed {processed_count} rows, saved {saved_count} ratings in total.")

print(f"BX Ratings loaded successfully! Total ratings saved: {saved_count}")
