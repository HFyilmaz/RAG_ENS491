from langchain_community.document_loaders import PyPDFLoader

async def load_data_simple(file_path):
    loader = PyPDFLoader(file_path)
    pages = []
    async for page in loader.alazy_load():
        pages.append(page)
    return pages

def run_simple(pages):
    for i in range(3, 5):
        print(f"{pages[i].metadata}\n")
        print(pages[i].page_content)