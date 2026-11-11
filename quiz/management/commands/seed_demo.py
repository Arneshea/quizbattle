from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from quiz.models import Quiz, Question

QUESTIONS = [
    ("What is the correct file extension for Python files?", ".pyt", ".py", ".pt", ".python", "B"),
    ("Which keyword is used to define a function in Python?", "function", "def", "func", "define", "B"),
    ("What data type is the result of 10 / 3 in Python?", "int", "float", "str", "complex", "B"),
    ("Which of these is used to create a list in Python?", "{}", "()", "[]", "<>", "C"),
    ("What does the len() function do?", "Converts to lowercase", "Returns length of an object",
     "Deletes a variable", "Rounds a number", "B"),
]


class Command(BaseCommand):
    help = 'Creates a demo host account and a sample Python quiz.'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(username='host')
        if created:
            user.set_password('host12345')
            user.save()
        quiz, qcreated = Quiz.objects.get_or_create(
            title='Python Basics', created_by=user,
            defaults={'description': 'Five warm-up questions'})
        if qcreated:
            for text, a, b, c, d, correct in QUESTIONS:
                Question.objects.create(quiz=quiz, text=text, option_a=a, option_b=b,
                                        option_c=c, option_d=d, correct_option=correct)
        self.stdout.write(self.style.SUCCESS(
            'Demo ready. Login: host / host12345  (quiz: Python Basics)'))
