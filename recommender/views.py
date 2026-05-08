from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Value, FloatField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from recommender.models import Book, UserBook
from textblob import TextBlob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import math, json, os
from .preprocessor import preprocess_book


# ------------------ HELPERS ------------------
def _get_book_rating_stats(book):
    """Return (avg_rating_display, num_ratings). avg_rating_display is scaled (half-star) or None."""
    rating_data = UserBook.objects.filter(book=book).aggregate(
        avg_rating=Coalesce(Avg('rating', output_field=FloatField()), Value(0.0)),
        num_ratings=Count('rating')
    )
    num = rating_data['num_ratings']
    if num > 0:
        avg = rating_data['avg_rating']
        # convert from 1-5 raw to half-star display as in your UI (divide by 2)
        display = round(avg / 2, 1)
        return display, num
    return None, 0


# ------------------ LANDING ------------------
def landing_page(request):
    return render(request, 'recommender/landing.html')


# ------------------ DASHBOARD ------------------
@login_required
def dashboard_view(request):
    # Only include UserBook entries where the user actually clicked "Read" (read_clicked=True)
    recent_reads_qs = UserBook.objects.filter(
        user=request.user, status='read', read_clicked=True
    ).order_by('-id')[:6]

    recent_reads = []
    recent_book_ids = []

    for ub in recent_reads_qs:
        display_rating, num_ratings = _get_book_rating_stats(ub.book)
        read_available = bool(ub.book.file_path)
        author_name = ub.book.author if ub.book.author else "Unknown"

        recent_reads.append({
            'id': ub.book.id,
            'title': ub.book.title,
            'author': author_name,
            'cover_url': ub.book.cover_url or '/static/images/default_cover.jpg',
            'file_path': ub.book.file_path,
            'source': ub.book.source,
            'avg_rating': display_rating if display_rating is not None else "No rating yet",
            'num_ratings': num_ratings,
            'can_read': read_available,
        })
        recent_book_ids.append(ub.book.id)

    # Weighted recommendations (original logic preserved)
    m = 5
    global_avg = UserBook.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    recommended_books_qs = Book.objects.filter(source='BX', file_path__isnull=False).annotate(
        avg_rating=Coalesce(Avg('userbook__rating', output_field=FloatField()), Value(0.0)),
        num_ratings=Count('userbook')
    ).exclude(id__in=recent_book_ids)

    weighted_books = []
    for b in recommended_books_qs:
        v = b.num_ratings
        R = b.avg_rating
        WR = (v / (v + m)) * R + (m / (v + m)) * global_avg if (v + m) > 0 else R
        weighted_books.append((WR, b))

    weighted_books.sort(key=lambda x: x[0], reverse=True)

    recommended_books = []
    seen_titles = set()
    for WR, b in weighted_books[:8]:
        if b.title not in seen_titles:
            seen_titles.add(b.title)
            display_rating = round(b.avg_rating / 2, 1) if b.num_ratings > 0 else None
            read_available = bool(b.file_path)
            recommended_books.append({
                'id': b.id,
                'title': b.title,
                'author': b.author if b.author else "Unknown",
                'cover_url': b.cover_url or '/static/images/default_cover.jpg',
                'file_path': b.file_path,
                'source': b.source,
                'avg_rating': display_rating if display_rating is not None else "No rating yet",
                'num_ratings': b.num_ratings,
                'can_read': read_available,
            })

    books_read = UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count()
    favorites_count = UserBook.objects.filter(user=request.user, status='favorite').count()

    return render(request, 'recommender/dashboard.html', {
        'recent_reads': recent_reads,
        'recommended_books': recommended_books,
        'books_read': books_read,
        'favorites_count': favorites_count,
    })


# ------------------ BROWSE ------------------
@login_required
def browse_books_view(request):
    books_qs = Book.objects.annotate(
        avg_rating=Coalesce(Avg('userbook__rating', output_field=FloatField()), Value(0.0)),
        num_ratings=Count('userbook')
    ).order_by('-avg_rating', '-num_ratings', '-id')[:50]

    books = []
    for b in books_qs:
        display_rating = round(b.avg_rating / 2, 1) if b.num_ratings > 0 else None
        read_available = bool(b.file_path)
        books.append({
            'id': b.id,
            'title': b.title,
            'author': b.author if b.author else "Unknown",
            'cover_url': b.cover_url or '/static/images/default_cover.jpg',
            'file_path': b.file_path,
            'source': b.source,
            'avg_rating': display_rating if display_rating is not None else "No rating yet",
            'num_ratings': b.num_ratings,
            'can_read': read_available,
        })

    return render(request, 'recommender/browse_books.html', {'books': books})


