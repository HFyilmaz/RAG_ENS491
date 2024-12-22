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

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def query(request):
    query_text = request.data.get('query')  # Get username from request
    conversation_id = request.data.get('conversation_id')
    print(conversation_id)
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
    # Access the queries JSON field
    queries = conversation.queries.all() 
    
    # Initialize chat history
    chat_history = []

    # Loop through the queries and populate chat history
    if len(queries) == 0:
        chat_history.append(SystemMessage(content="No conversation history is available."))
    for query in queries:
        human_input = query.query_text
        ai_response = query.response_text

        # Append HumanMessage and AIMessage to chat_history
        chat_history.append(HumanMessage(content=human_input))
        chat_history.append(AIMessage(content=ai_response))

    response = query_llm(query_text, chat_history)
    # Save the query to the database, associating it with the authenticated user
    query_instance = Query.objects.create(user=request.user, query_text=query_text, response_text=response["response_text"])

    # Adding the query to the conversation
    conversation.queries.add(query_instance)
    # Updating the fields, "last_modified", and "created_at" depending on the newly added query(for last_modified especially)
    conversation.update_timestamps()

    


    return Response(response, status=status.HTTP_200_OK)



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