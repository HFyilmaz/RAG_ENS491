import re
from django.conf import settings
from django.urls import reverse
import os
from .elastic_search import search_content, index_pdf_content

def clean_query(query):
    """Cleans the user's input query to normalize it for phrase searching."""
    query = query.lower()
    query = re.sub(r"[-]+", " ", query)
    query = ' '.join(query.split())
    return query

def remove_html_tags(text):
    """Removes all HTML tags (like <b>...</b>) from the given text."""
    clean_text = re.sub(r'<.*?>', '', text)
    return clean_text

def perform_search(query_text, request=None):
    """Main function to perform search using Elasticsearch."""
    try:
        # Clean the query
        query_text = clean_query(query_text)
        
        # Perform the search using Elasticsearch
        results = search_content(query_text, request)
        
        response = {
            "results": results,
        }
        
        # If no results found, we could implement suggestions here
        if not results:
            response["suggestions"] = []
            
        return response
        
    except Exception as e:
        return {"error": str(e)}
