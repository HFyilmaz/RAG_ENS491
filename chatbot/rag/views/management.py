from django.shortcuts import render, redirect
from ..models import RagUser 
from ..vectordb import populator, delete_file_from_chroma
from ..serializers import UserSerializer
from ..permissions import IsSuperAdmin
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from django.core.mail import send_mail
from django.core.mail import EmailMessage
from django.conf import settings


from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

import secrets
RANDOM_STRING_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def get_users(request):
    # Query all RagFile objects
    users = RagUser.objects.all()

    # Serialize the data
    serializer = UserSerializer(users, many=True)

    # Return the serialized data
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def delete_user(request, user_id):
    try:
        user = RagUser.objects.get(id=user_id)
        
        user.delete()

        return Response({"message": f"User '{user.username}' deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    except RagUser.DoesNotExist:
        return Response({"error": f"User does not exist"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def add_user(request):

    #Randomly generated password -  LENGTH 12
    request.data["password"] = "".join(secrets.choice(RANDOM_STRING_CHARS) for i in range(12))
    

    serializer = UserSerializer(data=request.data)  # Bind JSON data to the serializer.

    if serializer.is_valid():  # Validate input data.
        user = serializer.save()  # Call the custom `create` method to save the user.
        
        subject = "Your account is ready to use!"
        
        context = {
            'username':request.data["username"],
            'password':request.data["password"],
            'role':request.data["role"]
        }
        email = EmailMessage(
            subject=subject,
            body=render_to_string('rag/account_creation_email.html', context=context),
            from_email=settings.EMAIL_HOST_USER,
            to=[request.data["email"]],
        )
        email.content_subtype = "html"  # Important: Set content type to HTML
        email.send()
        return Response({
            "message": f"Account creation is successfull!",
        }, status=status.HTTP_201_CREATED)

    return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)