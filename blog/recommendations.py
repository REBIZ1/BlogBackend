import re
import numpy as np
import scipy.sparse as sp
from implicit.als import AlternatingLeastSquares
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import Post, ReadingTime, Like, Comment, Follow
from .utils import get_tag_index_map
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

# Контентная фильтрация
LIKE_WEIGHT    = 1.0
SUBSCRIBE_WEIGHT  = 0.3
READ_WEIGHT    = 0.5
COMMENT_WEIGHT   = 0.8
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

# Коллаборативная рекомендация
# кеш для CF-модели
_cf_model        = None
_cf_mat          = None    # users×posts
_cf_users        = None
_cf_posts        = None
_cf_user_index   = None
_cf_post_index   = None

def build_interaction_matrix():
    User = get_user_model()

    likes_qs    = Like.objects.select_related('user','post').all()
    reads_qs    = ReadingTime.objects.select_related('user','post') \
                     .filter(seconds_spent__gte=READ_THRESHOLD)
    comments_qs = Comment.objects.select_related('author','post').all()
    follows_qs  = Follow.objects.select_related('user','author').all()

    # кто и по каким постам взаимодействовал
    user_ids = set(likes_qs.values_list('user_id', flat=True)) \
             | set(reads_qs.values_list('user_id', flat=True)) \
             | set(comments_qs.values_list('author_id', flat=True)) \
             | set(follows_qs.values_list('user_id', flat=True))

    posts = list(Post.objects.all())
    users = list(User.objects.filter(id__in=user_ids))

    if not users or not posts:
        return sp.csr_matrix((0, 0)), users, posts, {}, {}

    user_index = {u.id: i for i, u in enumerate(users)}
    post_index = {p.id: j for j, p in enumerate(posts)}

    rows, cols, data = [], [], []

    for like in likes_qs:
        u, p = like.user_id, like.post_id
        if u in user_index and p in post_index:
            rows.append(user_index[u])
            cols.append(post_index[p])
            data.append(LIKE_WEIGHT)

    for rt in reads_qs:
        u, p = rt.user_id, rt.post_id
        if u in user_index and p in post_index:
            rows.append(user_index[u])
            cols.append(post_index[p])
            data.append(READ_WEIGHT)

    for c in comments_qs:
        u, p = c.author_id, c.post_id
        if u in user_index and p in post_index:
            rows.append(user_index[u])
            cols.append(post_index[p])
            data.append(COMMENT_WEIGHT)

    # подписка даёт сигнал ко всем постам автора
    posts_by_author = {}
    for p in posts:
        posts_by_author.setdefault(p.author_id, []).append(post_index[p.id])
    for f in follows_qs:
        u, a = f.user_id, f.author_id
        if u in user_index and a in posts_by_author:
            for pid in posts_by_author[a]:
                rows.append(user_index[u])
                cols.append(pid)
                data.append(SUBSCRIBE_WEIGHT)

    mat = sp.coo_matrix(
        (np.array(data, dtype=np.float32), (rows, cols)),
        shape=(len(users), len(posts))
    )
    return mat.tocsr(), users, posts, user_index, post_index

def train_cf_model(factors=50, regularization=0.01, iterations=20, force=False):
    """
    Тренирует ALS раз и кеширует результат.
    Если force=True — тренирует заново даже если _cf_model уже есть.
    """
    global _cf_model, _cf_mat, _cf_users, _cf_posts, _cf_user_index, _cf_post_index

    if _cf_model is not None and not force:
        return

    mat, users, posts, uidx, pidx = build_interaction_matrix()
    if mat.shape[0] == 0 or mat.shape[1] == 0:
        return

    item_users = mat.T.tocsr()
    model = AlternatingLeastSquares(
        factors        = factors,
        regularization = regularization,
        iterations     = iterations
    )
    model.fit(item_users)

    model.user_items = mat
    _cf_model        = model
    _cf_mat          = mat
    _cf_users        = users
    _cf_posts        = posts
    _cf_user_index   = uidx
    _cf_post_index   = pidx

def recommend_by_cf(user, top_n=10):
    # перед выдачей убеждаемся, что модель свежая
    train_cf_model()

    if _cf_model is None or user.id not in _cf_user_index:
        return []

    uidx     = _cf_user_index[user.id]
    user_row = _cf_mat[uidx]
    ids, scores = _cf_model.recommend(0, user_row, N=top_n, filter_already_liked_items=True)

    res = []
    for idx, sc in zip(ids, scores):
        if 0 <= idx < len(_cf_posts):
            p = _cf_posts[idx]
            p.cf_score = float(sc)
            res.append(p)
    return res

# ------------- Django-сигналы --------------

@receiver([post_save, post_delete], sender=Like)
@receiver([post_save, post_delete], sender=ReadingTime)
@receiver([post_save, post_delete], sender=Comment)
@receiver([post_save, post_delete], sender=Follow)
def _on_signal_update_cf(sender, **kwargs):
    # При любом изменении сигналов — перетренировать модель
    train_cf_model(force=True)

# === ГИБРИДНЫЕ РЕКОМЕНДАЦИИ (CONTENT + CF) ===

def recommend_hybrid(user, top_n=20, alpha=0.6):
    """
    Гибридная рекомендация с динамическим чередованием:
    в итоговых top_n статей доля content ≈ alpha, доля CF ≈ 1-alpha.
    """
    # 1) Получим оба списка и их нормализованные скоринги
    total = Post.objects.count()
    content_recs = recommend_by_content(user, top_n=total)
    cf_recs      = recommend_by_cf(user,      top_n=total)

    c_scores = {p.id: getattr(p, 'content_score', 0.0) for p in content_recs}
    f_scores = {p.id: getattr(p, 'cf_score',      0.0) for p in cf_recs}

    def normalize(d):
        if not d: return {}
        vals = np.array(list(d.values()), float)
        mn, mx = vals.min(), vals.max()
        if mx>mn:
            return {k:(v-mn)/(mx-mn) for k,v in d.items()}
        return {k:1.0 for k in d}

    c_norm = normalize(c_scores)
    f_norm = normalize(f_scores)

    # 2) Отсортируем подпулы
    content_queue = [pid for pid,_ in sorted(c_norm.items(), key=lambda x: x[1], reverse=True)]
    cf_queue      = [pid for pid,_ in sorted(f_norm.items(), key=lambda x: x[1], reverse=True)]

    # 3) Динамическое чередование в соответствии с alpha
    result_ids = []
    content_picked = 0
    cf_picked = 0

    while len(result_ids) < top_n and (content_queue or cf_queue):
        total_picked = content_picked + cf_picked
        # текущая доля контента в выдаче
        current_alpha = content_picked / total_picked if total_picked > 0 else 0

        # решаем, из какой очереди брать следующий элемент
        take_content = False
        if current_alpha < alpha and content_queue:
            take_content = True
        elif not cf_queue:
            take_content = True

        if take_content:
            pid = content_queue.pop(0)
            content_picked += 1
        else:
            pid = cf_queue.pop(0)
            cf_picked += 1

        if pid not in result_ids:
            result_ids.append(pid)

    # 4) Подтянем объекты и проставим hybrid_score для отладки
    hybrid_scores = {}
    for pid in result_ids:
        cs = c_norm.get(pid, 0.0)
        fs = f_norm.get(pid, 0.0)
        hybrid_scores[pid] = alpha * cs + (1 - alpha) * fs

    posts_map = Post.objects.in_bulk(result_ids)
    result = []
    for pid in result_ids:
        post = posts_map.get(pid)
        if post:
            post.hybrid_score = float(hybrid_scores[pid])
            result.append(post)

    return result