from django.contrib import admin

from .models import Quiz, Question, Session, Participant, Answer


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at')
    search_fields = ('title',)
    inlines = [QuestionInline]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'room_code', 'host', 'is_active', 'has_started',
                    'current_question_index', 'started_at')
    list_filter = ('is_active', 'has_started')
    readonly_fields = ('room_code',)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'score', 'joined_at')
    list_filter = ('session',)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('participant', 'question', 'selected_option', 'is_correct', 'points', 'answered_at')
    list_filter = ('is_correct',)