# ------------------ RECOMMENDATIONS ------------------
@login_required
def recommendations_view(request):
    recommended_books_qs = Book.objects.annotate(
        avg_rating=Coalesce(Avg('userbook__rating', output_field=FloatField()), Value(0.0)),
        num_ratings=Count('userbook')
    ).order_by('-avg_rating', '-num_ratings', '-id')[:50]

    recommended_books = []
    seen_titles = set()
    for b in recommended_books_qs:
        if b.title not in seen_titles:
            seen_titles.add(b.title)
            display_rating = round(b.avg_rating / 2, 1) if b.num_ratings > 0 else None
            read_available = bool(b.file_path)
            recommended_books.append({
                'id': b.id,
                'title': b.title,
                'author': b.author if b.author else "Unknown",
                'cover_url': b.cover_url or '/static/images/default_cover.jpg',
                'file_path': b.file_path,
                'source': b.source,
                'avg_rating': display_rating if display_rating is not None else "No rating yet",
                'num_ratings': b.num_ratings,
                'can_read': read_available,
            })

    return render(request, 'recommender/recommendations.html', {'recommended_books': recommended_books})


# ------------------ BOOK DETAIL ------------------
@login_required
def book_detail_view(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    userbook, _ = UserBook.objects.get_or_create(user=request.user, book=book)

    # Handle AJAX POST requests (rating, review, favorite, mark_read, undo_rating)
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        data = json.loads(request.body)

        # ------- Rating -------
        if 'rating' in data:
            # rating should NOT implicitly mark as read (per your rule)
            try:
                userbook.rating = int(data['rating'])
            except (TypeError, ValueError):
                userbook.rating = None
            userbook.save()

            avg_display, num = _get_book_rating_stats(book)
            books_read = UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count()
            favorites_count = UserBook.objects.filter(user=request.user, status='favorite').count()
            return JsonResponse({
                "success": True,
                "user_rating": userbook.rating,
                "avg_rating": avg_display if avg_display is not None else "No rating yet",
                "num_ratings": num,
                "books_read": books_read,
                "favorites_count": favorites_count
            })

        # ------- Favorite / Undo favorite -------
        if 'favorite' in data:
            # Toggle favorite robustly without setting status to None (invalid)
            currently_fav = (userbook.status == 'favorite')
            if currently_fav:
                # undo favorite: restore to 'read' if the user has actually read it,
                # otherwise keep default 'read' (you can change to another behavior later)
                userbook.status = 'read'
                is_favorite = False
            else:
                # set favorite — preserve read_clicked if already True
                userbook.status = 'favorite'
                is_favorite = True
            userbook.save()

            books_read = UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count()
            favorites_count = UserBook.objects.filter(user=request.user, status='favorite').count()
            return JsonResponse({
                "success": True,
                "is_favorite": is_favorite,
                "books_read": books_read,
                "favorites_count": favorites_count
            })

        # ------- Review / Sentiment -------
        if 'review' in data:
            review_text = (data.get('review') or "").strip()
            userbook.review = review_text if review_text else None
            if review_text:
                sentiment = TextBlob(review_text).sentiment.polarity
                userbook.sentiment_score = round(sentiment, 2)
            else:
                userbook.sentiment_score = None
            userbook.save()

            # compute avg sentiment for the book for quick feedback
            all_reviews = UserBook.objects.filter(book=book).exclude(review__isnull=True).exclude(review__exact="")
            sentiments = [ub.sentiment_score for ub in all_reviews if ub.sentiment_score is not None]
            avg_sentiment = round(np.mean(sentiments), 2) if sentiments else None

            # human-friendly feedback
            if userbook.sentiment_score is not None:
                if userbook.sentiment_score > 0.2:
                    sentiment_feedback = "👍 Positive"
                elif userbook.sentiment_score < -0.2:
                    sentiment_feedback = "👎 Negative"
                else:
                    sentiment_feedback = "😐 Neutral"
            else:
                sentiment_feedback = "No sentiment"

            return JsonResponse({
                "success": True,
                "sentiment_feedback": sentiment_feedback,
                "avg_sentiment": avg_sentiment
            })

        # ------- Undo Rating -------
        if 'undo_rating' in data:
            userbook.rating = None
            # keep status as 'read' if read_clicked else keep 'read' default (avoid None)
            if getattr(userbook, 'read_clicked', False):
                userbook.status = 'read'
            else:
                userbook.status = 'read'
            userbook.save()

            avg_display, num = _get_book_rating_stats(book)
            return JsonResponse({
                "success": True,
                "avg_rating": avg_display if avg_display is not None else "No rating yet",
                "num_ratings": num
            })

        # ------- Mark as Read (clicked Read button) -------
        if 'mark_read' in data:
            userbook.status = 'read'
            # ensure the model has read_clicked field — set True
            setattr(userbook, 'read_clicked', True)
            userbook.read_clicked = True
            userbook.save()
            books_read = UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count()
            return JsonResponse({"success": True, "books_read": books_read})

        return JsonResponse({"success": False})

    # Normal GET render
    user_rating = userbook.rating or 0
    is_favorite = (userbook.status == 'favorite')

    avg_display, num_ratings = _get_book_rating_stats(book)

    # Recommendations (content-based TF-IDF)
    recommended_books = []
    books_qs = Book.objects.filter(source='BX', file_path__isnull=False).exclude(id=book.id).values('id', 'title', 'author', 'description', 'cover_url')

    if books_qs:
        corpus = [book.title + " " + (book.author or "") + " " + (book.description or "")]
        corpus += [b['title'] + " " + (b['author'] or "") + " " + (b['description'] or "") for b in books_qs]
        tfidf = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf.fit_transform(corpus)
        cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        valid_indices = [i for i, sim in enumerate(cosine_sim) if sim > 0]
        top_indices = sorted(valid_indices, key=lambda i: cosine_sim[i], reverse=True)[:5]
        # top_indices = cosine_sim.argsort()[-5:][::-1]
        similar_books = [list(books_qs)[i] for i in top_indices]
        for b in similar_books:
            author_name = b['author'] if b['author'] else "Unknown"
            avg_b_display, _ = _get_book_rating_stats(Book.objects.get(id=b['id']))
            recommended_books.append({
                'id': b['id'],
                'title': b['title'],
                'author': author_name,
                'cover_url': b['cover_url'] or '/static/images/default_cover.jpg',
                'avg_rating': avg_b_display if avg_b_display is not None else "No rating yet",
                'detail_url': f"/books/{b['id']}/detail/"
            })

    # Aggregate sentiment for display
    all_reviews = UserBook.objects.filter(book=book).exclude(review__isnull=True).exclude(review__exact="")
    sentiments = [ub.sentiment_score for ub in all_reviews if ub.sentiment_score is not None]
    avg_sentiment = round(np.mean(sentiments), 2) if sentiments else None

    context = {
        'book': book,
        'user_rating': user_rating,
        'is_favorite': is_favorite,
        'avg_rating': avg_display if avg_display is not None else "No rating yet",
        'num_ratings': num_ratings,
        'recommended_books': recommended_books,
        'avg_sentiment': avg_sentiment,
        'books_read': UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count(),
        'favorites_count': UserBook.objects.filter(user=request.user, status='favorite').count(),
    }

    return render(request, 'recommender/book_detail.html', context)

import os
import re
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Book, UserBook
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

REPORTLAB_AVAILABLE = True  # Set True if reportlab installed

@login_required
def read_book_view(request, book_id):
    
    def clean_book_text(text):
        """Clean Gutenberg-style text and normalize spacing, with Contents as a list."""

        # --- 1. Remove Gutenberg header/footer ---
        text = re.sub(r'\*\*\* *START OF THE PROJECT GUTENBERG[^*]*\*\*\*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\*\*\* *END OF THE PROJECT GUTENBERG[^*]*\*\*\*', '', text, flags=re.IGNORECASE)

        # --- 2. Remove transcriber/copyright/legalese lines ---
        text = re.sub(r'project gutenberg.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'transcriber.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'copyright.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'all rights reserved.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'public domain.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(this file was.*?\)', '', text, flags=re.IGNORECASE)

        # --- 3. Normalize quotes, dashes, ellipses ---
        replacements = {
            '“': '"', '”': '"', '‘': "'", '’': "'", '—': '-', '–': '-', '…': '...'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # --- 4. Remove hyphenated line breaks & normalize line endings ---
        text = re.sub(r'-\n', '', text)          # merge hyphenated words
        text = re.sub(r'\r\n', '\n', text)       # Windows → Unix line endings
        text = re.sub(r'\n{3,}', '\n\n', text)   # no more than 2 newlines

        # --- 5. Keep single newlines inside paragraph as space (no breaks) ---
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)

        # --- 6. Collapse extra spaces & strip ---
        text = re.sub(r' +', ' ', text)
        text = text.strip()

        # --- 7. Handle Contents section separately ---
        contents_list = []
        def extract_contents(match):
            nonlocal contents_list
            lines = [line.strip() for line in match.group(1).split('\n') if line.strip()]
            contents_list = lines
            return ''  # Remove contents block from normal paragraphs

        text = re.sub(r'Contents\n(.*?)\n\n', extract_contents, text, flags=re.DOTALL | re.IGNORECASE)

        # --- 8. Split text into paragraphs (only at double newlines) ---
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # --- 9. Determine paragraph type ---
        formatted_paragraphs = []
        for p in paragraphs:
            if p.startswith('"') or p.startswith("'"):
                formatted_paragraphs.append({'type': 'dialogue', 'text': p})
            elif p.startswith('*****'):
                formatted_paragraphs.append({'type': 'separator', 'text': p})
            elif re.match(r'^\d+\.', p):
                formatted_paragraphs.append({'type': 'list', 'text': p})
            else:
                formatted_paragraphs.append({'type': 'normal', 'text': p})

        return formatted_paragraphs, contents_list

    # --- Main Logic ---
    book = get_object_or_404(Book, id=book_id)
    userbook, _ = UserBook.objects.get_or_create(user=request.user, book=book)

    userbook.read_clicked = True
    if userbook.status != 'favorite':
        userbook.status = 'read'
    userbook.save()

    file_path = book.file_path
    if file_path:
        cleaned_path = file_path.replace(".txt", "_clean.txt")
        if os.path.exists(cleaned_path):
            file_path = cleaned_path

    if not file_path or not os.path.exists(file_path):
        return render(request, 'recommender/read_book.html', {
            'book': book,
            'error': 'Book file not found.',
            'pages': [],
            'current_page': 1,
            'total_pages': 0,
            'contents_list': [],
        })

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_text = f.read()

    paragraphs, contents_list = clean_book_text(raw_text)

    # --- Page creation (~500 words per page) ---
    pages = []
    page = []
    word_count = 0
    for para in paragraphs:
        page.append({'type': para['type'], 'text': para['text']})
        word_count += len(para['text'].split())
        if word_count >= 500:
            pages.append(page)
            page = []
            word_count = 0
    if page:
        pages.append(page)

    total_pages = len(pages)
    start_page = userbook.last_page or 1
    try:
        start_page = int(start_page)
    except Exception:
        start_page = 1
    if start_page < 1: start_page = 1
    if start_page > total_pages: start_page = total_pages or 1
  # --- ADD SIDEBAR COUNTS HERE ---
    books_read = UserBook.objects.filter(
        user=request.user, status='read', read_clicked=True
    ).count()

    favorites_count = UserBook.objects.filter(
        user=request.user, status='favorite'
    ).count()
    context = {
        'book': book,
        'pages': pages,
        'current_page': start_page,
        'total_pages': total_pages,
        'userbook': userbook,
        'contents_list': contents_list,
         # Sidebar counts
        'books_read': books_read,
        'favorites_count': favorites_count,

        
    }
    return render(request, 'recommender/read_book.html', context)


# ---------- AJAX endpoints for reader ----------
@login_required
def reader_ajax_view(request, book_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=400)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"success": False, "error": "invalid json"}, status=400)

    book = get_object_or_404(Book, id=book_id)
    userbook, _ = UserBook.objects.get_or_create(user=request.user, book=book)
    action = data.get("action")

    if action == "bookmark":
        page = int(data.get("page", 1))
        userbook.last_page = page
        userbook.read_clicked = True
        userbook.save()
        return JsonResponse({"success": True, "last_page": userbook.last_page})
    elif action == "undo_favorite":
        if userbook.status == 'favorite':
            userbook.status = 'read'
            userbook.save()
        return JsonResponse({"success": True, "is_favorite": False})
    elif action == "favorite":
        userbook.status = 'favorite'
        userbook.save()
        return JsonResponse({"success": True, "is_favorite": True})
    elif action == "history":
        userbook.updated_at = timezone.now()
        userbook.save()
        return JsonResponse({"success": True, "updated_at": userbook.updated_at.isoformat()})
    else:
        return JsonResponse({"success": False, "error": "unknown action"}, status=400)


