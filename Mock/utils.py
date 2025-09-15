import numpy as np
from scipy.optimize import minimize
from django.core.cache import cache
from .models import Question, UserAnswer, CustomUser, UserAttempt, UserAttemptSection

def calculate_question_difficulty(question_id):
    """
    Savolning qiyinlik darajasini Rasch modeli asosida hisoblaydi.
    """
    cache_key = f'question_difficulty_{question_id}'
    cached_difficulty = cache.get(cache_key)
    if cached_difficulty is not None:
        return cached_difficulty

    try:
        question = Question.objects.get(id=question_id)
        answers = UserAnswer.objects.filter(question=question).select_related('section_attempt__attempt__user')

        if not answers.exists():
            return 0.0

        abilities = [answer.section_attempt.attempt.user.ability for answer in answers]
        responses = [1 if answer.is_correct else 0 for answer in answers]

        def log_likelihood(difficulty):
            likelihood = 0
            for ability, response in zip(abilities, responses):
                p = 1 / (1 + np.exp(-(ability - difficulty)))
                likelihood += response * np.log(p + 1e-10) + (1 - response) * np.log(1 - p + 1e-10)
            return -likelihood

        result = minimize(log_likelihood, x0=0.0, method='Nelder-Mead')
        difficulty = max(min(result.x[0], 3.0), -3.0)

        cache.set(cache_key, difficulty, timeout=3600)  # 1 soat kesh
        return difficulty
    except Question.DoesNotExist:
        return 0.0

def calculate_user_ability(user_id):
    """
    Foydalanuvchi qobiliyatini Rasch modeli asosida hisoblaydi.
    """
    cache_key = f'user_ability_{user_id}'
    cached_ability = cache.get(cache_key)
    if cached_ability is not None:
        return cached_ability

    try:
        user = CustomUser.objects.get(id=user_id)
        answers = UserAnswer.objects.filter(section_attempt__attempt__user=user).select_related('question')

        if not answers.exists():
            return 0.0

        difficulties = [answer.question.difficulty for answer in answers]
        responses = [1 if answer.is_correct else 0 for answer in answers]

        def log_likelihood(ability):
            likelihood = 0
            for difficulty, response in zip(difficulties, responses):
                p = 1 / (1 + np.exp(-(ability - difficulty)))
                likelihood += response * np.log(p + 1e-10) + (1 - response) * np.log(1 - p + 1e-10)
            return -likelihood

        result = minimize(log_likelihood, x0=0.0, method='Nelder-Mead')
        ability = max(min(result.x[0], 3.0), -3.0)

        cache.set(cache_key, ability, timeout=3600)
        return ability
    except CustomUser.DoesNotExist:
        return 0.0

def calculate_attempt_ability(attempt_id, section_attempt_id=None):
    """
    Muayyan imtihon urinishidagi yoki bo'lim urinishidagi qobiliyatni hisoblaydi.
    """
    cache_key = f'attempt_ability_{attempt_id}_{section_attempt_id or ""}'
    cached_ability = cache.get(cache_key)
    if cached_ability is not None:
        return cached_ability

    try:
        attempt = UserAttempt.objects.get(id=attempt_id)
        if section_attempt_id:
            answers = UserAnswer.objects.filter(section_attempt_id=section_attempt_id).select_related('question')
        else:
            answers = UserAnswer.objects.filter(section_attempt__attempt=attempt).select_related('question')

        if not answers.exists():
            return 0.0

        difficulties = [answer.question.difficulty for answer in answers]
        responses = [1 if answer.is_correct else 0 for answer in answers]

        def log_likelihood(ability):
            likelihood = 0
            for difficulty, response in zip(difficulties, responses):
                p = 1 / (1 + np.exp(-(ability - difficulty)))
                likelihood += response * np.log(p + 1e-10) + (1 - response) * np.log(1 - p + 1e-10)
            return -likelihood

        result = minimize(log_likelihood, x0=0.0, method='Nelder-Mead')
        ability = max(min(result.x[0], 3.0), -3.0)

        cache.set(cache_key, ability, timeout=3600)
        return ability
    except UserAttempt.DoesNotExist:
        return 0.0

def update_question_difficulties():
    """
    Barcha savollar uchun qiyinlikni yangilaydi.
    """
    questions = Question.objects.all()
    for question in questions:
        question.difficulty = calculate_question_difficulty(question.id)
        question.save()

def update_user_abilities():
    """
    Barcha foydalanuvchilar uchun qobiliyatni yangilaydi.
    """
    users = CustomUser.objects.filter(role='student')
    for user in users:
        user.ability = calculate_user_ability(user.id)
        user.save()

def get_adaptive_question(user, section_attempt, answered_question_ids):
    """
    Foydalanuvchi qobiliyatiga va bo'lim qoidalariga mos keluvchi savolni tanlaydi.
    """
    user_ability = calculate_attempt_ability(section_attempt.attempt.id, section_attempt.id)
    section = section_attempt.exam_section
    exam = section_attempt.attempt.exam

    questions = []
    static_questions = section.static_questions.all().select_related('question')
    questions.extend([sq.question for sq in static_questions])

    topic_rules = section.topic_rules.all()
    for rule in topic_rules:
        topic_questions = Question.objects.filter(
            subtopic__topic=rule.topic,
            author=exam.teacher
        ).exclude(id__in=answered_question_ids)[:rule.question_count]
        questions.extend(topic_questions)

    subtopic_rules = section.subtopic_rules.all()
    for rule in subtopic_rules:
        subtopic_questions = Question.objects.filter(
            subtopic=rule.subtopic,
            author=exam.teacher
        ).exclude(id__in=answered_question_ids)[:rule.question_count]
        questions.extend(subtopic_questions)

    if not questions:
        return None

    # Rasch modeliga asoslangan adaptiv savol tanlash
    suitable_questions = [
        q for q in questions
        if user_ability - 0.5 <= q.difficulty <= user_ability + 0.5
    ]
    return suitable_questions[0] if suitable_questions else questions[0]