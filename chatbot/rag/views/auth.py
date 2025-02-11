from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

## Serializers to ensure input validation
from ..serializers import UserSerializer
import datetime

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_status(request):
    user = request.user  # Get the current authenticated user
    serializer = UserSerializer(user)  # Serialize the user object
    return Response(serializer.data, status=status.HTTP_200_OK)

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

    user.last_login = datetime.datetime.now()
    user.save(update_fields=['last_login'])
    # Return tokens and basic user information
    return Response({
        "user": {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "last_login": user.last_login
        },
        "refresh": str(refresh),
        "access": str(access)
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def reset_password(request):
    email = request.data.get('email')  # Get username from request

    return Response({
        "message": str(f"Email has been sent for {email}")
    }, status=status.HTTP_200_OK)
