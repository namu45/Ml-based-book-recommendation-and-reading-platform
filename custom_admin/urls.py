from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('', views.admin_dashboard, name='admin_dashboard'),
       path('users/', views.admin_users, name='admin_users'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin-books/', views.admin_books, name='admin_books'),

    # Edit a book
    # path('admin-books/edit/<int:pk>/', views.edit_book, name='edit_book'),

    # Delete a book
    path('admin-books/delete/<int:pk>/', views.delete_book, name='delete_book'),
        path('userbooks/', views.admin_userbooks, name='admin_userbooks'),
    path('userbooks/toggle-favorite/<int:pk>/', views.toggle_favorite, name='toggle_favorite'),
    path('userbooks/delete/<int:pk>/', views.delete_userbook, name='delete_userbook'),
]