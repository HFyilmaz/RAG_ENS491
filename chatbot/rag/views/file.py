from django.shortcuts import render, redirect
from ..forms import FileUploadForm
from ..models import UploadedFile
from ..vectordb import populator
import os
from django.conf import settings

from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated]) 
def upload_file(request):
    # Handle file upload
    form = FileUploadForm(request.POST, request.FILES)
    if form.is_valid():
        form.save()

        # Save the files to the data directory
        data_dir = settings.DATA_PATH
        for file in request.FILES.getlist('file'):
            destination = os.path.join(data_dir, file.name)

            # Ensure the `data/` directory exists
            os.makedirs(data_dir, exist_ok=True)

            # Save the file
            with open(destination, 'wb+') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)

        # Populate database from "data" folder
        message = populator()

        return Response({"message": message}, status=status.HTTP_201_CREATED)
    else:
        return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
def register(request):
    serializer = UserSerializer(data=request.data)  # Bind JSON data to the serializer.

    if serializer.is_valid():  # Validate input data.
        user = serializer.save()  # Call the custom `create` method to save the user.
        

        # Return the tokens and user data
        return Response({
            "user": serializer.data,
        }, status=status.HTTP_201_CREATED)

    return Response({"error":serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login(request):
    username = request.data.get('username')  # Get username from request
    password = request.data.get('password')  # Get password from request

    # Validate input
    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Authenticate the user
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token

    # Return tokens and basic user information
    return Response({
        "user": {
            "username": user.username,
            "email": user.email
        },
        "refresh": str(refresh),
        "access": str(access)
    }, status=status.HTTP_200_OK)
