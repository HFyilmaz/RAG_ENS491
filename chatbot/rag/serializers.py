# serializers.py
from rest_framework import serializers
from .models import Query
from .models import RagFile
from .models import RagUser
from .models import Conversation
from .models import Search

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
    query_id = serializers.IntegerField(source='id')  # Map `id` to `query_id`
    sources = serializers.SerializerMethodField() # Defining custom field
    
    class Meta:
        model = Query
        fields = ['query_id', 'query_text', 'created_at', 'response_text', 'sources']

    def get_sources(self, obj):
        """
        Split the `sources` comma-separated string into a list.
        Handle empty or null values gracefully.
        """
        return obj.sources.split(",") if obj.sources else []

class SearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Search
        fields = ['id', 'search_text', 'response_text', 'created_at']

class ConversationSerializer(serializers.ModelSerializer):
    # Nested representation of queries
    queries = QuerySerializer(many=True, read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    conversation_id = serializers.IntegerField(source='id')

    class Meta:
        model = Conversation
        fields = ['conversation_id', 'created_at', 'last_modified', 'queries','username']
  

class RagFileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = RagFile
        fields = ['id', 'file_name', 'created_at','username']

