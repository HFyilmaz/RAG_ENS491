from whoosh.index import open_dir
from whoosh.query import Phrase
from whoosh import qparser
import re


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



if __name__ == "__main__":
    index_path = './whoosh_index'  # This is the folder where the Whoosh index is stored

    keyword = input("Enter an exact phrase to search for: ")
    
    # Correct the query before performing the search
    corrected_query = correct_query(index_path, keyword)
    if corrected_query:
        print(f"Did you mean: {corrected_query}?")
        user_response = input("Press Y to search with the corrected query, or press any other key to continue with the original query: ").strip().lower()
        if user_response == 'y':
            keyword = corrected_query
    
    results = search_keyword(index_path, keyword)
    
    if results:
        print("\nMatched Documents:")
        matched_files = set()
        for result in results:
            matched_files.add(result['filename'])
        
        for i, file in enumerate(matched_files):
            print(f"{i+1}. {file}")

        print("\n\n")

        print("\nMatching Results:")
        for i, result in enumerate(results):
            print(f"{i+1}. File: {result['filename']} | Page: {result['page_num']}")
            print(f"   Snippet: {result['snippet']}\n")
            print("--------------------------------------------\n")
    else:
        print("\nNo results found.")
        
        # Suggest possible corrections if no results found
        suggestions = suggest_corrections(index_path, keyword)
        if suggestions:
            print("\nDid you mean one of these?:")
            for i, suggestion in enumerate(suggestions):
                print(f"{i+1}. {suggestion}")
