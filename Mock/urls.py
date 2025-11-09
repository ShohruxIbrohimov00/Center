from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.logout_view, name='logout'),
    

    path('dashboard/', views.dashboard_redirect_view, name='dashboard_base'),
    path('exam-ajax/', views.handle_exam_ajax, name='exam_ajax'),  
    path('test-ajax/', views.handle_exam_ajax, name='handle_exam_ajax'),
    path('get-question/', views.get_question_data, name='get_question'),
    path('ajax/get_answer_detail/', views.get_answer_detail_ajax, name='get_answer_detail_ajax'),
    path('move-questions/<int:subtopic_id>/', views.move_questions, name='move_questions'),
    path('change-password/', views.change_password_view, name='change_password'),

    path('<slug:slug>/exam/<int:exam_id>/attempts/', views.exam_attempts_view, name='exam_attempts'),
    path('<slug:slug>/exam/subject-result/<int:attempt_id>/', views.view_subject_exam_result, name='view_subject_exam_result'), 
    path('<slug:slug>/solution/<int:question_id>/', views.view_solution, name='view_solution'), 
    path('<slug:slug>/price/', views.price_view, name='price'),
    path('<slug:slug>/all_exams/', views.all_exams_view, name='all_exams'),
    path('<slug:slug>/exams/<int:exam_id>/start/', views.start_exam_view, name='start_exam'),
    path('<slug:slug>/test/<int:exam_id>/<int:attempt_id>/', views.exam_mode_view, name='exam_mode'),
    path('<slug:slug>/profile/', views.profile_view, name='profile'),
    
    path('<slug:slug>/dashboard/', views.dashboard_view, name='dashboard'),
    path('<slug:slug>/completed-exams/', views.completed_exams_view, name='completed_exams'),
    path('<slug:slug>/exams/<int:exam_id>/', views.exam_detail_view, name='exam_detail'), 
    path('<slug:slug>/result/<int:attempt_id>/', views.view_result_detail, name='view_result_detail'),
    path('<slug:slug>/teacher/results/', views.teacher_results, name='teacher_results'), 
    path('<slug:slug>/teacher/results/<int:attempt_id>/detail/', views.teacher_view_result_detail, name='teacher_view_result_detail'),
    path('<slug:slug>/student/courses/', views.all_courses_for_students, name='all_courses'),
    path('<slug:slug>/course/<int:pk>/', views.course_detail_view, name='course_detail'),
    path('<slug:slug>/course/<int:course_id>/roadmap/', views.course_roadmap_view, name='course_roadmap'),
    path('<slug:slug>/update-flashcard-progress/', views.update_flashcard_progress, name='update_flashcard_progress'),
    path('<slug:slug>/my-flashcards/', views.my_flashcards_view, name='my_flashcards'),
    path('<slug:slug>/my-flashcards/practice/<str:status_filter>/', views.practice_flashcards_view, name='practice_flashcards'),
    path('<slug:slug>/flashcards/list/<str:status_filter>/', views.flashcard_status_list_view, name='flashcard_status_list'),
    path('<slug:slug>/flashcard/<int:exam_id>/', views.flashcard_exam_view, name='flashcard_exam_view'),
    path('<slug:slug>/purchase/<str:purchase_type>/<int:item_id>/', views.process_purchase_view, name='process_purchase'),
    path('<slug:slug>/upload-screenshot/<int:purchase_id>/', views.upload_screenshot_view, name='upload_screenshot'),
    path('<slug:slug>/course/<int:course_id>/enroll/', views.course_enroll_view, name='course_enroll'),

    path('center/teacher/<slug:slug>/topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    path('center/teacher/<slug:slug>/subtopic/<int:subtopic_id>/', views.subtopic_questions, name='subtopic_questions'),
    path('center/teacher/<slug:slug>/subtopic/<int:subtopic_id>/edit/', views.edit_subtopic, name='edit_subtopic'),
    path('center/teacher/<slug:slug>/subtopic/<int:subtopic_id>/delete/', views.delete_subtopic, name='delete_subtopic'),
    path('center/teacher/<slug:slug>/create-topic/', views.create_topic, name='create_topic'),
    
    path('center/teacher/<slug:slug>/topic/<int:topic_id>/create-subtopic/', views.create_subtopic, name='create_subtopic'),
    path('center/teacher/<slug:slug>/topic/<int:topic_id>/edit/', views.edit_topic, name='edit_topic'),
    path('center/teacher/<slug:slug>/topic/<int:topic_id>/delete/', views.delete_topic, name='delete_topic'),
    path('center/teacher/<slug:slug>/uncategorized-questions/', views.uncategorized_questions, name='uncategorized_questions'),
    path('center/teacher/<slug:slug>/question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('center/teacher/<slug:slug>/question/<int:question_id>/delete/', views.delete_question, name='delete_question'),

    path('center/teacher/<slug:slug>/flashcards/', views.list_flashcards, name='list_flashcards'),
    path('center/teacher/<slug:slug>/flashcards/create/', views.create_flashcard, name='create_flashcard'),
    path('center/teacher/<slug:slug>/flashcards/edit/<int:pk>/', views.edit_flashcard, name='edit_flashcard'),
    path('center/teacher/<slug:slug>/flashcards/delete/<int:pk>/', views.delete_flashcard, name='delete_flashcard'),
    path('center/teacher/<slug:slug>/api/search-flashcards/', views.search_flashcards_api, name='search_flashcards_api'),
    
    path('center/teacher/<slug:slug>/passages/', views.passage_list, name='passage_list'),
    path('center/teacher/<slug:slug>/passages/add/', views.add_passage, name='add_passage'),
    path('center/teacher/<slug:slug>/passages/edit/<int:pk>/', views.edit_passage, name='edit_passage'),
    path('center/teacher/<slug:slug>/passages/delete/<int:pk>/', views.delete_passage, name='delete_passage'),

    path('center/teacher/<slug:slug>/my-questions/', views.my_questions, name='my_questions'),
    path('center/teacher/<slug:slug>/add-question/', views.add_question, name='add_question'),
    path('center/teacher/<slug:slug>/edit/<int:question_id>/', views.edit_question, name='edit_question'),
    path('center/teacher/<slug:slug>/delete-question/<int:question_id>/', views.delete_question, name='delete_question'),
    
    
    

    # ⭐️ O'QITUVCHI/ADMIN UCHUN: KURSLARNI BOSHQARISH (CRUD)
    path('<slug:slug>/courses/', views.course_list, name='course_list'),
    path('<slug:slug>/courses/create/',  views.course_create,  name='course_create'),
    path('<slug:slug>/courses/<int:pk>/update/',  views.course_update,  name='course_update'),
    path('<slug:slug>/courses/<int:pk>/delete/',  views.course_delete,  name='course_delete'),
    path('result/subject/<int:attempt_id>/', views.view_subject_exam_result, name='view_subject_exam_result'),

    # 1. KURS MODULLARI BOSHQARUVI
    path('courses/<int:course_id>/modules/', views.module_list, name='module_list'),
    path('courses/<int:course_id>/modules/create/', views.module_create, name='module_create'),
    path('courses/<int:course_id>/modules/<int:module_id>/edit/', views.module_update, name='module_update'),
    path('courses/<int:course_id>/modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),
    
    # 2. DARS BOSHQARUVI (Modul ichida)
    path('modules/<int:module_id>/lessons/', views.lesson_list, name='lesson_list'),
    path('modules/<int:module_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('lessons/<int:lesson_id>/update/', views.lesson_update, name='lesson_update'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),
    
    # 3. DARS RESURSLARI BOSHQARUVI (Dars ichida)
    path('lessons/<int:lesson_id>/resources/create/', views.resource_create, name='resource_create'),
    # path('resources/<int:pk>/update/', views.resource_update, name='resource_update'), # ...
    
    # 4. JADVAL BOSHQARUVI (Offline/Muddatli kurs uchun)
    path('courses/<int:course_id>/schedules/', views.schedule_list, name='schedule_list'),
    path('courses/<int:course_id>/schedules/create/', views.schedule_create, name='schedule_create'),
    path('course/<int:course_id>/schedules/<int:schedule_id>/update/', views.schedule_update, name='schedule_update'),
    path('course/<int:course_id>/schedules/<int:schedule_id>/delete/',  views.schedule_delete, name='schedule_delete'),



    path('center/teacher/<slug:slug>/tags/', views.tag_list_view, name='tag_list'),
    path('center/teacher/<slug:slug>/tags/create/', views.tag_create_or_update_view, name='tag_create'),
    path('center/teacher/<slug:slug>/tags/<int:tag_id>/update/', views.tag_create_or_update_view, name='tag_update'),
    path('center/teacher/<slug:slug>/tags/<int:tag_id>/delete/', views.tag_delete_view, name='tag_delete'),

    
    path('center/teacher/<slug:slug>/groups/',  views.group_list_view,  name='group_list'),
    path('center/teacher/<slug:slug>/groups/create/',  views.group_create_view,  name='group_create'),
    path('center/teacher/<slug:slug>/groups/<int:pk>/update/',  views.group_update_view,  name='group_update'),
    path('center/teacher/<slug:slug>/groups/<int:pk>/students/',  views.group_manage_students_view,  name='group_manage_students'),
    path('center/teacher/<slug:slug>/groups/<int:pk>/delete/', views.group_delete_view,  name='group_delete'),
    path('ajax/search-students/',  views.search_students_ajax,  name='search_students_ajax'),


    path('center/teacher/<slug:slug>/exams/', views.exam_list,  name='exam_list'),
    path('center/teacher/<slug:slug>/exams/create/', views.exam_create, name='exam_create'),
    path('center/teacher/<slug:slug>/exams/<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    path('center/teacher/<slug:slug>/exams/<int:pk>/delete/', views.exam_delete, name='exam_delete'),


    path('center/teacher/<slug:slug>/sections/',  views.section_list,  name='section_list'),
    path('center/teacher/<slug:slug>/sections/create/', views.section_create,  name='section_create'),
    path('center/teacher/<slug:slug>/sections/<int:section_id>/edit/',  views.section_edit,  name='section_edit'),
    path('center/teacher/<slug:slug>/sections/<int:section_id>/delete/',  views.section_delete, name='section_delete'),
    path('center/teacher/<slug:slug>/sections/<int:section_id>/questions/', views.static_questions_add, name='static_questions_add'),
    path('center/teacher/<slug:slug>/sections/<int:section_id>/save-questions/', views.save_static_questions, name='save_static_questions'),
    path('center/teacher/<slug:slug>/ajax/get-subtopics/',  views.get_subtopics,  name='get_subtopics'),
    path('center/teacher/<slug:slug>/ajax/get-questions/',  views.get_questions,  name='get_questions'),


    # O'qituvchilarni boshqarish (Markazga biriktirish)
    path('admin-panel/centers/<int:center_id>/remove-teacher/<int:user_id>/',  views.remove_teacher_view, name='center_remove_teacher'),
    path('ajax/search-unassigned-teachers/', views.search_unassigned_teachers_ajax, name='search_unassigned_teachers_ajax'),
    path('centers/<int:center_id>/assign-teacher/', views.assign_teacher_to_center, name='assign_teacher_to_center'),
    path('centers/ajax/<int:center_id>/groups/', views.center_groups_ajax, name='center_groups_ajax'),

    path('admin-panel/centers/', views.center_list_view, name='center_list'),
    path('admin-panel/center/create/', views.center_edit_view, name='center_create'),
    path('admin-panel/center/edit/<int:center_id>/', views.center_edit_view, name='center_update'), 
    path('admin-panel/delete/<int:center_id>/', views.center_delete_view, name='center_delete'),

    path('upload/ckeditor/', views.ckeditor_upload_image, name='ckeditor_upload'),
]