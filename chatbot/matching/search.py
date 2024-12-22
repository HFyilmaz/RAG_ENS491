from whoosh.index import open_dir
from whoosh.query import Phrase
from whoosh import qparser
import re
from django.conf import settings
import os


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

def suggest_corrections(index_path, keyword):
    """Suggest corrections for the user's query using the Whoosh spelling corrector."""
    index = open_dir(index_path)
    with index.searcher() as searcher:
        corrector = searcher.corrector("content")
        suggestions = corrector.suggest(keyword, limit=3)
    return suggestions

def correct_query(index_path, query_string):
    """Attempt to correct the user's query using Whoosh's correct_query method."""
    index = open_dir(index_path)
    with index.searcher() as searcher:
        qp = qparser.QueryParser("content", index.schema)
        query = qp.parse(query_string)
        corrected = searcher.correct_query(query, query_string)
        if corrected.query != query:
            return corrected.string
    return None

def search_keyword(index_path, keyword):
    """Search the Whoosh index for the given keyword as an exact phrase."""
    index = open_dir(index_path)
    keyword = clean_query(keyword)
    results = []
    
    with index.searcher() as searcher:
        # Use a Phrase query to search for the exact phrase
        phrase_query = Phrase("content", keyword.split())
        hits = searcher.search(phrase_query, limit=None)  # Remove limit to see all results
        for hit in hits:
            raw_snippet = hit.highlights("content")
            clean_snippet = remove_html_tags(raw_snippet)
            results.append({
                "filename": hit["filename"],
                "page_num": hit["page_num"],
                "snippet": clean_snippet
            })
    
    return results

def perform_search(query_text):
    """Main function to perform search with corrections and suggestions."""
    try:
        index_path = settings.INDEX_PATH
        
        # First try to correct the query
        corrected_query = correct_query(index_path, query_text)
        
        if corrected_query:
            # Search with original query
            results = search_keyword(index_path, corrected_query)
        else:
            # Search with original query
            results = search_keyword(index_path, query_text)
        
        response = {
            "results": results,
        }
        
        # If no results found, add suggestions
        if not results:
            suggestions = suggest_corrections(index_path, query_text)
            response["suggestions"] = suggestions
            
        return response
        
    except Exception as e:
        return {"error": str(e)}
