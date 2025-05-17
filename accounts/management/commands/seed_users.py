# accounts/management/commands/seed_users.py

import random
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Seed the database with fake users (Russian names)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--number',
            type=int,
            default=100,
            help='How many users to create (default: 100)'
        )

    def handle(self, *args, **options):
        count = options['number']
        fake = Faker('ru_RU')
        created = 0

        for _ in range(count):
            first = fake.first_name()
            last = fake.last_name()
            # Генерим латинский username через Faker
            username = fake.user_name()
            # Если вдруг уже есть такой, добавляем случайный суффикс

            while User.objects.filter(username=username).exists():
                username = f"{fake.user_name()}{fake.random_number(digits=2)}"

            email = f"{username}@example.com"
            password = 'test1234'

            user = User.objects.create_user(
                username=username,
                first_name=first,
                last_name=last,
                email=email,
                password=password
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully created {created} users."
        ))
