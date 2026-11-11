from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # participant
    path('', views.join_session, name='join_session'),
    path('play/<int:session_id>/', views.play, name='play'),
    path('play/<int:session_id>/answer/', views.submit_answer, name='submit_answer'),
    path('status/<int:session_id>/', views.session_status, name='session_status'),

    # auth
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),

    # host
    path('dashboard/', views.dashboard, name='dashboard'),
    path('quizzes/search/', views.quiz_search, name='quiz_search'),
    path('quizzes/new/', views.quiz_create, name='quiz_create'),
    path('quizzes/<int:quiz_id>/edit/', views.quiz_edit, name='quiz_edit'),
    path('quizzes/<int:quiz_id>/delete/', views.quiz_delete, name='quiz_delete'),
    path('quizzes/<int:quiz_id>/host/', views.session_create, name='session_create'),
    path('host/<int:session_id>/', views.host_dashboard, name='host_dashboard'),
    path('host/<int:session_id>/start/', views.start_quiz, name='start_quiz'),
    path('host/<int:session_id>/next/', views.next_question, name='next_question'),
    path('host/<int:session_id>/end/', views.end_session, name='end_session'),
    path('host/<int:session_id>/results/', views.results, name='results'),
    path('host/<int:session_id>/export/csv/', views.export_csv, name='export_csv'),
    path('host/<int:session_id>/export/pdf/', views.export_pdf, name='export_pdf'),
]
