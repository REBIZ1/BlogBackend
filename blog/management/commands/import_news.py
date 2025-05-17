# blog/management/commands/import_news.py
from django.utils.text import slugify
import hashlib
import random
import requests

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import transaction
from newspaper import Article   # <-- импортируем newspaper
from newsapi import NewsApiClient
import spacy

from django.contrib.auth import get_user_model
from blog.models import Post, Tag

User = get_user_model()

# spaCy для русского
nlp = spacy.load("ru_core_news_sm")


class Command(BaseCommand):
    help = "Import Russian tech articles via everything(q='технология', language='ru')"

    def add_arguments(self, parser):
        parser.add_argument(
            '--api_key', required=True,
            help="Your NewsAPI.org API key"
        )
        parser.add_argument(
            '--page_size', type=int, default=100,
            help="How many articles per request (max 100)"
        )

    def handle(self, *args, **options):
        api_key   = options['api_key']
        page_size = options['page_size']

        # Список реальных пользователей (кроме import_bot)
        real_users = list(
            User.objects.exclude(username='import_bot').filter(is_active=True)
        )
        if not real_users:
            self.stdout.write(self.style.ERROR(
                "Нет реальных пользователей! Сначала создайте их командой seed_users."
            ))
            return

        newsapi = NewsApiClient(api_key=api_key)

        resp = newsapi.get_everything(
            q="it технология OR itтехнологии",
            language="ru",
            page_size=page_size,
            sort_by="publishedAt"
        )
        articles = resp.get('articles') or []
        self.stdout.write(f"NewsAPI everything вернул {len(articles)} статей.")

        if not articles:
            self.stdout.write(self.style.WARNING(
                "Список статей пуст — проверьте API-ключ и лимиты."
            ))
            return

        created = 0
        with transaction.atomic():
            for art in articles:
                url = art.get('url')
                if not url:
                    continue

                slug = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
                if Post.objects.filter(content__icontains=slug).exists():
                    continue

                title     = art.get('title') or 'Без заголовка'
                desc      = art.get('description') or ''
                content = ''
                url = art.get('url')
                if url:
                    try:
                        news = Article(url, language='ru')
                        news.download()
                        news.parse()
                        content = news.text
                    except Exception:
                        content = art.get('content') or ''
                else:
                    content = art.get('content') or ''

                published = art.get('publishedAt')
                author    = random.choice(real_users)

                post = Post(
                    title=title,
                    content=f"{desc}\n\n{content}\n\nImported ID: {slug}",
                    author=author,
                    created_at=published or timezone.now(),
                    updated_at=published or timezone.now()
                )

                # Скачиваем обложку
                image_url = art.get('urlToImage')
                if image_url:
                    try:
                        r = requests.get(image_url, timeout=5)
                        if r.status_code == 200 and 'image' in r.headers.get('content-type',''):
                            name = image_url.split('/')[-1].split('?')[0] or f"{slug}.jpg"
                            post.cover.save(name, ContentFile(r.content), save=False)
                    except Exception:
                        pass

                post.save()

                # spaCy: только именованные сущности
                doc = nlp(f"{title}\n\n{desc}\n\n{content}")
                key_phrases = set(
                    ent.text.strip().lower()
                    for ent in doc.ents
                    if ent.label_ in ("PER", "ORG", "LOC", "MISC")
                    or ent.label_ in ("PERSON","ORG","GPE","NORP","EVENT","WORK_OF_ART")
                )

                # Привязываем теги
                tag_objs = []
                for phrase in key_phrases:
                    clean_name = phrase if len(phrase) <= 50 else phrase[:50]
                    clean_slug = slugify(clean_name)
                    if not clean_slug:
                        clean_slug = hashlib.md5(clean_name.encode('utf-8')).hexdigest()[:12]

                    tg, created = Tag.objects.get_or_create(
                        slug=clean_slug,
                        defaults={'name': clean_name}
                    )
                    tag_objs.append(tg)
                    post.tags.set(tag_objs)



                created += 1

        self.stdout.write(self.style.SUCCESS(f"Импортировано {created} новых статей."))
