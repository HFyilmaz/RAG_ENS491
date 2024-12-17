from django.urls import path

from .views import auth, file, llm


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
    path('conversations/<int:conversation_id>/', llm.get_conversation, name='get_conversation')

]