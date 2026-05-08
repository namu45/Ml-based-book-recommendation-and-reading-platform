from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, ProfileUpdateForm, ProfileImageForm, PasswordUpdateForm
from .models import Profile
from django.db import IntegrityError
from recommender.models import UserBook


# Registration

def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                # Only create Profile if it doesn't exist
                Profile.objects.get_or_create(user=user)
            except IntegrityError:
                # If profile already exists, just ignore
                pass
            
            messages.success(request, "🎉 Account created successfully! Please login.")
            return redirect('accounts:login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

# Login
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "✅ Logged in successfully!")
            return redirect('recommender:dashboard')
        else:
            messages.error(request, "❌ Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

# Logout
def logout_view(request):
    logout(request)
    return redirect('accounts:login')

# Profile Settings
@login_required
def profile_view(request):
    user = request.user
    profile = user.profile  # OneToOne Profile

    if request.method == "POST":
        user_form = ProfileUpdateForm(request.POST, instance=user)
        profile_form = ProfileImageForm(request.POST, request.FILES, instance=profile)
        password_form = PasswordUpdateForm(user, request.POST)

        # Update profile info
        if 'update_profile' in request.POST:
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "✅ Profile updated successfully!")
                return redirect('accounts:profile')

        # Change password
        if 'change_password' in request.POST:
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "✅ Password changed successfully!")
                return redirect('accounts:profile')
            else:
                messages.error(request, "❌ Please correct the password errors.")

    else:
        user_form = ProfileUpdateForm(instance=user)
        profile_form = ProfileImageForm(instance=profile)
        password_form = PasswordUpdateForm(user)

    # ➤ ADD SIDEBAR COUNTS HERE
    books_read = UserBook.objects.filter(
        user=request.user, status='read', read_clicked=True
    ).count()

    favorites_count = UserBook.objects.filter(
        user=request.user, status='favorite'
    ).count()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'books_read': books_read,
        'favorites_count': favorites_count,
    }
    return render(request, 'accounts/profile.html', context)
