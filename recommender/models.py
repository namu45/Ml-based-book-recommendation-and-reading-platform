from django.db import models
from django.contrib.auth.models import User

# ============================
# BOOK MODEL
# ============================
class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    genre = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=13, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    cover_url = models.URLField(blank=True, null=True)
    cover_image = models.ImageField(
        upload_to='book_covers/',
        blank=True,
        null=True
    )   
    file_path = models.CharField(max_length=500, blank=True, null=True)
    source = models.CharField(
        max_length=10,
        choices=(('BX', 'Book-Crossing'), ('GUT', 'Gutenberg')),
        default='BX'
    )

    # NEW: optional total page count (useful for page tracking)
    total_pages = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']

    @property
    def safe_cover(self):
        """Return a valid cover URL or fallback to default image."""
        return self.cover_url or '/static/images/default_cover.jpg'

    @property
    def display_author(self):
        """Return author name or 'Unknown Author'."""
        return self.author if self.author else "Unknown Author"

    @property
    def display_genre(self):
        """Return genre or 'Unknown'."""
        return self.genre if self.genre else "Unknown"
    
    @property
    def display_description(self):
        """
        Return the actual description if available,
        otherwise fallback text.
        """
        if self.description and self.description != "No description available.":
            return self.description
        return "No description available."

    
    



# ============================
# USERBOOK MODEL
# ============================
class UserBook(models.Model):
    STATUS_CHOICES = (
        ('read', 'Read'),
        ('favorite', 'Favorite'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='read')
    rating = models.IntegerField(blank=True, null=True)
    review = models.TextField(blank=True, null=True)
    sentiment_score = models.FloatField(blank=True, null=True)
    read_clicked = models.BooleanField(default=False)
    last_page = models.PositiveIntegerField(default=1) 

    def __str__(self):
        return f"{self.user.username} - {self.book.title}"

    class Meta:
        unique_together = ('user', 'book')

    @property
    def is_favorite(self):
        return self.status == 'favorite'

    @property
    def display_rating(self):
        return self.rating if self.rating is not None else "-"


# ============================
# READING HISTORY MODEL
# ============================
class ReadingHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    current_page = models.IntegerField(default=1)
    last_read = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} reading {self.book.title} (Page {self.current_page})"


# ============================
# DOWNLOAD LOG MODEL
# ============================
class DownloadLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    format = models.CharField(max_length=10, default="pdf")

    def __str__(self):
        return f"{self.user.username} downloaded {self.book.title} ({self.format.upper()})"
