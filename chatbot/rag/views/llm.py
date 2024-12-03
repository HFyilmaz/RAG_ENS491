from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from ..llm_model import query_llm

@api_view(['POST'])
def query(request):
    query = request.data.get('query')  # Get username from request
    # Validate input
    if not query.strip():
        return Response({"error": "Your query is empty!"}, status=status.HTTP_400_BAD_REQUEST)
    
    response = query_llm(query)
    return Response({"response": response}, status=status.HTTP_200_OK)