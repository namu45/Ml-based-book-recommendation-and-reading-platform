# recommender/views_helpers.py

from django.db.models import Avg, Count, Value, FloatField
from django.db.models.functions import Coalesce
from recommender.models import UserBook

def _get_book_rating_stats(book):
    """
    Returns (avg_rating_display, num_ratings)
    avg_rating_display is scaled (half-star) or None
    """
    rating_data = UserBook.objects.filter(book=book).aggregate(
        avg_rating=Coalesce(Avg('rating', output_field=FloatField()), Value(0.0)),
        num_ratings=Count('rating')
    )
    num = rating_data['num_ratings']
    if num > 0:
        avg = rating_data['avg_rating']
        display = round(avg / 2, 1)
        return display, num
    return None, 0