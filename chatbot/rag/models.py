from django.db import models
from django.contrib.auth.models import AbstractUser

from django.conf import settings
from django_rest_passwordreset.signals import reset_password_token_created
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

import os
from dotenv import load_dotenv

load_dotenv()

class RagUser(AbstractUser):
    USER_ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
        ('superadmin', 'Super Admin')
    ]
    role = models.CharField(max_length=10, choices=USER_ROLE_CHOICES, default='user')
    email = models.EmailField(unique=True)  # Ensure email is unique

# Create your models here.
class UploadedFile(models.Model):
    file = models.FileField(upload_to="rag_database")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    

class Query(models.Model):
    user = models.ForeignKey(RagUser, related_name='queries', on_delete=models.SET_NULL, null=True)
    query_text = models.TextField()
    response_text = models.TextField()  # for very large, unbounded text
    created_at = models.DateTimeField(auto_now_add=True)
    sources = models.TextField()
    
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

class Search(models.Model):
    user = models.ForeignKey(RagUser, related_name='searches', on_delete=models.SET_NULL, null=True)
    search_text = models.TextField()
    response_text = models.JSONField()  # Store the entire search response as JSON
    created_at = models.DateTimeField(auto_now_add=True)

'''    class Meta:
        ordering = ['-created_at']  # Order by most recent first'''

class SearchHistory(models.Model):
    user = models.ForeignKey(RagUser, related_name='search_history', on_delete=models.SET_NULL, null=True)
    searches = models.ManyToManyField('Search', related_name='search_history', blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True)

    def update_timestamps(self):
        searches = self.searches.order_by('created_at')
        if searches.exists():
            self.created_at = searches.first().created_at
            self.last_modified = searches.last().created_at
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
    
# When the API request is done, a new entry is being created in one of the database tables and this function is executed.
@receiver(reset_password_token_created)
def password_reset_token_created(reset_password_token, *args, **kwargs):
    #change it to 80 when using docker
    frontend_link = "http://localhost:80/"
    token = f"{reset_password_token.key}"

    full_link = str(frontend_link) + str("password-reset/") + str(token)
    print(full_link)

    context = {
        'full_link': full_link,
        'email_address': reset_password_token.user.email,
        'username': reset_password_token.user.username,
    }

    html_message = render_to_string('rag/password_reset_email.html', context=context)
    plain_message = strip_tags(html_message)

    msg = EmailMultiAlternatives(
        subject=f"Request to reset password for {reset_password_token.user.email}",
        body=plain_message,
        from_email=os.getenv("EMAIL_ADDR"),
        to=[reset_password_token.user.email]

    )
    msg.attach_alternative(html_message, "text/html")
    msg.send()