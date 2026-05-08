# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.landing_page, name='landing'),
#     # path('books/', views.book_list, name='book_list'),  # Assuming book_list already exists
#     # other urls like register, login will come later
# ]
from django.urls import path
from . import views
app_name = 'recommender'
urlpatterns = [
    path('', views.landing_page, name='landing'),
        path('dashboard/', views.dashboard_view, name='dashboard'), 
         path('browse/', views.browse_books_view, name='browse_books'),
        #  path('recommendations/', views.recommendations_view, name='recommendations'),
        path('books/<int:book_id>/detail/', views.book_detail_view, name='book_detail'),  # <-- this is needed
    #      path('books/<int:book_id>/read/', views.read_book_view, name='read_book'),
          
    # path('books/<int:book_id>/reader-ajax/', views.reader_ajax_view, name='reader_ajax'),
    
    # path('books/<int:book_id>/download/', views.download_book_pdf, name='download_book'),
    path('books/<int:book_id>/read/', views.read_book_view, name='read_book'),

    # AJAX endpoint for bookmarks, favorites, history
    path('books/<int:book_id>/read/ajax/', views.reader_ajax_view, name='reader_ajax_view'),

    # Download as PDF
    path('books/<int:book_id>/read/download/', views.download_book_pdf, name='download_book_pdf'),
    path('recommendations/', views.collaborative_recommendations_view, name='recommendations'),
]


