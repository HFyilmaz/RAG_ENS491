from django.urls import path, include

from .views import auth, file, llm, matching, management, evaluation

app_name = "rag"

urlpatterns = [
    path('upload/', file.upload_file, name='upload_file'),
    path('rag_files/', file.get_rag_files, name='get_rag_files'),
    path('rag_file/<int:rag_file_id>', file.delete_rag_file, name='delete_rag_file'),
    path('register/', auth.register, name='register'),
    path('login/', auth.login, name='login'),
    path('status/', auth.get_status, name='get_status'),
    path('query/', llm.query, name='query'),
    path('queries/', llm.get_queries, name='get_queries'),
    path('conversations/',llm.get_conversations, name='get_conversations'),
    path('conversations/<int:conversation_id>/', llm.get_conversation, name='get_conversation'),
    path('conversations/<int:conversation_id>/update_name/', llm.update_conversation_name, name='update_conversation_name'),
    path('conversations/delete/<int:conversation_id>', llm.delete_conversation, name='delete_conversation'),
    path('search/', matching.search, name='search'),
    path('search_history/', matching.get_search_history, name='get_search_history'),
    path('delete_search_history/', matching.delete_search_history, name='delete_search_history'),
    path('users/', management.get_users, name='get_users'),
    path('add_user/', management.add_user, name='add_user'),
    path('users/delete/<int:user_id>', management.delete_user, name='delete_user'),
    path('password_reset/', include('django_rest_passwordreset.urls', namespace='password_reset')),
    
    # Evaluation endpoints
    path('evaluation/data/', evaluation.get_evaluation_data, name='get_evaluation_data'),
    path('evaluation/generate/', evaluation.generate_evaluation_qa_pairs, name='generate_evaluation_qa_pairs'),
    path('evaluation/filter/', evaluation.filter_evaluation_qa_pairs, name='filter_evaluation_qa_pairs'),
    path('evaluation/evaluate/pair/', evaluation.evaluate_qa_pair, name='evaluate_qa_pair'),
    path('evaluation/evaluate/all/', evaluation.evaluate_all_filtered_qa_pairs, name='evaluate_all_filtered_qa_pairs'),
]
