# serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Query

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Ensure the password is not exposed in responses.
    email = serializers.EmailField(required=True)  # Ensure email is required.

    class Meta:
        model = User  # Connect the serializer to the User model.
        fields = ['username', 'email' ,'password']  # Specify the fields exposed by this serializer.

    def create(self, validated_data):
        # Override the default create method to handle password hashing.
        return User.objects.create_user(**validated_data)

class QuerySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Query
        fields = ['id', 'query_text', 'created_at', 'username']


