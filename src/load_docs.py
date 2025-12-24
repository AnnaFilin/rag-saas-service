# src/load_docs.py
# --------------------------------------------
# Handles downloading a PDF file and converting it to Markdown
# using the MarkItDown library.

# import requests
from pathlib import Path
from markitdown import MarkItDown


# def download_file(url: str, file_path: Path):
#     """
#     Download file from URL if it doesn't already exist.
#     Returns the path to the downloaded file.
#     """
#     file_path.parent.mkdir(parents=True, exist_ok=True)
#     if not file_path.exists():
#         response = requests.get(url, stream=True, timeout=30)
#         response.raise_for_status()
#         file_path.write_bytes(response.content)
#         print(f"✅ Downloaded: {file_path}")
#     else:
#         print(f"ℹ️ Already exists: {file_path}")
#     return file_path


# def convert_to_markdown(file_path: Path):
#     """
#     Convert a PDF file to Markdown text using MarkItDown.
#     Returns the markdown content as a string.
#     """
#     md = MarkItDown()
#     result = md.convert(file_path)
#     text_content = result.text_content

#     print("\n📄 Preview (first 300 chars):")
#     print(text_content[:300] + "...\n")
#     print(f"✅ Converted to markdown ({len(text_content):,} characters)")
#     return text_content


# def load_document(url: str, output_folder="documents", filename="thinkpython2.pdf"):
#     """
#     Full pipeline step:
#     - downloads the file (if missing)
#     - converts it to markdown
#     - returns { 'source': Path, 'content': str }
#     """
#     file_path = Path(output_folder) / filename
#     downloaded_path = download_file(url, file_path)
#     text = convert_to_markdown(downloaded_path)
#     return {"source": str(downloaded_path), "content": text}


from typing import List, Union

def convert_to_markdown(file_path: Union[str, Path]):
    """
    Convert a local PDF/MD file into markdown text.
    Returns dict: {"source": str, "content": str}
    """
    p = Path(file_path)
    md = MarkItDown()
    result = md.convert(p)
    text = result.text_content
    print(f"✅ Converted {p.name} ({len(text):,} chars)")
    return {"source": str(p), "content": text}


def load_local_documents(file_paths: List[Union[str, Path]]):
    """
    Convert multiple local files (PDF/MD) to markdown documents.
    Returns a list of {"source": str, "content": str}.
    """
    docs = []
    for fp in file_paths:
        docs.append(convert_to_markdown(fp))
    return docs


# if __name__ == "__main__":
#     # Example run
#     url = "https://greenteapress.com/thinkpython2/thinkpython2.pdf"
#     document = load_document(url)
#     print(f"Document ready: {len(document['content']):,} characters")
