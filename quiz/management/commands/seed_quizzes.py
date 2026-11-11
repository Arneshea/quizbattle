from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quiz.models import Quiz, Question
from quiz.sample_data import SAMPLE_QUIZZES


class Command(BaseCommand):
    help = ('Adds sample quizzes to a host account. Safe to run more than once '
            '(quizzes that already exist are skipped).')

    def add_arguments(self, parser):
        parser.add_argument('--user', help='Username that should own the quizzes. '
                            'Default: the first superuser, or a "host" account if none exists.')
        parser.add_argument('--reset', action='store_true',
                            help='Delete and recreate the sample quizzes for that user.')

    def handle(self, *args, **options):
        user = self._get_user(options['user'])
        created, skipped = 0, 0

        with transaction.atomic():
            for data in SAMPLE_QUIZZES:
                existing = Quiz.objects.filter(title=data['title'], created_by=user)
                if existing.exists():
                    if options['reset']:
                        existing.delete()
                    else:
                        skipped += 1
                        self.stdout.write(f"  skipped (already exists): {data['title']}")
                        continue

                quiz = Quiz.objects.create(title=data['title'], description=data['description'],
                                           created_by=user)
                Question.objects.bulk_create([
                    Question(quiz=quiz, text=t, option_a=a, option_b=b, option_c=c, option_d=d,
                             correct_option=correct, time_limit_seconds=data['time_limit'])
                    for t, a, b, c, d, correct in data['questions']
                ])
                created += 1
                self.stdout.write(f"  added: {data['title']} ({len(data['questions'])} questions)")

        self.stdout.write(self.style.SUCCESS(
            f"Done for user '{user.username}': {created} added, {skipped} skipped."))

    def _get_user(self, username):
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' does not exist. "
                                   f"Create it first (createsuperuser or the signup page).")
        user = User.objects.filter(is_superuser=True).order_by('id').first()
        if user:
            return user
        user, made = User.objects.get_or_create(username='host')
        if made:
            user.set_password('host12345')
            user.save()
            self.stdout.write('No superuser found, created demo account host / host12345')
        return user