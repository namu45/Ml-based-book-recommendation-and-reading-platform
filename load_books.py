import csv
import os
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bookwise.settings")
django.setup()

from recommender.models import Book

# Path to your dataset
dataset_path = os.path.join(os.getcwd(), "datasets", "BX-Books.csv")

with open(dataset_path, encoding='latin-1') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        isbn = row.get('ISBN')
        title = row.get('Book-Title')
        author = row.get('Book-Author')
        try:
            Book.objects.create(
                isbn=isbn,
                title=title,
                author=author,
                cover_url=''  # we can fetch covers later
            )
        except:
            # Skip duplicates
            continue

print("Book-Crossing data loaded successfully!")
