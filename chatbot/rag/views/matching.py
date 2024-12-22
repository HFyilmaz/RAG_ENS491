import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from matching.search import perform_search

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    """
    API endpoint that allows users to search through the document database.
    """
    query_text = request.data.get('search')
    
    # Validate input
    if not query_text or not query_text.strip():
        return Response(
            {"error": "Query text is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Perform the search
    search_results = perform_search(query_text)
    
    # Check for errors
    if "error" in search_results:
        return Response(
            {"error": search_results["error"]}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return Response(search_results, status=status.HTTP_200_OK)