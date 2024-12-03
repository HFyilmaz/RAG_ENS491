from django.urls import path

from .views import auth, file, llm


app_name = "rag"

urlpatterns = [
    path('upload/', file.upload_file, name='upload_file'),
    path('register/', auth.register, name='register'),
    path('login/', auth.login, name='login'),
    path('query/', llm.query, name='query'),
]