from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('telegram-login/', views.telegram_login, name='telegram_login'),
    path('logout/', views.logout_view, name='logout'),
     path('profile/', views.profile_view, name='profile'),
    path('price/', views.price_view, name='price'),
    path('purchase/<str:purchase_type>/<int:item_id>/', views.process_purchase_view, name='process_purchase'),
    path('change-password/', views.change_password, name='change_password'),
    path('tests/', views.tests, name='tests'),

    path('create-adaptive/step-1/', views.create_adaptive_exam_step1, name='create_adaptive_exam_step1'),
    path('create-adaptive/step-2/', views.create_adaptive_exam_step2, name='create_adaptive_exam_step2'),

    path('exam/select-topic/', views.select_topic_for_exam, name='select_topic_for_exam'),
    path('exam/topic-questions/<int:topic_id>/', views.questions_by_topic_for_exam, name='questions_by_topic_for_exam'),
    
    path('create-static/step-1/', views.create_static_exam_step1, name='create_static_exam_step1'),
    path('create-static/step-2/<int:exam_id>/', views.create_static_exam_step2, name='create_static_exam_step2'),

    path('section/<int:section_id>/edit/', views.edit_section, name='edit_section'),
    path('teacher/delete-section/<int:section_id>/', views.delete_section, name='delete_section'),

    path('exam/topics/<int:exam_id>/', views.exam_topics_list, name='exam_topics_list'),
    path('exam/topic/<int:exam_id>/<int:topic_id>/subtopics/', views.exam_subtopic_list, name='exam_subtopic_list'),
    path('exam/subtopic/<int:exam_id>/<int:subtopic_id>/questions/', views.exam_subtopic_questions, name='exam_subtopic_questions'),
    path('exam/uncategorized/<int:exam_id>/questions/', views.exam_uncategorized_questions, name='exam_uncategorized_questions'),
    path('exams/<int:pk>/', views.exam_detail, name='exam_detail'),
    
    path('start-exam/<int:exam_id>/', views.start_exam, name='start_exam'),
    path('test/<int:exam_id>/<int:attempt_id>/', views.test_page, name='test_page'),
    path('test-ajax/', views.handle_test_ajax, name='handle_test_ajax'),
    path('get-question/', views.get_question, name='get_question'),
    path('results/', views.student_results, name='student_results'),
    path('result/<int:attempt_id>/', views.view_result_detail, name='view_result_detail'),
    path('teacher/results/', views.teacher_results, name='teacher_results'),
    path('teacher/result/<int:attempt_id>/', views.teacher_view_result_detail, name='teacher_view_result_detail'),
    path('teacher/tests/', views.my_exams, name='my_exams'),
    path('teacher/edit-exam/<int:exam_id>/', views.edit_exam, name='edit_exam'),
    path('teacher/delete-exam/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('teacher/delete-section/<int:section_id>/', views.delete_section, name='delete_section'),
    path('teacher/remove-question/<int:section_id>/<int:question_id>/', views.remove_question_from_section, name='remove_question_from_section'),

    path('my-questions/', views.my_questions_home, name='my_questions'),
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    path('subtopic/<int:subtopic_id>/', views.subtopic_questions, name='subtopic_questions'),
    path('uncategorized/', views.uncategorized_questions, name='uncategorized_questions'),
    
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    path('subtopic/<int:subtopic_id>/', views.subtopic_questions, name='subtopic_questions'),
    path('create-topic/', views.create_topic, name='create_topic'),
    path('edit-topic/<int:topic_id>/', views.edit_topic, name='edit_topic'),
    path('delete-topic/<int:topic_id>/', views.delete_topic, name='delete_topic'),
    path('create-subtopic/', views.create_subtopic, name='create_subtopic'),
    path('create-subtopic/<int:topic_id>/', views.create_subtopic, name='create_subtopic_for_topic'),
    path('edit-subtopic/<int:subtopic_id>/', views.edit_subtopic, name='edit_subtopic'),
    path('delete-subtopic/<int:subtopic_id>/', views.delete_subtopic, name='delete_subtopic'),
    path('move-questions/<int:subtopic_id>/', views.move_questions, name='move_questions'),


    path('flashcards/', views.list_flashcards, name='list_flashcards'),
    path('flashcards/create/', views.create_flashcard, name='create_flashcard'),
    path('flashcards/edit/<int:pk>/', views.edit_flashcard, name='edit_flashcard'),
    path('flashcards/delete/<int:pk>/', views.delete_flashcard, name='delete_flashcard'),
    path('api/search-flashcards/', views.search_flashcards_api, name='search_flashcards_api'),

    path('passages/', views.passage_list, name='passage_list'),
    path('passages/add/', views.add_passage, name='add_passage'),
    path('passages/edit/<int:pk>/', views.edit_passage, name='edit_passage'),
    path('passages/delete/<int:pk>/', views.delete_passage, name='delete_passage'),


    path('teacher/add-question/', views.add_question, name='add_question'),
    path('edit/<int:question_id>/', views.edit_question, name='edit_question'),
    path('teacher/delete-question/<int:question_id>/', views.delete_question, name='delete_question'),
    path('upload_image/', views.upload_image, name='upload_image'),
]