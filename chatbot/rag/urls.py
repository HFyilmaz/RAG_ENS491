from django.urls import path

from .views import auth, file, llm


app_name = "rag"

urlpatterns = [
    path('upload/', file.upload_file, name='upload_file'),
    path('get_rag_files/', file.get_rag_files, name='get_rag_files'),
    path('delete_rag_file/', file.delete_rag_file, name='delete_rag_file'),
    path('register/', auth.register, name='register'),
    path('login/', auth.login, name='login'),
    path('get_status/', auth.get_status, name='get_status'),
    path('query/', llm.query, name='query'),
    path('get_queries/', llm.get_queries, name='get_queries'),
]