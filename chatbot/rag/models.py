from django.db import models
from django.contrib.auth.models import AbstractUser

from django.conf import settings

import os

class RagUser(AbstractUser):
    USER_ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=USER_ROLE_CHOICES, default='user')

# Create your models here.
class UploadedFile(models.Model):
    file = models.FileField(upload_to="rag_database")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    

class Query(models.Model):
    user = models.ForeignKey(RagUser, related_name='queries', on_delete=models.SET_NULL, null=True)
    query_text = models.TextField()
    response_text = models.TextField()  # for very large, unbounded text
    created_at = models.DateTimeField(auto_now_add=True)

class Conversation(models.Model):
    created_at = models.DateTimeField(null=True, blank=True)  # Set when the first query is added
    last_modified = models.DateTimeField(null=True, blank=True)  # Set when a query is added or modified
    queries = models.ManyToManyField('Query', related_name='conversations', blank=True)
    user = models.ForeignKey(RagUser, related_name='conversations', on_delete=models.SET_NULL, null=True)


    def update_timestamps(self):
        queries = self.queries.order_by('created_at')
        if queries.exists():
            self.created_at = queries.first().created_at
            self.last_modified = queries.last().created_at
            self.save()


class RagFile(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(RagUser, related_name='files_uploaded', on_delete=models.SET_NULL, null=True)
    file_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


    ## Syncing model file whenever there is an update in the rag_database folder
    @classmethod
    def sync_rag_files(cls,user):
        # Get the list of all files in the folder
        for filename in os.listdir(settings.DATA_PATH):
            # Check if the file already exists in the database
            if not cls.objects.filter(file_name=filename).exists():
                # Create a new RagFile object
                cls.objects.create(file_name=filename, user=user)

    ## Deleting the file from folder
    @classmethod
    def delete_rag_file_from_folder(cls, file_name):          
        # Check if the file exists in the folder
        file_path = os.path.join(settings.DATA_PATH, file_name)
        if os.path.exists(file_path):
            # Delete the file from the folder
            os.remove(file_path)
        
        return f"File '{file_name}' deleted successfully."


