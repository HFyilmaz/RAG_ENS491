from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploaded_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Query(models.Model):
    user = models.ForeignKey(User, related_name='queries', on_delete=models.CASCADE)
    query_text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)