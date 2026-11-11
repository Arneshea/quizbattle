# Live Classroom Quiz Battle

Full Stack Development Lab (24B15CS314) mini project: a Django app where a host runs a live,
timed quiz and players join from their phones with a room code. The leaderboard updates live
using AJAX polling (no page reloads).

## Quick start (Windows PowerShell)

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py seed_demo          # creates host/host12345 + a sample "Python Basics" quiz
    python manage.py runserver 0.0.0.0:8000

Want more quizzes? Load 7 ready-made ones (Python, Django, HTML/CSS/JS, DBMS, Networking, DevOps + a 3-question demo round):

    python manage.py seed_quizzes                 # goes to the first superuser (or creates host/host12345)
    python manage.py seed_quizzes --user arnesh   # or pick the account that should own them
    python manage.py seed_quizzes --user arnesh --reset   # wipe and re-add the samples

Safe to run repeatedly; existing quizzes are skipped. Edit `quiz/sample_data.py` to add your own.

Open http://127.0.0.1:8000/ . Admin panel: `python manage.py createsuperuser`, then /admin/.

## Demo with phones

1. Laptop and phones on the same Wi-Fi (or turn on the laptop's mobile hotspot and join it with the phones).
2. Find the laptop IP (`ipconfig`, look for IPv4). Phones open `http://<laptop-ip>:8000`.
3. If phones cannot connect, allow Python through Windows Firewall (private network) when prompted.
4. Bootstrap is bundled locally, so the demo works even without internet.

## How a session runs

1. Host logs in -> My quizzes -> **Host live** (creates a room code).
2. Players open the site, enter the room code + name, and wait in the lobby.
3. Host clicks **Start quiz**. The timer starts for question 1.
4. Players answer on their phones. Faster correct answers earn more (10 pts + up to 5 speed bonus).
5. Host clicks **Next question** / **Finish quiz**. Results page offers **CSV** and **PDF** export.

## Syllabus mapping

| Module | Where |
|---|---|
| Python & Django fundamentals | project layout, settings, MVT |
| Views, URLs, templates | `quiz/views.py`, `quiz/urls.py`, `templates/` |
| Template inheritance, static files | `templates/base.html`, `static/` (CSS, bundled Bootstrap) |
| ORM, relationships, CRUD, forms | `quiz/models.py` (FK relations), `quiz/forms.py` (ModelForms + inline formset) |
| Auth + Admin | login/logout/signup, `@login_required`, `quiz/admin.py` |
| Reporting + AJAX | CSV/PDF export (ReportLab), live quiz search, live leaderboard/timer polling |

## Models

Quiz -> Question (one-to-many); Quiz -> Session (one-to-many); Session -> Participant -> Answer.

## Tests

    python manage.py test

## Notes

- "Live" updates use AJAX polling every ~2 s (not WebSockets). Possible future scope: Django Channels.
- The countdown uses the server's clock, so phones with wrong time still show the right timer.
- `ALLOWED_HOSTS = ['*']` and `DEBUG = True` are for lab use only.