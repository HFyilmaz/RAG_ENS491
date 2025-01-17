from elasticsearch_dsl import Document, Text, Integer, connections
from elasticsearch_dsl.analysis import analyzer, tokenizer
from django.conf import settings
import os
from elasticsearch import Elasticsearch
import time

#TODO:
# 1. By default, searches return only the top 10 matching hits. 
# (https://www.elastic.co/guide/en/elasticsearch/reference/8.11/paginate-search-results.html)
# 2. Calculation of the score should be clear. 
# (https://www.one-tab.com/page/P9mPf495Squ9ngKmZdbYKg)


def get_elasticsearch_client():
    """Get Elasticsearch client with retries"""
    for _ in range(3):  # Try 3 times
        try:
            client = Elasticsearch(
                hosts=['http://localhost:9200'],
                verify_certs=False,
                ssl_show_warn=False,
                retry_on_timeout=True,
                max_retries=3,
                timeout=30
            )
            if client.ping():  # Test the connection
                return client
        except Exception as e:
            print(f"Connection attempt failed: {e}")
            time.sleep(1)  # Wait before retrying
    return None

# Initialize the connection
es_client = get_elasticsearch_client()
if es_client:
    connections.create_connection(
        hosts=['http://localhost:9200'],
        verify_certs=False,
        ssl_show_warn=False
    )
else:
    print("Failed to establish Elasticsearch connection")

# Custom analyzer for better text search
pdf_analyzer = analyzer('pdf_analyzer',
    tokenizer=tokenizer('standard'),
    filter=['lowercase', 'stop', 'snowball']
)

class PDFDocument(Document):
    """Elasticsearch document mapping for PDF content"""
    filename = Text(fields={'raw': Text(analyzer='keyword')})  # Add raw field for exact matching
    page_num = Integer()
    content = Text(analyzer=pdf_analyzer)
    
    class Index:
        name = 'pdf_documents'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

def setup_elasticsearch():
    """Initialize Elasticsearch index and mappings"""
    try:
        PDFDocument.init()
        return True
    except Exception as e:
        print(f"Error setting up Elasticsearch: {e}")
        return False

def file_exists_in_elasticsearch(filename):
    """Check if any document exists with the given filename"""
    try:
        client = get_elasticsearch_client()
        if not client:
            print("Failed to get Elasticsearch client")
            return False

        response = client.search(
            index=PDFDocument._index._name,
            body={
                "query": {
                    "term": {
                        "filename.raw": filename
                    }
                },
                "size": 1
            }
        )
        
        return response['hits']['total']['value'] > 0
    except Exception as e:
        print(f"Error checking file existence in Elasticsearch: {e}")
        return False

def index_pdf_content(filename, page_num, content):
    """Index a single page of PDF content"""
    try:
        doc = PDFDocument(
            filename=filename,
            page_num=page_num,
            content=content
        )
        doc.save()
        return True
    except Exception as e:
        print(f"Error indexing document: {e}")
        return False

def delete_file_from_elasticsearch(filename):
    """Delete all documents for a given filename from Elasticsearch"""
    try:
        # Get the Elasticsearch client
        client = get_elasticsearch_client()
        if not client:
            print("Failed to get Elasticsearch client")
            return False

        # Delete by query to remove all documents matching the exact filename
        response = client.delete_by_query(
            index=PDFDocument._index._name,
            body={
                "query": {
                    "term": {
                        "filename.raw": filename  # Use the raw field for exact matching
                    }
                }
            },
            refresh=True  # Make sure the index is refreshed after deletion
        )
        
        # Check if the deletion was successful
        deleted_count = response.get('deleted', 0)
        if deleted_count > 0:
            return True
        return False
    except Exception as e:
        print(f"Error deleting documents from Elasticsearch: {e}")
        return False

def search_content(query_text, request=None, minimum_score=0.25):
    """Search indexed PDF content with advanced features
    
    Args:
        query_text (str): The text to search for
        request: The HTTP request object
        minimum_score (float): Minimum score threshold (0 to 1). Higher values mean more relevant results.
                             Defaults to 0.25 for moderate filtering.
    """
    try:
        s = PDFDocument.search()
        
        # Set size to a large number to get all results
        s = s.extra(size=10000)  # This will return up to 10,000 results
        
        # Combine exact phrase matching with fuzzy matching
        s = s.query(
            'bool',
            should=[
                # Exact phrase matching with high boost
                {
                    'match_phrase': {
                        'content': {
                            'query': query_text,
                            'boost': 10,  # Give highest priority to exact phrases
                            'slop': 1  # Allow only 1 word between phrase terms
                        }
                    }
                },
                # Fuzzy matching as fallback with lower boost
                {
                    'multi_match': {
                        'query': query_text,
                        'fields': ['content^2', 'filename'],
                        'fuzziness': 'AUTO',
                        'minimum_should_match': '75%',
                        'boost': 1  # Lower priority for fuzzy matches
                    }
                }
            ],
            minimum_should_match=1  # At least one should clause must match
        )
        
        # Add highlighting
        s = s.highlight('content', 
            fragment_size=75,
            number_of_fragments=3,
            pre_tags=['<mark>'],
            post_tags=['</mark>']
        )
        
        # Execute search
        response = s.execute()
        
        results = []
        if len(response) > 0:
            # Get the maximum score to normalize scores to 0-1 range
            max_score = response[0].meta.score
            
            for hit in response:
                # Normalize the score to 0-1 range
                normalized_score = hit.meta.score / max_score
                
                # Only include results that meet the minimum score threshold
                if normalized_score >= minimum_score:
                    file_path = request.build_absolute_uri(f"/media/rag_database/{hit.filename}")
                    
                    if hasattr(hit.meta, 'highlight') and hasattr(hit.meta.highlight, 'content'):
                        snippet = '...'.join(hit.meta.highlight.content)
                    else:
                        snippet = hit.content[:200] + '...' if len(hit.content) > 200 else hit.content
                    
                    results.append({
                        "filename": hit.filename,
                        "page_num": hit.page_num,
                        "snippet": snippet,
                        "file_url": file_path,
                        "score": round(normalized_score, 2)
                    })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
    except Exception as e:
        print(f"Error searching documents: {e}")
        return []


def clear_index():
    """Clear all indexed documents"""
    try:
        PDFDocument._index.delete()
        PDFDocument.init()
        return True
    except Exception as e:
        print(f"Error clearing index: {e}")
        return False 