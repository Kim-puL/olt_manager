from celery import Celery

# The broker URL specifies the Redis server to use as a message broker.
# The backend URL is used to store the results of the tasks.
celery_app = Celery(
    'olt_manager',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['tasks']
)

# Celery configuration options
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Jakarta',
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    'check-expired-subscriptions-every-day': {
        'task': 'tasks.check_expired_subscriptions',
        'schedule': 86400.0,  # every 24 hours
    },
    'check-olt-status-every-minute': {
        'task': 'tasks.check_all_olts_status',
        'schedule': 60.0,  # every 60 seconds
    },
    'sync-all-olts-data-every-30-minutes': {
        'task': 'tasks.sync_all_olts_data',
        'schedule': 1800.0, # every 30 minutes
    },
}
