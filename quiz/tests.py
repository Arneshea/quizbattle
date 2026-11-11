from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import Quiz, Question, Session, Participant, Answer


class QuizFlowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user('host', password='pw12345!')
        self.quiz = Quiz.objects.create(title='Python Basics', created_by=self.host)
        for i in range(3):
            Question.objects.create(quiz=self.quiz, text=f'Q{i}', option_a='a', option_b='b',
                                    option_c='c', option_d='d', correct_option='B',
                                    time_limit_seconds=20)
        self.session = Session.objects.create(quiz=self.quiz, host=self.host)
        self.hostc = Client()
        self.hostc.login(username='host', password='pw12345!')
        self.player = Client()

    def join(self, client, name='Asha'):
        return client.post(reverse('join_session'),
                           {'room_code': self.session.room_code, 'name': name}, follow=True)

    def start(self):
        self.hostc.post(reverse('start_quiz', args=[self.session.id]))
        self.session.refresh_from_db()

    def answer(self, client, option='B'):
        q = self.session.current_question()
        return client.post(reverse('submit_answer', args=[self.session.id]),
                           {'question_id': q.id, 'selected_option': option})

    def test_join_and_waiting_room(self):
        r = self.join(self.player)
        self.assertContains(r, 'Waiting for the host')

    def test_bad_room_code(self):
        r = self.player.post(reverse('join_session'), {'room_code': 'ZZZZZZ', 'name': 'X'})
        self.assertContains(r, 'Invalid or inactive')

    def test_duplicate_name_blocked_for_other_device(self):
        self.join(self.player, 'Asha')
        r = self.join(Client(), 'asha')
        self.assertContains(r, 'already taken')

    def test_rejoin_same_device_ok(self):
        self.join(self.player, 'Asha')
        r = self.join(self.player, 'Asha')
        self.assertEqual(Participant.objects.count(), 1)
        self.assertContains(r, 'Waiting for the host')

    def test_cannot_answer_before_start(self):
        self.join(self.player)
        r = self.player.post(reverse('submit_answer', args=[self.session.id]),
                             {'question_id': 1, 'selected_option': 'B'})
        self.assertEqual(r.status_code, 400)

    def test_full_flow_scores_and_finishes(self):
        self.join(self.player)
        self.start()
        self.assertTrue(self.session.has_started)

        r = self.answer(self.player, 'B')
        data = r.json()
        self.assertTrue(data['correct'])
        self.assertGreaterEqual(data['points'], 10)
        self.assertLessEqual(data['points'], 15)

        # no double answering
        self.assertEqual(self.answer(self.player, 'B').status_code, 400)

        # wrong answer scores nothing
        self.hostc.post(reverse('next_question', args=[self.session.id]))
        self.session.refresh_from_db()
        r = self.answer(self.player, 'A')
        self.assertFalse(r.json()['correct'])
        self.assertEqual(r.json()['points'], 0)

        # finish
        self.hostc.post(reverse('next_question', args=[self.session.id]))
        self.hostc.post(reverse('next_question', args=[self.session.id]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_finished)
        self.assertFalse(self.session.is_active)
        r = self.player.get(reverse('play', args=[self.session.id]))
        self.assertContains(r, 'Quiz complete')

    def test_time_limit_enforced_server_side(self):
        self.join(self.player)
        self.start()
        self.session.current_question_started_at = timezone.now() - timedelta(seconds=40)
        self.session.save()
        r = self.answer(self.player, 'B')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Time', r.json()['error'])
        self.assertEqual(Answer.objects.count(), 0)

    def test_stale_question_rejected(self):
        self.join(self.player)
        self.start()
        old_q = self.session.current_question()
        self.hostc.post(reverse('next_question', args=[self.session.id]))
        r = self.player.post(reverse('submit_answer', args=[self.session.id]),
                             {'question_id': old_q.id, 'selected_option': 'B'})
        self.assertEqual(r.status_code, 400)

    def test_status_endpoint(self):
        self.join(self.player)
        self.start()
        d = self.player.get(reverse('session_status', args=[self.session.id])).json()
        self.assertTrue(d['has_started'])
        self.assertEqual(d['participant_count'], 1)
        self.assertTrue(0 < d['remaining'] <= 20)

    def test_host_pages_require_login_and_ownership(self):
        url = reverse('host_dashboard', args=[self.session.id])
        self.assertEqual(Client().get(url).status_code, 302)
        User.objects.create_user('other', password='pw12345!')
        other = Client()
        other.login(username='other', password='pw12345!')
        self.assertEqual(other.get(url).status_code, 404)

    def test_host_pages_render(self):
        self.join(self.player)
        for name in ['host_dashboard', 'results']:
            r = self.hostc.get(reverse(name, args=[self.session.id]))
            self.assertEqual(r.status_code, 200, name)
        self.start()
        self.assertEqual(self.hostc.get(reverse('host_dashboard', args=[self.session.id])).status_code, 200)
        self.assertContains(self.player.get(reverse('play', args=[self.session.id])), 'Question 1')

    def test_exports(self):
        self.join(self.player)
        self.start()
        self.answer(self.player, 'B')
        r = self.hostc.get(reverse('export_csv', args=[self.session.id]))
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn('Asha', r.content.decode())
        r = self.hostc.get(reverse('export_pdf', args=[self.session.id]))
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_quiz_crud_and_search(self):
        r = self.hostc.post(reverse('quiz_create'), {'title': 'Algorithms', 'description': 'sorting'})
        qz = Quiz.objects.get(title='Algorithms')
        self.assertRedirects(r, reverse('quiz_edit', args=[qz.id]))
        # add a question through the formset
        data = {
            'title': 'Algorithms', 'description': 'sorting',
            'questions-TOTAL_FORMS': '1', 'questions-INITIAL_FORMS': '0',
            'questions-MIN_NUM_FORMS': '0', 'questions-MAX_NUM_FORMS': '1000',
            'questions-0-text': 'Best sort?', 'questions-0-option_a': 'a', 'questions-0-option_b': 'b',
            'questions-0-option_c': 'c', 'questions-0-option_d': 'd',
            'questions-0-correct_option': 'A', 'questions-0-time_limit_seconds': '15',
        }
        self.hostc.post(reverse('quiz_edit', args=[qz.id]), data)
        self.assertEqual(qz.questions.count(), 1)
        # search
        res = self.hostc.get(reverse('quiz_search'), {'q': 'algo'}).json()['results']
        self.assertEqual([x['title'] for x in res], ['Algorithms'])
        res = self.hostc.get(reverse('quiz_search'), {'q': 'zzz'}).json()['results']
        self.assertEqual(res, [])
        # validation: bad time limit
        data['questions-0-time_limit_seconds'] = '1'
        r = self.hostc.post(reverse('quiz_edit', args=[qz.id]), data)
        self.assertContains(r, 'between 5 and 300')
        # empty quiz cannot be hosted
        empty = Quiz.objects.create(title='Empty', created_by=self.host)
        self.hostc.post(reverse('session_create', args=[empty.id]))
        self.assertFalse(Session.objects.filter(quiz=empty).exists())
        # delete
        self.hostc.post(reverse('quiz_delete', args=[qz.id]))
        self.assertFalse(Quiz.objects.filter(id=qz.id).exists())

    def test_signup_and_dashboard(self):
        c = Client()
        r = c.post(reverse('signup'), {'username': 'newhost', 'password1': 'Strong#Pass9x', 'password2': 'Strong#Pass9x'})
        self.assertRedirects(r, reverse('dashboard'))
        self.assertEqual(c.get(reverse('dashboard')).status_code, 200)
        r = c.post(reverse('logout'))
        self.assertEqual(r.status_code, 302)

    def test_end_session_early(self):
        self.join(self.player)
        self.start()
        self.hostc.post(reverse('end_session', args=[self.session.id]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_finished)
