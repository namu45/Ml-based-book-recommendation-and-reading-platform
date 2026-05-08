# recommender/collab_filters.py
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from recommender.models import UserBook, Book

# ----------------------------
# User-Item Matrix
# ----------------------------
def get_user_item_matrix(limit_books=5000):
    """Return sparse user-item matrix (users x books)"""
    qs = UserBook.objects.exclude(rating__isnull=True).values('user_id', 'book_id', 'rating')
    df = pd.DataFrame(list(qs))
    if df.empty:
        return pd.DataFrame()
    if limit_books:
        df = df[df['book_id'].isin(df['book_id'].unique()[:limit_books])]
    matrix = df.pivot(index='user_id', columns='book_id', values='rating').fillna(0)
    return matrix

# ----------------------------
# User-Based CF
# ----------------------------
def user_based_cf(user_id, top_n=5, top_k_users=20):
    """Return top-N book recommendations for a user using user-based CF"""
    user_item_matrix = get_user_item_matrix()
    if user_id not in user_item_matrix.index or user_item_matrix.empty:
        return Book.objects.none()

    # Sparse matrix for memory efficiency
    user_matrix = csr_matrix(user_item_matrix.values)
    user_sim = cosine_similarity(user_matrix, dense_output=False)
    user_index = user_item_matrix.index.get_loc(user_id)
    sim_scores = pd.Series(user_sim[user_index].toarray().flatten(), index=user_item_matrix.index)

    # Take top-k most similar users
    sim_scores = sim_scores[sim_scores > 0].sort_values(ascending=False).head(top_k_users)

    # Already rated/read books
    rated_books = UserBook.objects.filter(user=user_id).values_list('book_id', flat=True)

    # Weighted score for books
    scored_books = pd.Series(dtype=float)
    for sim_user_id, sim_score in sim_scores.items():
        user_books = user_item_matrix.loc[sim_user_id]
        # Only consider books the current user hasn't rated/read
        user_books = user_books[~user_books.index.isin(rated_books)]
        scored_books = scored_books.add(user_books * sim_score, fill_value=0)

    top_books = scored_books.sort_values(ascending=False).head(top_n).index.tolist()
    return Book.objects.filter(id__in=top_books)

# ----------------------------
# Item-Based CF
# ----------------------------
def item_based_cf(book_id, top_n=5, top_k_items=20, user_id=None):
    """Return top-N similar books using item-based CF (exclude already rated/read books if user_id provided)"""
    user_item_matrix = get_user_item_matrix()
    if book_id not in user_item_matrix.columns or user_item_matrix.empty:
        return Book.objects.none()

    # Sparse matrix
    item_matrix = csr_matrix(user_item_matrix.T.values)
    item_sim = cosine_similarity(item_matrix, dense_output=False)
    book_index = list(user_item_matrix.columns).index(book_id)
    sim_scores = pd.Series(item_sim[book_index].toarray().flatten(), index=user_item_matrix.columns)

    # Take top-k similar items
    sim_scores = sim_scores[sim_scores > 0].sort_values(ascending=False).head(top_k_items)

    # Exclude the current book
    top_books = sim_scores.index[sim_scores.index != book_id]

    # Exclude already rated/read books if user_id given
    if user_id:
        rated_books = UserBook.objects.filter(user=user_id).values_list('book_id', flat=True)
        top_books = [b for b in top_books if b not in rated_books]

    top_books = list(top_books[:top_n])
    return Book.objects.filter(id__in=top_books)