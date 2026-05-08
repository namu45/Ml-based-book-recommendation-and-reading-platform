from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count
from recommender.models import Book, UserBook, ReadingHistory, DownloadLog

def is_admin_user(user):
    return user.is_staff or user.is_superuser

def admin_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user and is_admin_user(user):
            login(request, user)
            return redirect('admin_dashboard')
        else:
            return render(request, 'custom_admin/login.html', {'error': 'Invalid credentials or not authorized'})
    return render(request, 'custom_admin/login.html')

@login_required
def admin_logout(request):
    logout(request)
    return redirect('admin_login')

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard(request):
    # Total metrics
    total_users = User.objects.filter(
    is_staff=False,
    is_superuser=False
).exclude(email='').count()
    total_books = Book.objects.count()
    total_downloads = DownloadLog.objects.count()
    total_reviews = UserBook.objects.exclude(review__isnull=True).exclude(review__exact='').count()
    total_favorites = UserBook.objects.filter(status='favorite').count()

    # Recent activity from UserBook
    recent_reads = UserBook.objects.select_related('user','book')\
        .filter(status='read')\
        .order_by('-id')[:5]

    recent_favorites = UserBook.objects.select_related('user','book')\
        .filter(status='favorite')\
        .order_by('-id')[:5]
    # Recent user registrations (last 5)
    recent_registrations = User.objects.filter(is_staff=False).order_by('-date_joined')[:5]
    recent_reviews = UserBook.objects.select_related('user','book')\
        .exclude(review__isnull=True)\
        .exclude(review__exact='')\
        .order_by('-id')[:5]

    context = {
        'total_users': total_users,
        'total_books': total_books,
        'total_downloads': total_downloads,
        'total_reviews': total_reviews,
        'total_favorites': total_favorites,
        'recent_reads': recent_reads,
        'recent_reviews': recent_reviews,
        'recent_favorites': recent_favorites,
        'recent_registrations': recent_registrations,  # <--- add this
    }

    return render(request, 'custom_admin/dashboard.html', context)

# =====================
# Users Management
# =====================
from django.db.models import Q
from django.contrib.auth.models import User

# =====================
# Users Management
# =====================

# =====================
# Users Management (Single Page)
# =====================

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django import forms


class AdminUserForm(forms.ModelForm):
    password = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'password']


@login_required
@user_passes_test(is_admin_user)
def admin_users(request):

    query = request.GET.get('q')
    edit_id = request.GET.get('edit')

    # Real users only
    users = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).exclude(email__isnull=True).exclude(email__exact='')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    users = users.order_by('-date_joined')

    # ADD or EDIT
    if edit_id:
        user_instance = get_object_or_404(User, id=edit_id)
    else:
        user_instance = None

    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=user_instance)

        if form.is_valid():
            user = form.save(commit=False)

            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)

            user.save()
            return redirect('admin_users')
    else:
        form = AdminUserForm(instance=user_instance)

    context = {
        'users': users,
        'form': form,
        'query': query,
        'total_users': users.count(),
        'editing': edit_id is not None
    }

    return render(request, 'custom_admin/users.html', context)


@login_required
@user_passes_test(is_admin_user)
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    return redirect('admin_users')


@login_required
@user_passes_test(is_admin_user)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('admin_users')


# =====================
# UserBook Management
# =====================
# =====================
# UserBook Management View
# =====================
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from recommender.models import UserBook, Book
from django.contrib.auth.models import User
from django import forms

# Admin check
def is_admin_user(user):
    return user.is_staff

# Admin form for UserBook
class UserBookAdminForm(forms.ModelForm):
    class Meta:
        model = UserBook
        fields = ['user', 'book', 'status', 'rating', 'review', 'read_clicked', 'last_page']
        widgets = {
            'status': forms.Select(attrs={'class':'form-select'}),
            'rating': forms.NumberInput(attrs={'min':1,'max':5}),
            'review': forms.Textarea(attrs={'rows':2}),
            'last_page': forms.NumberInput(attrs={'min':1}),
            'read_clicked': forms.CheckboxInput(),
        }

@login_required
@user_passes_test(is_admin_user)
def admin_userbooks(request):
    query = request.GET.get('q', '').strip()

    userbooks = UserBook.objects.select_related('user','book') \
        .filter(user__email__isnull=False).exclude(user__email='')

    if query:
        userbooks = userbooks.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(book__title__icontains=query)
        )

    editing = False
    form = None
    edit_id = request.GET.get('edit')

    # ✅ ONLY load form when editing OR adding
    if edit_id:
        editing = True
        instance = get_object_or_404(UserBook, pk=edit_id)
        form = UserBookAdminForm(instance=instance)

    context = {
        'userbooks': userbooks,
        'query': query,
        'form': form,
        'editing': editing,
    }
    return render(request, 'custom_admin/userbooks.html', context)
@login_required
@user_passes_test(is_admin_user)
def toggle_favorite(request, pk):
    ub = get_object_or_404(UserBook, pk=pk)
    ub.status = 'favorite' if ub.status != 'favorite' else 'read'
    ub.save()
    return redirect('admin_userbooks')

@login_required
@user_passes_test(is_admin_user)
def delete_userbook(request, pk):
    ub = get_object_or_404(UserBook, pk=pk)
    ub.delete()
    return redirect('admin_userbooks')


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django import forms
from recommender.models import Book

# Admin check
def is_admin_user(user):
    return user.is_staff

# Admin form for Book
class BookAdminForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'genre', 'isbn', 'description', 'cover_url', 'cover_image', 'file_path', 'source', 'total_pages']
        widgets = {
            'description': forms.Textarea(attrs={'rows':3}),
            'total_pages': forms.NumberInput(attrs={'min':1}),
            'source': forms.Select(attrs={'class':'form-select'}),
        }

@login_required
@user_passes_test(is_admin_user)
def admin_books(request):
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')  # all, with_file, without_file

    books = Book.objects.all()

    # Filtering
    if filter_type == 'with_file':
        books = books.exclude(file_path__isnull=True).exclude(file_path__exact='')
    elif filter_type == 'without_file':
        books = books.filter(Q(file_path__isnull=True) | Q(file_path__exact=''))

    # Search
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(genre__icontains=query) |
            Q(isbn__icontains=query)
        )

    # Pagination: 20 books per page
    paginator = Paginator(books, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Edit / Add book form
    editing = False
    form = None
    edit_id = request.GET.get('edit')
    if edit_id:
        editing = True
        instance = get_object_or_404(Book, pk=edit_id)
        if request.method == 'POST':
            form = BookAdminForm(request.POST, request.FILES, instance=instance)
            if form.is_valid():
                form.save()
                return redirect('admin_books')
        else:
            form = BookAdminForm(instance=instance)
    else:
        if request.method == 'POST':
            form = BookAdminForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                return redirect('admin_books')
        else:
            form = BookAdminForm()

    context = {
        'books': page_obj,
        'query': query,
        'filter_type': filter_type,
        'form': form,
        'editing': editing,
    }
    return render(request, 'custom_admin/books.html', context)

@login_required
@user_passes_test(is_admin_user)
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    book.delete()
    return redirect('admin_books')