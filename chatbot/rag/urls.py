from django.urls import path

from . import views


app_name = "rag"

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
]