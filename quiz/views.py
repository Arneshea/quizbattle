import csv
import io

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from .forms import QuizForm, QuestionFormSet, SignUpForm
from .models import Quiz, Session, Participant, Answer, Question

BASE_POINTS = 10
MAX_SPEED_BONUS = 5
GRACE_SECONDS = 1.5  # forgive network latency when checking the time limit


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Account created. Welcome!')
        return redirect('dashboard')
    return render(request, 'registration/signup.html', {'form': form})


# --------------------------------------------------------------------------
# Participant side
# --------------------------------------------------------------------------
def join_session(request):
    """Landing page: enter room code + name."""
    error = None
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').strip().upper()
        name = request.POST.get('name', '').strip()[:100]

        session = Session.objects.filter(room_code=room_code, is_active=True).first()
        if not session:
            error = 'Invalid or inactive room code.'
        elif not name:
            error = 'Please enter your name.'
        else:
            existing = Participant.objects.filter(session=session, name__iexact=name).first()
            if existing and request.session.get('participant_id') != existing.id:
                error = 'That name is already taken in this room. Pick another.'
            else:
                participant = existing or Participant.objects.create(session=session, name=name)
                request.session['participant_id'] = participant.id
                return redirect('play', session_id=session.id)

    return render(request, 'quiz/join.html', {'error': error})


def _get_participant(request, session):
    pid = request.session.get('participant_id')
    if not pid:
        return None
    return Participant.objects.filter(id=pid, session=session).first()


