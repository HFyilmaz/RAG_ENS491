from elasticsearch_dsl import Document, Text, Integer, connections
from elasticsearch_dsl.analysis import analyzer, tokenizer
from django.conf import settings
import os
from elasticsearch import Elasticsearch
import time

#TODO:
# - Add Multi-level phrase matching
# - Add Search Suggestions
# - Improve the response structure

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

def search_content(query_text, request=None):
    """Search indexed PDF content with advanced features"""
    try:
        s = PDFDocument.search()
        
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
            fragment_size=25,
            number_of_fragments=3,
            pre_tags=['<mark>'],
            post_tags=['</mark>']
        )
        
        # Execute search
        response = s.execute()
        
        results = []
        for hit in response:
            file_path = request.build_absolute_uri(f"/media/rag_database/{hit.filename}")
            
            # Get highlighted snippets or fall back to content
            if hasattr(hit.meta, 'highlight') and hasattr(hit.meta.highlight, 'content'):
                snippet = '...'.join(hit.meta.highlight.content)
            else:
                snippet = hit.content[:200] + '...' if len(hit.content) > 200 else hit.content
                
            results.append({
                "filename": hit.filename,
                "page_num": hit.page_num,
                "snippet": snippet,
                "file_url": file_path,
                "score": hit.meta.score  # Add relevance score
            })
        
        # Sort results by score
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