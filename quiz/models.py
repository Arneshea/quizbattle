import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'quizzes'

    def __str__(self):
        return self.title


class Question(models.Model):
    OPTION_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    option_d = models.CharField(max_length=200)
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)
    time_limit_seconds = models.PositiveIntegerField(default=20)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.text[:50]


def generate_room_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if not Session.objects.filter(room_code=code).exists():
            return code


class Session(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='sessions')
    room_code = models.CharField(max_length=6, unique=True, default=generate_room_code)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_sessions')
    is_active = models.BooleanField(default=True)
    has_started = models.BooleanField(default=False)
    current_question_index = models.PositiveIntegerField(default=0)
    current_question_started_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.quiz.title} ({self.room_code})"

    def questions_list(self):
        return list(self.quiz.questions.all())

    @property
    def is_finished(self):
        return self.has_started and self.current_question_index >= self.quiz.questions.count()

    def current_question(self):
        qs = self.questions_list()
        if self.current_question_index < len(qs):
            return qs[self.current_question_index]
        return None

    def seconds_remaining(self):
        """Time left on the current question, computed on the SERVER clock
        (so phones with wrong clocks still show the right countdown)."""
        q = self.current_question()
        if not q or not self.current_question_started_at:
            return 0
        elapsed = (timezone.now() - self.current_question_started_at).total_seconds()
        return max(0, int(round(q.time_limit_seconds - elapsed)))


class Participant(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=100)
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'name')
        ordering = ['-score', 'joined_at']

    def __str__(self):
        return f"{self.name} - {self.score} pts"


class Answer(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField(default=False)
    points = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('participant', 'question')

    def __str__(self):
        return f"{self.participant.name} -> {self.selected_option}"