def play(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    participant = _get_participant(request, session)
    if not participant:
        return redirect('join_session')

    if not session.has_started:
        return render(request, 'quiz/waiting.html', {'session': session, 'participant': participant})

    if session.is_finished:
        return render(request, 'quiz/finished.html', {
            'session': session,
            'participant': participant,
            'leaderboard': session.participants.all()[:10],
            'rank': list(session.participants.values_list('id', flat=True)).index(participant.id) + 1,
        })

    question = session.current_question()
    answer = Answer.objects.filter(participant=participant, question=question).first()

    return render(request, 'quiz/play.html', {
        'session': session,
        'participant': participant,
        'question': question,
        'answer': answer,
        'remaining': session.seconds_remaining(),
        'question_number': session.current_question_index + 1,
        'total_questions': session.quiz.questions.count(),
    })


@require_POST
def submit_answer(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    participant = _get_participant(request, session)
    if not participant:
        return JsonResponse({'error': 'You have not joined this session.'}, status=403)
    if not session.has_started or session.is_finished:
        return JsonResponse({'error': 'Quiz is not running.'}, status=400)

    question = session.current_question()
    # the question the phone thinks it is answering must be the live one
    if str(question.id) != request.POST.get('question_id'):
        return JsonResponse({'error': 'That question is already over.'}, status=400)

    selected = request.POST.get('selected_option', '').upper()
    if selected not in ('A', 'B', 'C', 'D'):
        return JsonResponse({'error': 'Invalid option.'}, status=400)

    elapsed = (timezone.now() - session.current_question_started_at).total_seconds()
    if elapsed > question.time_limit_seconds + GRACE_SECONDS:
        return JsonResponse({'error': "Time's up!"}, status=400)

    with transaction.atomic():
        if Answer.objects.filter(participant=participant, question=question).exists():
            return JsonResponse({'error': 'Already answered.'}, status=400)

        is_correct = selected == question.correct_option
        points = 0
        if is_correct:
            left = max(0.0, question.time_limit_seconds - elapsed)
            points = BASE_POINTS + int(MAX_SPEED_BONUS * left / question.time_limit_seconds)
        Answer.objects.create(participant=participant, question=question,
                              selected_option=selected, is_correct=is_correct, points=points)
        if points:
            participant.score += points
            participant.save(update_fields=['score'])

    return JsonResponse({
        'correct': is_correct,
        'points': points,
        'correct_option': question.correct_option,
        'new_score': participant.score,
    })


@require_GET
def session_status(request, session_id):
    """Polled by participant and host pages every couple of seconds."""
    session = get_object_or_404(Session, id=session_id)
    question = session.current_question()
    answered = 0
    if question:
        answered = Answer.objects.filter(participant__session=session, question=question).count()

    return JsonResponse({
        'has_started': session.has_started,
        'finished': session.is_finished,
        'current_question_index': session.current_question_index,
        'total_questions': session.quiz.questions.count(),
        'remaining': session.seconds_remaining(),
        'participant_count': session.participants.count(),
        'answered_count': answered,
        'leaderboard': [{'name': p.name, 'score': p.score} for p in session.participants.all()],
    })


# --------------------------------------------------------------------------
# Host side
# --------------------------------------------------------------------------
@login_required
def dashboard(request):
    quizzes = Quiz.objects.filter(created_by=request.user).annotate(q_count=Count('questions'))
    sessions = Session.objects.filter(host=request.user).select_related('quiz')[:10]
    return render(request, 'quiz/dashboard.html', {'quizzes': quizzes, 'sessions': sessions})


@login_required
@require_GET
def quiz_search(request):
    """AJAX live search over the host's quizzes."""
    q = request.GET.get('q', '').strip()
    quizzes = Quiz.objects.filter(created_by=request.user).annotate(q_count=Count('questions'))
    if q:
        quizzes = quizzes.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return JsonResponse({'results': [
        {'id': z.id, 'title': z.title, 'description': z.description,
         'q_count': z.q_count, 'created': z.created_at.strftime('%d %b %Y')}
        for z in quizzes
    ]})


@login_required
def quiz_create(request):
    form = QuizForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quiz = form.save(commit=False)
        quiz.created_by = request.user
        quiz.save()
        messages.success(request, 'Quiz created. Now add some questions.')
        return redirect('quiz_edit', quiz_id=quiz.id)
    return render(request, 'quiz/quiz_form.html', {'form': form, 'title': 'New quiz'})


@login_required
def quiz_edit(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    form = QuizForm(request.POST or None, instance=quiz)
    formset = QuestionFormSet(request.POST or None, instance=quiz)
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, 'Quiz saved.')
        return redirect('quiz_edit', quiz_id=quiz.id)
    return render(request, 'quiz/quiz_edit.html', {'quiz': quiz, 'form': form, 'formset': formset})


@login_required
@require_POST
def quiz_delete(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    quiz.delete()
    messages.success(request, 'Quiz deleted.')
    return redirect('dashboard')


@login_required
@require_POST
def session_create(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    if not quiz.questions.exists():
        messages.error(request, 'Add at least one question before hosting a session.')
        return redirect('quiz_edit', quiz_id=quiz.id)
    session = Session.objects.create(quiz=quiz, host=request.user)
    return redirect('host_dashboard', session_id=session.id)


@login_required
def host_dashboard(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    return render(request, 'quiz/host_dashboard.html', {
        'session': session,
        'question': session.current_question() if session.has_started else None,
        'total_questions': session.quiz.questions.count(),
        'leaderboard': session.participants.all(),
        'join_url': request.build_absolute_uri(reverse('join_session')),
        'remaining': session.seconds_remaining(),
    })


@login_required
@require_POST
def start_quiz(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    if not session.has_started:
        session.has_started = True
        session.current_question_index = 0
        session.current_question_started_at = timezone.now()
        session.save()
    return redirect('host_dashboard', session_id=session.id)


@login_required
@require_POST
def next_question(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    if session.has_started and not session.is_finished:
        session.current_question_index += 1
        session.current_question_started_at = timezone.now()
        if session.is_finished:
            session.is_active = False
        session.save()
    return redirect('host_dashboard', session_id=session.id)


@login_required
@require_POST
def end_session(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    session.has_started = True
    session.current_question_index = session.quiz.questions.count()
    session.is_active = False
    session.save()
    return redirect('results', session_id=session.id)


# --------------------------------------------------------------------------
# Results + exports
# --------------------------------------------------------------------------
def _results_rows(session):
    total_q = session.quiz.questions.count()
    rows = []
    for rank, p in enumerate(session.participants.all(), start=1):
        correct = p.answers.filter(is_correct=True).count()
        rows.append({'rank': rank, 'name': p.name, 'score': p.score,
                     'correct': correct, 'answered': p.answers.count(), 'total': total_q})
    return rows


@login_required
def results(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    return render(request, 'quiz/results.html', {'session': session, 'rows': _results_rows(session)})


@login_required
def export_csv(request, session_id):
    session = get_object_or_404(Session, id=session_id, host=request.user)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="quiz_{session.room_code}_results.csv"'
    writer = csv.writer(response)
    writer.writerow(['Rank', 'Name', 'Score', 'Correct answers', 'Questions answered', 'Total questions'])
    for r in _results_rows(session):
        writer.writerow([r['rank'], r['name'], r['score'], r['correct'], r['answered'], r['total']])
    return response


@login_required
def export_pdf(request, session_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    session = get_object_or_404(Session, id=session_id, host=request.user)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()

    story = [
        Paragraph(f'Quiz Results: {session.quiz.title}', styles['Title']),
        Paragraph(f'Room code: {session.room_code} &nbsp;|&nbsp; Host: {session.host.username} '
                  f'&nbsp;|&nbsp; Date: {session.started_at:%d %b %Y}', styles['Normal']),
        Spacer(1, 0.6 * cm),
    ]
    data = [['Rank', 'Name', 'Score', 'Correct', 'Answered']]
    for r in _results_rows(session):
        data.append([r['rank'], r['name'], r['score'], f"{r['correct']}/{r['total']}",
                     f"{r['answered']}/{r['total']}"])
    if len(data) == 1:
        data.append(['-', 'No participants', '-', '-', '-'])

    table = Table(data, repeatRows=1, colWidths=[1.8 * cm, 7 * cm, 2.5 * cm, 2.5 * cm, 2.7 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="quiz_{session.room_code}_results.pdf"'
    return response
