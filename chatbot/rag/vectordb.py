import argparse
import os
import shutil
from django.conf import settings


from langchain_community.document_loaders import PyPDFDirectoryLoader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from langchain_chroma import Chroma

from sentence_transformers import SentenceTransformer

## CURRENT WORKING DIRECTORY OF PYTHON SCRIPTS IS THE ROOT DIRECTORY OF THE PROJECT
## THEREFORE WE NO LONGER CAN USE PATHS RELATIVE TO THE SCRIPTS PARENT DIRECTORY

CHROMA_PATH = settings.CHROMA_PATH
DATA_PATH = settings.DATA_PATH

# TODO: THESE NEEDS TO BE SET IN THE ADMIN PANEL
CHUNK_SIZE = 500
CHUNK_OVERLAP = 75

def populator():
    # Create (or update) the data store.
    try:
        documents = load_documents()
        chunks = split_documents(documents)
        # If new documents added, the message is set accordingly
        is_changed = add_to_chroma(chunks)
        return is_changed
    except Exception as e:
        return f"Error: {e}"


def load_documents():
    document_loader = PyPDFDirectoryLoader(DATA_PATH)
    return document_loader.load()


def split_documents(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)


def add_to_chroma(chunks: list[Document]):
    # Modify the source to include only the file name and append it to the base URL.
    for chunk in chunks:
        source = chunk.metadata.get("source")
        if source:
            chunk.metadata["source"] = f"http://127.0.0.1:8000/media/rag_database/{os.path.basename(source)}"

    # Load the existing database.
    db = Chroma(
        persist_directory=CHROMA_PATH, embedding_function=get_embedding_function_ollama()
    )

    # Calculate Page IDs.
    chunks_with_ids = calculate_chunk_ids(chunks)

    # Add or Update the documents.
    existing_items = db.get(include=[])  # IDs are always included by default
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB: {len(existing_ids)}")

    # Only add documents that don't exist in the DB.
    new_chunks = []
    for chunk in chunks_with_ids:
        if chunk.metadata["id"] not in existing_ids:
            new_chunks.append(chunk)


    if len(new_chunks):
        print(f"👉 Added new documents: {len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, ids=new_chunk_ids)
        return True
    print("No new documents to add")
    return False


def calculate_chunk_ids(chunks):
    # This will create IDs like "data/monopoly.pdf:6:2"
    # Page Source : Page Number : Chunk Index

    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page") + 1  # Page numbers starts from 1 instead of 0
        current_page_id = f"{source}:{page}"

        # If the page ID is the same as the last one, increment the index.
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        # Calculate the chunk ID.
        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        # Add it to the page meta-data.
        chunk.metadata["id"] = chunk_id

    return chunks


def clear_database():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)


# Wrapper class to make SentenceTransformer compatible
class EmbeddingWrapper:
    def __init__(self, model_name='sentence-transformers/all-mpnet-base-v2'):
        self.model = SentenceTransformer(model_name)
    
    # The vector store expects this method
    def embed_documents(self, texts):
        embeddings = self.model.encode(texts)
        return embeddings.tolist()  # Ensure embeddings are a list, not an array

    # Method to embed a single query
    def embed_query(self, query):
        return self.model.encode([query])[0]

def get_embedding_function():
    # Return an instance of the wrapper
    return EmbeddingWrapper()

#documents = load_documents()
#chunks = split_documents(documents)
#print(chunks[0])

from langchain_ollama import OllamaEmbeddings


def get_embedding_function_ollama():
    embeddings = OllamaEmbeddings(model="nomic-embed-text",base_url="http://host.docker.internal:11434")
    return embeddings

def delete_file_from_chroma(filename):
    """Delete all chunks for a given filename from Chroma database"""
    try:
        db = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=get_embedding_function_ollama()
        )
        # Get all document IDs that start with the file URL
        file_url = f"http://127.0.0.1:8000/media/rag_database/{filename}"
        existing_items = db.get(include=[])
        file_doc_ids = [doc_id for doc_id in existing_items["ids"] if doc_id.startswith(file_url)]
        if file_doc_ids:
            db.delete(ids=file_doc_ids)
        return True
    except Exception as e:
        print(f"Error deleting documents from Chroma: {e}")
        return False