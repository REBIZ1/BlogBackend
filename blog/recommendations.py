# blog/recommendations.py

import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import Post, ReadingTime
from .utils import get_tag_index_map

LIKE_WEIGHT    = 1.0
READ_WEIGHT    = 0.5
READ_THRESHOLD = 10

# для MMR
MMR_LAMBDA = 0.7

def strip_html(html: str) -> str:
    """Простейшее удаление HTML-тегов."""
    return re.sub(r'<[^>]+>', ' ', html or '')

def build_user_profile(user):
    tag_map = get_tag_index_map()
    dim_tags = len(tag_map)

    # 1) Лайки
    liked = list(Post.objects.filter(likes__user=user)
                           .prefetch_related('tags'))
    # 2) Чтения ≥ READ_THRESHOLD (исключая лайкнутые)
    read_ids = (ReadingTime.objects
                .filter(user=user, seconds_spent__gte=READ_THRESHOLD)
                .values_list('post_id', flat=True)
                .distinct())
    read = list(Post.objects.filter(id__in=read_ids)
                             .exclude(likes__user=user)
                             .prefetch_related('tags'))

    vectors_tags = []
    weights = []
    for p in liked:
        vectors_tags.append(p.tag_vector(tag_map))
        weights.append(LIKE_WEIGHT)
    for p in read:
        vectors_tags.append(p.tag_vector(tag_map))
        weights.append(READ_WEIGHT)

    if not vectors_tags:
        # Нет сигналов
        return None, None, tag_map

    # Строим теговый профиль
    arr_tags = np.array(vectors_tags)                 # (N, dim_tags)
    wts = np.array(weights).reshape(-1,1)             # (N,1)
    profile_tags = (arr_tags * wts).sum(axis=0) / wts.sum()  # (dim_tags,)

    # Строим TF-IDF по текстам
    # Взять тексты только из liked+read, чтобы профиль не шумел
    texts = []
    for p in liked + read:
        texts.append(p.title + ' ' + strip_html(p.content))
    vectorizer = TfidfVectorizer(max_features=1000)
    tfidf_mat = vectorizer.fit_transform(texts)  # (N, dim_tfidf)
    # взвешенное суммирование по тем же весам
    profile_tfidf = (tfidf_mat.multiply(wts).sum(axis=0) / wts.sum()).A1
    # нормировка профиля
    if np.linalg.norm(profile_tfidf) > 0:
        profile_tfidf = profile_tfidf / np.linalg.norm(profile_tfidf)

    return profile_tags, profile_tfidf, tag_map, vectorizer

def mmr(doc_vectors, user_vector, lambda_param, top_n):
    """
    Maximal Marginal Relevance:
    doc_vectors: np.array (M, D)
    user_vector: np.array (D,)
    """
    selected = []
    unselected = set(range(len(doc_vectors)))
    # первый: наивысшее сходство с user_vector
    sims = cosine_similarity(doc_vectors, user_vector.reshape(1,-1)).reshape(-1)
    first = int(np.argmax(sims))
    selected.append(first)
    unselected.remove(first)

    while len(selected) < top_n and unselected:
        mmr_scores = {}
        for idx in unselected:
            sim_to_user = sims[idx]
            # максимальная близость к уже выбранным
            sim_to_sel = max(cosine_similarity(
                doc_vectors[idx].reshape(1,-1),
                doc_vectors[np.array(selected)]
            ).reshape(-1))
            mmr_scores[idx] = lambda_param * sim_to_user - (1-lambda_param) * sim_to_sel
        next_idx = max(mmr_scores, key=mmr_scores.get)
        selected.append(next_idx)
        unselected.remove(next_idx)
    return selected

def recommend_by_content(user, top_n=10):
    # 1) Построить профиль
    result = build_user_profile(user)
    if result[0] is None:
        return []  # нет сигналов

    profile_tags, profile_tfidf, tag_map, vectorizer = result

    # 2) Векторы всех постов
    posts = list(Post.objects.all().prefetch_related('tags'))

    # теговые
    tag_vecs = np.array([p.tag_vector(tag_map) for p in posts])  # (M, dim_tags)
    # tfidf
    texts_all = [p.title + ' ' + strip_html(p.content) for p in posts]
    tfidf_all = vectorizer.transform(texts_all).toarray()         # (M, dim_tfidf)

    # нормируем tag_vecs
    norms = np.linalg.norm(tag_vecs, axis=1, keepdims=True)
    norms[norms==0] = 1
    tag_vecs = tag_vecs / norms

    # объединяем фичи
    post_vecs = np.hstack([tag_vecs, tfidf_all])                  # (M, D)

    # объединяем профили
    # нормируем profile_tags
    if np.linalg.norm(profile_tags) > 0:
        profile_tags = profile_tags / np.linalg.norm(profile_tags)
    user_vec = np.concatenate([profile_tags, profile_tfidf])      # (D,)

    # 3) считаем MMR
    idxs = mmr(post_vecs, user_vec, MMR_LAMBDA, top_n)

    # 4) возвращаем
    return [posts[i] for i in idxs]
