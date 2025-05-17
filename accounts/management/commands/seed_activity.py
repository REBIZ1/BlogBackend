import random
import datetime
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone
from faker import Faker

from blog.models import Post, Like, ReadingTime, Follow, Comment
from django.contrib.auth import get_user_model

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = "Seed random likes, views, follows and comments for existing users and posts"

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-likes', type=int, default=5,
            help='Минимальное число лайков на пользователя'
        )
        parser.add_argument(
            '--max-likes', type=int, default=20,
            help='Максимальное число лайков на пользователя'
        )
        parser.add_argument(
            '--min-views', type=int, default=20,
            help='Минимальное число просмотров на пользователя'
        )
        parser.add_argument(
            '--max-views', type=int, default=50,
            help='Максимальное число просмотров на пользователя'
        )

    def handle(self, *args, **options):
        users = list(User.objects.filter(is_active=True))
        posts = list(Post.objects.all())
        total_likes = total_views = total_reading = total_follows = total_comments = 0

        for user in users:
            # Лайки
            n_likes = random.randint(options['min_likes'], options['max_likes'])
            liked_posts = random.sample(posts, k=min(n_likes, len(posts)))
            for p in liked_posts:
                like, created = Like.objects.get_or_create(user=user, post=p)
                if created:
                    total_likes += 1

            # Просмотры и ReadingTime
            n_views = random.randint(options['min_views'], options['max_views'])
            viewed_posts = random.sample(posts, k=min(n_views, len(posts)))
            for p in viewed_posts:
                Post.objects.filter(pk=p.pk).update(views=F('views') + 1)
                total_views += 1

                seconds = random.randint(8, 300)
                # используем datetime.timezone.utc
                timestamp = fake.date_time_between(
                    start_date=p.created_at, end_date=timezone.now(),
                    tzinfo=datetime.timezone.utc
                )
                ReadingTime.objects.create(
                    user=user, post=p,
                    seconds_spent=seconds,
                    timestamp=timestamp
                )
                total_reading += 1

            # Подписки (Follow): каждый пользователь подписывается на 5–15 других
            others = [u for u in users if u != user]
            to_follow = random.sample(others, k=min(len(others), random.randint(5,15)))
            for author in to_follow:
                follow, created = Follow.objects.get_or_create(user=user, author=author)
                if created:
                    total_follows += 1

            # Комментарии: 0–5 на случайные посты
            for _ in range(random.randint(0,5)):
                p = random.choice(posts)
                Comment.objects.create(
                    post=p,
                    author=user,
                    content=fake.sentence(),
                    created_at=fake.date_time_between(
                        start_date=p.created_at, end_date=timezone.now(),
                        tzinfo=datetime.timezone.utc
                    )
                )
                total_comments += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {total_likes} likes, "
            f"{total_views} views, "
            f"{total_reading} reading records, "
            f"{total_follows} follows, "
            f"{total_comments} comments."
        ))
