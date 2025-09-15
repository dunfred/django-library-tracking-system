import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_system.settings')

app = Celery('library_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.update(
    beat_schedule = {
        'check_overdue_loans_daily':{
            'task': 'library.tasks.check_overdue_loans',
            'schedule': crontab(hour=6, minute=0) # Run at 6 am everyday
        }
    }
)