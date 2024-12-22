import os
import pdfplumber
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import RegexTokenizer, LowercaseFilter
from django.conf import settings

index_path = settings.INDEX_PATH
DATA_PATH = settings.DATA_PATH

def create_whoosh_index(index_path):
    """Creates a Whoosh index if it doesn't exist."""
    if not os.path.exists(index_path):
        os.mkdir(index_path)
        custom_analyzer = RegexTokenizer() | LowercaseFilter()
        schema = Schema(
            filename=ID(stored=True, unique=True), 
            page_num=ID(stored=True), 
            content=TEXT(stored=True, phrase=True, analyzer=custom_analyzer)  # Use custom analyzer
        )
        create_in(index_path, schema)
    return open_dir(index_path)


def get_already_indexed_files(index):
    """Returns a list of filenames that are already indexed."""
    filenames = set()
    with index.searcher() as searcher:
        for fields in searcher.all_stored_fields():
            filenames.add(fields['filename'])
    return filenames

def clean_text(text):
    """Normalize the extracted text to ensure better searchability."""
    if text:
        text = text.replace("\xa0", " ")  # Replace non-breaking spaces with regular space
        text = text.replace("\n", " ")    # Merge lines
        text = ' '.join(text.split())     # Remove extra spaces, tabs, etc.
    return text

def index_pdfs(index_path, DATA_PATH):
    """Indexes new PDF files that are not already in the index."""
    index = create_whoosh_index(index_path)
    indexed_files = get_already_indexed_files(index)
    writer = index.writer()
    
    for filename in os.listdir(DATA_PATH):
        if filename.endswith(".pdf") and filename not in indexed_files:
            pdf_path = os.path.join(DATA_PATH, filename)
            print(f"Indexing {filename}...")
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        page_text = clean_text(page_text)  # Normalize text here
                        if page_text:  # Ensure the page is not empty
                            writer.add_document(
                                filename=filename, 
                                page_num=str(i + 1), 
                                content=page_text
                            )
            except Exception as e:
                print(f"Error processing {filename}: {e}")
    
    writer.commit()
    print("Indexing completed successfully!")


'''
if __name__ == "__main__":
    # Configuration
    pdf_folder_path = './documents/'  # The folder where your PDFs are located
    index_path = './whoosh_index'  # This is the folder where the Whoosh index is stored

    # Index the PDFs (only new PDFs will be indexed)
    index_pdfs(index_path, pdf_folder_path)
'''