# ---------- Download as PDF ----------
@login_required
def download_book_pdf(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if not book.file_path or not os.path.exists(book.file_path):
        return HttpResponse("Book file not found", status=404)

    file_path = book.file_path
    cleaned_path = file_path.replace(".txt", "_clean.txt")
    if os.path.exists(cleaned_path):
        file_path = cleaned_path

    # Assume preprocess_book exists to split into pages
    cleaned = preprocess_book(file_path)

    if REPORTLAB_AVAILABLE:
        from io import BytesIO
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        textobj = p.beginText(40, height - 60)
        textobj.setFont("Times-Roman", 11)
        line_height = 14
        for page in cleaned:
            for paragraph in page:
                line = paragraph['text']
                while len(line) > 120:
                    textobj.textLine(line[:120])
                    line = line[120:]
                textobj.textLine(line)
                textobj.textLine("")  # paragraph spacing
                if textobj.getY() < 60:
                    p.drawText(textobj)
                    p.showPage()
                    textobj = p.beginText(40, height - 60)
                    textobj.setFont("Times-Roman", 11)
        p.drawText(textobj)
        p.showPage()
        p.save()
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{book.title}.pdf"'
        return response
    else:
        txt_content = "\n\n".join("\n".join(p['text'] for p in page) for page in cleaned)
        response = HttpResponse(txt_content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{book.title}.txt"'
        return response


# recommender/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from recommender.models import Book, UserBook
from .views_helpers import _get_book_rating_stats
from .collab_filters import user_based_cf, item_based_cf

def _format_book_dict(book):
    """
    Helper to create a dictionary for template rendering.
    Handles avg_rating, cover fallback, can_read, and file_path.
    """
    avg_rating, num_ratings = _get_book_rating_stats(book)
    return {
        'id': book.id,
        'title': book.title,
        'author': book.author or "Unknown",
        'cover_url': book.cover_url or '/static/images/default_cover.jpg',
        'avg_rating': avg_rating if avg_rating is not None else "No rating yet",
        'num_ratings': num_ratings,
        'detail_url': f"/books/{book.id}/detail/",
        'file_path': book.file_path,
        'can_read': bool(book.file_path),
    }

@login_required
def collaborative_recommendations_view(request):
    """
    Collaborative Filtering Recommendations Page
    - For You → user-based CF
    - Because You Liked → item-based CF (last action: read or rated)
    Only books with file_path are shown.
    """

    user_id = request.user.id

    # ----------------------------
    # 1️⃣ USER-BASED CF (For You)
    # ----------------------------
    raw_for_you = user_based_cf(user_id, top_n=10).filter(file_path__isnull=False)
    for_you_books = [_format_book_dict(book) for book in raw_for_you]

    # -----------------------------------
    # 2️⃣ ITEM-BASED CF (Because You Liked)
    # -----------------------------------

    # Last read book
    last_read_ub = UserBook.objects.filter(
        user=request.user,
        status='read',
        read_clicked=True
    ).order_by('-id').first()

    # Last rated book
    last_rated_ub = UserBook.objects.filter(
        user=request.user,
        rating__isnull=False
    ).order_by('-id').first()

    # Pick the most recent action
    reference_ub = None
    if last_read_ub and last_rated_ub:
        reference_ub = last_read_ub if last_read_ub.id > last_rated_ub.id else last_rated_ub
    elif last_read_ub:
        reference_ub = last_read_ub
    elif last_rated_ub:
        reference_ub = last_rated_ub

    because_you_liked_books = []
    because_you_liked_heading = None

    if reference_ub:
        reference_book = reference_ub.book

        if reference_book.file_path:
            because_you_liked_heading = f'Because you liked "{reference_book.title}"'
            raw_item_books = item_based_cf(book_id=reference_book.id, top_n=10)
            raw_item_books = raw_item_books.filter(file_path__isnull=False)

            # Optional: exclude books already read by user
            raw_item_books = raw_item_books.exclude(
                id__in=UserBook.objects.filter(user=request.user).values_list('book_id', flat=True)
            )

            because_you_liked_books = [_format_book_dict(book) for book in raw_item_books]

    # ----------------------------
    # Sidebar counts (same as dashboard)
    # ----------------------------
    books_read = UserBook.objects.filter(
        user=request.user,
        status='read',
        read_clicked=True
    ).count()

    favorites_count = UserBook.objects.filter(
        user=request.user,
        status='favorite'
    ).count()

    context = {
        'for_you_books': for_you_books,
        'because_you_liked_books': because_you_liked_books,
        'because_you_liked_heading': because_you_liked_heading,
        'books_read': books_read,
        'favorites_count': favorites_count,
    }

    return render(request, 'recommender/recommendations.html', context)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, FloatField, Q, Value
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.http import JsonResponse
from recommender.models import Book, UserBook


@login_required
def browse_books_view(request):
    BOOKS_PER_PAGE = 20

    # ── 1. Annotate all books that have readable content ──────────────────
    books_qs = Book.objects.filter(
        file_path__isnull=False
    ).exclude(file_path__exact='').annotate(
        avg_rating_ann=Coalesce(
            Avg('userbook__rating', output_field=FloatField()), Value(0.0)
        ),
        num_ratings=Count('userbook__id'),      # count only rating rows, not dupes
        num_reads=Count('userbook', filter=Q(userbook__read_clicked=True)),  
    )

    # ── 2. Search filter ──────────────────────────────────────────────────
    query = request.GET.get('q', '').strip()
    if query:
        books_qs = books_qs.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(description__icontains=query)
        )

    # ── 3. Bayesian weighted rating ───────────────────────────────────────
    m          = 5
    global_avg = UserBook.objects.aggregate(avg=Avg('rating'))['avg'] or 0

    weighted = []
    for b in books_qs:
        v  = b.num_ratings
        R  = b.avg_rating_ann
        WR = (v / (v + m)) * R + (m / (v + m)) * global_avg if (v + m) > 0 else R
        weighted.append((WR, b))

    # Default server-side order: highest weighted rating first
    weighted.sort(key=lambda x: x[0], reverse=True)

    # ── 4. De-duplicate by title (keep highest-rated copy) ────────────────
    seen_titles  = set()
    unique_books = []
    for WR, b in weighted:
        if b.title not in seen_titles:
            seen_titles.add(b.title)
            unique_books.append((WR, b))

    # Max ratings for popularity bar
    max_ratings = max((b.num_ratings for _, b in unique_books), default=1) or 1

    # ── 5. Paginate ───────────────────────────────────────────────────────
    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        page_number = 1

    paginator = Paginator(unique_books, BOOKS_PER_PAGE)
    page_obj  = paginator.get_page(page_number)

    # ── 6. Build book dicts ───────────────────────────────────────────────
    def build_dict(b, WR):
        display_rating = round(b.avg_rating_ann / 2, 1) if b.num_ratings > 0 else None
        cover_image_url = None
        if hasattr(b, 'cover_image') and b.cover_image:
            try:
                cover_image_url = b.cover_image.url
            except Exception:
                pass
        return {
            'id':             b.id,
            'title':          b.title or '',
            'author':         b.author or 'Unknown',
            'description':    (b.description or '')[:400],
            'cover_url':      cover_image_url or b.cover_url or '/static/images/default_cover.jpg',
            'file_path':      bool(b.file_path),    # just a boolean for the template
            'source':         b.source or '',
            'avg_rating':     display_rating if display_rating is not None else 'No rating yet',
            'num_reads':      b.num_reads,  # ← NEW
            'avg_rating_raw': round(b.avg_rating_ann, 2),
            'num_ratings':    b.num_ratings,
            'popularity_pct': round((b.num_ratings / max_ratings) * 100),
            'can_read':       True,
            'detail_url':     f'/books/{b.id}/detail/',
            'read_url':       f'/books/{b.id}/read/',
        }

    books_data = [build_dict(b, WR) for WR, b in page_obj.object_list]

    # ── 7. Sidebar counts ─────────────────────────────────────────────────
    books_read      = UserBook.objects.filter(user=request.user, status='read', read_clicked=True).count()
    favorites_count = UserBook.objects.filter(user=request.user, status='favorite').count()

    # ── 8. AJAX response (infinite scroll) ───────────────────────────────
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'books':    books_data,
            'has_next': page_obj.has_next(),
            'page':     page_number,
        })

    # ── 9. Initial HTML render ────────────────────────────────────────────
    context = {
        'books':            books_data,
        'books_read':       books_read,
        'favorites_count':  favorites_count,
        'query':            query,
        'has_next':         page_obj.has_next(),
        'next_page':        page_number + 1,      # always next integer; JS checks has_next first
    }
    return render(request, 'recommender/browse_books.html', context)