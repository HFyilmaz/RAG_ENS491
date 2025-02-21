from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
import time
import logging

from ..models import Query
from ..models import Conversation
from ..llm_model import query_llm, generate_conversation_name
from ..serializers import QuerySerializer
from ..serializers import ConversationSerializer
from ..permissions import IsAdmin

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def query(request):
    start_time = time.time()
    
    query_text = request.data.get('query')
    conversation_id = request.data.get('conversation_id')
    logger.info(f"Processing query request - conversation_id: {conversation_id}")
    
    # Validate input
    if not query_text.strip():
        return Response({"error": "Your query is empty!"}, status=status.HTTP_400_BAD_REQUEST)

    # Conversation handling
    conversation_start = time.time()
    conversation = None
    is_new_conversation = False
    if conversation_id:
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({"error": "Invalid conversation ID!"}, status=status.HTTP_404_NOT_FOUND)
    else:
        conversation = Conversation.objects.create(
            created_at=None,
            last_modified=None,
            user=request.user
        )
        is_new_conversation = True
    logger.info(f"Conversation handling took: {time.time() - conversation_start:.2f} seconds")

    # Chat history processing
    history_start = time.time()
    queries = conversation.queries.all()
    chat_history = []
    if len(queries) == 0:
        chat_history.append(SystemMessage(content="No conversation history is available."))
    for query in queries:
        chat_history.append(HumanMessage(content=query.query_text))
        chat_history.append(AIMessage(content=query.response_text))
    logger.info(f"Chat history processing took: {time.time() - history_start:.2f} seconds")
    logger.info(f"Number of messages in history: {len(chat_history)}")

    # LLM Query
    llm_start = time.time()
    response = query_llm(query_text, chat_history)
    logger.info(f"LLM query took: {time.time() - llm_start:.2f} seconds")

    # Database operations
    db_start = time.time()
    comma_seperated_sources = ",".join(response["sources"])
    query_instance = Query.objects.create(
        user=request.user,
        query_text=query_text,
        response_text=response["response_text"],
        sources=comma_seperated_sources
    )
    
    if is_new_conversation:
        conversation_name = generate_conversation_name(query_text, response["response_text"])
        conversation.name = conversation_name
    
    conversation.queries.add(query_instance)
    conversation.update_timestamps()
    logger.info(f"Database operations took: {time.time() - db_start:.2f} seconds")

    # Prepare response
    response["conversation_id"] = conversation.id
    response["query_id"] = query_instance.id
    if is_new_conversation:
        response["conversation_name"] = conversation_name

    total_time = time.time() - start_time
    logger.info(f"Total query endpoint execution time: {total_time:.2f} seconds")

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
    # Directly fetch conversations related to the authenticated user, ordered by last_modified
    conversations = request.user.conversations.all().order_by('-last_modified')

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

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_conversation_name(request, conversation_id):
    # Retrieve the conversation by ID, ensuring it's owned by the authenticated user
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    
    # Get the new name from request data
    new_name = request.data.get('name')
    if not new_name:
        return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update the name and last_modified
    conversation.name = new_name
    conversation.last_modified = timezone.now()
    conversation.save()
    
    # Return the updated conversation
    serializer = ConversationSerializer(conversation)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_conversation(request, conversation_id):
    
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)


    conversation.delete()


    return Response({"message": f"Conversation with id {conversation_id} deleted successfully."}, status=status.HTTP_200_OK)

    