from celery import shared_task
from .utils import update_question_difficulties, update_user_abilities

@shared_task
def update_rasch_parameters():
    update_question_difficulties()
    update_user_abilities()