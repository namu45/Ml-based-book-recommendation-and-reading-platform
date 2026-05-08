from django.contrib import admin
from .models import Book, UserBook

# Inline ratings inside Book admin
class UserBookInline(admin.TabularInline):
    model = UserBook
    extra = 0
    readonly_fields = ('user', 'rating', 'status')

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    # Show file_path column in admin
    list_display = ('title', 'author', 'source', 'isbn', 'file_path')
    list_filter = ('source',)
    search_fields = ('title', 'author', 'isbn')
    inlines = [UserBookInline]   # <-- added inline ratings

# Separate UserBook admin section
@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'rating', 'status')
    list_filter = ('status', 'rating')
    search_fields = ('user__username', 'book__title')
