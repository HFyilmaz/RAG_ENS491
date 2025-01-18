from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from matching.search import perform_search
from ..models import Search, SearchHistory
from ..serializers import SearchSerializer

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

    search_results = perform_search(query_text, request)
    
    # Check for errors
    if "error" in search_results:
        return Response(
            {"error": search_results["error"]}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    search_instance = Search.objects.create(
        user=request.user,
        search_text=query_text,
        response_text=search_results
    )

    search_history, created = SearchHistory.objects.get_or_create(user=request.user)
    search_history.searches.add(search_instance)
    search_history.update_timestamps()

    return Response(search_results, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_search_history(request):
    """
    API endpoint that allows users to retrieve their search history.
    """
    searches = Search.objects.filter(user=request.user).order_by('-created_at')
    serializer = SearchSerializer(searches, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_search_history(request):
    """
    API endpoint that allows users to delete their entire search history.
    """
    # Delete all searches associated with the user
    Search.objects.filter(user=request.user).delete()
    
    # Also delete the SearchHistory instance if it exists
    SearchHistory.objects.filter(user=request.user).delete()
    
    return Response(status=status.HTTP_204_NO_CONTENT)

