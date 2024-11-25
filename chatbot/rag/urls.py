from django.urls import path

from . import views


app_name = "rag"

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('populate/', views.populate_database, name='populate_database'),
]