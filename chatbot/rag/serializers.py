# serializers.py
from rest_framework import serializers
from .models import Query
from .models import RagFile
from .models import RagUser


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)  # Ensure the password is not exposed in responses.
    email = serializers.EmailField(required=True)  # Ensure email is required.
    role = serializers.ChoiceField(choices=RagUser.USER_ROLE_CHOICES, required=False, default='user')

    class Meta:
        model = RagUser  # Connect the serializer to the User model.
        fields = ['username', 'email' ,'password','role']  # Specify the fields exposed by this serializer.

    def create(self, validated_data):
        # Override the default create method to handle password hashing.
        return RagUser.objects.create_user(**validated_data)

class QuerySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Query
        fields = ['id', 'query_text', 'created_at', 'username', 'response_text']



class RagFileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RagFile
        fields = ['id', 'file_name', 'created_at','username']

