from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from matching.search import perform_search
from ..models import Search, SearchHistory
from ..serializers import SearchSerializer
from itertools import groupby
from operator import itemgetter

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    """
    API endpoint that allows users to search through the document database.
    Groups results by filename and maintains score-based ordering within groups.
    """
    query_text = request.data.get('search')
    
    # Validate input
    if not query_text or not query_text.strip():
        return Response(
            {"error": "Query text is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Perform the search
    search_response = perform_search(query_text, request)
    
    
    # Check for errors
    if isinstance(search_response, dict) and "error" in search_response:
        return Response(
            {"error": search_response["error"]}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Extract results from the response
    if not isinstance(search_response, dict) or 'results' not in search_response:
        return Response(
            {"error": "Invalid search response format"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    search_results = search_response['results']
    
    if not search_results:
        return Response({'results': []}, status=status.HTTP_200_OK)

    # Sort results by filename and then by score in descending order
    sorted_results = sorted(search_results, key=lambda x: (x['filename'], -x['score']))
    
    # Group results by filename
    grouped_results = []
    for filename, group in groupby(sorted_results, key=itemgetter('filename')):
        group_list = list(group)
        # Sort the group by score in descending order
        group_list.sort(key=lambda x: x['score'], reverse=True)
        grouped_results.append({
            'filename': filename,
            'matches': group_list
        })
    
    # Sort groups by the highest score in each group
    grouped_results.sort(key=lambda x: max(item['score'] for item in x['matches']), reverse=True)
    
    response_data = {
        'results': grouped_results
    }
    
    search_instance = Search.objects.create(
        user=request.user,
        search_text=query_text,
        response_text=response_data
    )

    search_history, created = SearchHistory.objects.get_or_create(user=request.user)
    search_history.searches.add(search_instance)
    search_history.update_timestamps()

    return Response(response_data, status=status.HTTP_200_OK)

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

