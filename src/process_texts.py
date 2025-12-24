# src/process_texts.py
# --------------------------------------------
# Handles text splitting into chunks optimized for Q&A
# using LangChain's RecursiveCharacterTextSplitter.

from langchain_text_splitters import RecursiveCharacterTextSplitter
from collections import Counter


def split_into_chunks(
    text: str,
    source: str,
    chunk_size: int = 600,
    chunk_overlap: int = 120,
) -> list:
    """
    Split a document into overlapping text chunks for Q&A tasks.
    Returns a list of {'content': str, 'source': str}.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(text)
    chunked_docs = [{"content": chunk, "source": source} for chunk in chunks]

    print(f"✅ Split into {len(chunked_docs)} chunks "
          f"({chunk_size}-char size, {chunk_overlap}-char overlap)")
    return chunked_docs


def analyze_chunks(chunks: list):
    """
    Print simple statistics about created chunks:
    - total count
    - length range
    - source counts
    """
    lengths = [len(chunk["content"]) for chunk in chunks]
    sources = [chunk["source"] for chunk in chunks]
    counts = Counter(sources)

    print("\n📊 Chunk analysis:")
    print(f"  - Total chunks: {len(chunks)}")
    print(f"  - Length range: {min(lengths)}–{max(lengths)} characters")
    print(f"  - Sources: {dict(counts)}\n")


# if __name__ == "__main__":
#     # Example run for testing
#     sample_text = "Python is great.\n\nFunctions define reusable logic.\nLoops repeat actions."
#     chunks = split_into_chunks(sample_text, source="sample.txt")
#     analyze_chunks(chunks)
