from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from ..models import Query
from ..llm_model import query_llm
from ..serializers import QuerySerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def query(request):
    query_text = request.data.get('query')  # Get username from request
    # Validate input
    if not query_text.strip():
        return Response({"error": "Your query is empty!"}, status=status.HTTP_400_BAD_REQUEST)

    # Save the query to the database, associating it with the authenticated user
    query_instance = Query.objects.create(user=request.user, query_text=query_text)
    
    response = query_llm(query_text)
    return Response({"response": response}, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_queries(request):
    # Retrieve all queries submitted by the authenticated user
    queries = Query.objects.filter(user=request.user)
    
    # Serialize the queries using the QuerySerializer
    serializer = QuerySerializer(queries, many=True)
   
    return Response({"queries": serializer.data}, status=status.HTTP_200_OK)
