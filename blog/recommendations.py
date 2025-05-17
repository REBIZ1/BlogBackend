# blog/recommendations.py
import numpy as np
from .models import Post
from .utils import get_tag_index_map
from sklearn.metrics.pairwise import cosine_similarity

def build_user_profile(user):
    tag_map = get_tag_index_map()
    # допустим, берем все посты, которые user лайкнул
    liked_posts = Post.objects.filter(likes__user=user)
    if not liked_posts:
        return np.zeros(len(tag_map))

    vecs = [p.tag_vector(tag_map) for p in liked_posts]
    profile = np.mean(vecs, axis=0)
    return profile, tag_map

def recommend_by_content(user, top_n=10):
    profile, tag_map = build_user_profile(user)
    # Получаем все посты и их векторы
    posts = list(Post.objects.all().prefetch_related('tags'))
    post_vecs = np.array([p.tag_vector(tag_map) for p in posts])

    # Считаем косинусное сходство
    sims = cosine_similarity([profile], post_vecs)[0]
    # argsort возвращает numpy.int64 — конвертируем в обычный int
    idxs = sims.argsort()[::-1][:top_n]
    # Собираем результат, явное приведение к int
    recommended = [posts[int(i)] for i in idxs]
    return recommended