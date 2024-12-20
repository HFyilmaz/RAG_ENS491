import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from ..models import Query
from ..models import Conversation
from ..llm_model import query_llm
from ..serializers import QuerySerializer
from ..serializers import ConversationSerializer
from ..permissions import IsAdmin, IsUser

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def query(request):
    query_text = request.data.get('query')  # Get query text from request
    conversation_id = request.data.get('conversation_id')
    
    # Validate input
    if not query_text.strip():
        return Response({"error": "Your query is empty!"}, status=status.HTTP_400_BAD_REQUEST)

    # If the id is not provided that means we are creating new conversation
    conversation = None
    if conversation_id:
        # Make sure provided id exists among conversations
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({"error": "Invalid conversation ID!"}, status=status.HTTP_404_NOT_FOUND)
    else:
        # If no conversation ID is provided, create a new conversation
        conversation = Conversation.objects.create(
            created_at=None,  # Will be set later when the first query is added
            last_modified=None,
            user=request.user
        )
    
    response_data = query_llm(query_text)
    
    if "error" in response_data:
        return Response({"error": response_data["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Save the query to the database, associating it with the authenticated user
    response_text = response_data.get("response", "")
    sources = response_data.get("sources", [])
    
    # Combine response and sources into a single JSON string for storage
    query_instance = Query.objects.create(
        user=request.user, 
        query_text=query_text, 
        response_text=json.dumps(response_data)  # Store as JSON in the database
    )

    # Adding the query to the conversation
    conversation.queries.add(query_instance)
    
    # Updating the fields, "last_modified", and "created_at" depending on the newly added query(for last_modified especially)
    conversation.update_timestamps()

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_queries(request):
    # Retrieve all queries submitted by the authenticated user
    queries = Query.objects.filter(user=request.user)
    
    # Serialize the queries using the QuerySerializer
    serializer = QuerySerializer(queries, many=True)
   
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversations(request):
    # Directly fetch conversations related to the authenticated user
    conversations = request.user.conversations.all()

    # Serialize the conversations
    serializer = ConversationSerializer(conversations, many=True)
    
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation(request, conversation_id):
    # Retrieve the conversation by ID, ensuring it's owned by the authenticated user
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)

    serializer = ConversationSerializer(conversation)

    return Response(serializer.data, status=status.HTTP_200_OK)