from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.logout_view, name='logout'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('all_exams/', views.all_exams_view, name='all_exams'),
    path('exams/<int:exam_id>/start/', views.start_exam_view, name='exam_detail'),
    path('start-exam/<int:exam_id>/', views.start_exam_view, name='start_exam'),
    path('test/<int:exam_id>/<int:attempt_id>/', views.exam_mode_view, name='exam_mode'),
    path('exam-ajax/', views.handle_exam_ajax, name='exam_ajax'),
    path('price/', views.price_view, name='price'),
    path('achievements/', views.achievements_view, name='achievements'),
    path('test/<int:exam_id>/study/', views.study_mode_view, name='study_mode_page'),
    path('study/ajax/', views.handle_study_ajax, name='handle_study_ajax'),
    path('test-ajax/', views.handle_exam_ajax, name='handle_exam_ajax'),
    path('get-question/', views.get_question_data, name='get_question'),
    path('result/<int:attempt_id>/', views.view_result_detail, name='view_result_detail'),
    path('ajax/get_answer_detail/', views.get_answer_detail_ajax, name='get_answer_detail_ajax'),
    path('exam/<int:exam_id>/attempts/', views.exam_attempts_view, name='exam_attempts'),
    path('solution/<int:question_id>/', views.view_solution, name='view_solution'), 
    path('teacher/results/', views.teacher_results, name='teacher_results'),
    path('teacher/result/<int:attempt_id>/', views.teacher_view_result_detail, name='teacher_view_result_detail'),
    path('teacher/tests/', views.my_exams, name='my_exams'),

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
    

    path('exams/completed/', views.completed_exams_view, name='completed_exams'),
    path('flashcard/<int:exam_id>/', views.flashcard_exam_view, name='flashcard_exam_view'),
    path('update-flashcard-progress/', views.update_flashcard_progress, name='update_flashcard_progress'),
    path('my-flashcards/', views.my_flashcards_view, name='my_flashcards'),
    path('my-flashcards/practice/<str:status_filter>/', views.practice_flashcards_view, name='practice_flashcards'),
    
    path('purchase/<str:purchase_type>/<int:item_id>/', views.process_purchase_view, name='process_purchase'),
    path('upload-screenshot/<int:purchase_id>/', views.upload_screenshot_view, name='upload_screenshot'),

]