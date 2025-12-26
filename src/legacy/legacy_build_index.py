# src/build_index.py
# --------------------------------------------
# Handles embedding generation and building a persistent ChromaDB index.

from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np
import chromadb
import math


def create_embeddings(chunks: list, model_name: str = "multi-qa-mpnet-base-dot-v1"):
    """
    Create embeddings for all text chunks using a SentenceTransformer model.
    Returns a tuple: (embeddings as np.ndarray, model).
    """
    print("\n🧠 Loading embedding model...")
    model = SentenceTransformer(model_name)

    texts = [chunk["content"] for chunk in chunks]
    print(f"⚙️ Encoding {len(texts)} chunks into embeddings...")
    embeddings = model.encode(texts)

    print(f"✅ Embeddings created: shape={embeddings.shape}, dim={embeddings.shape[1]}")
    return embeddings, model


def store_in_chroma(
    chunks: list,
    embeddings: np.ndarray,
    db_path: str = "./data/index/chroma_db",
    collection_name: str = "python_guide",
):
    """
    Store text chunks and embeddings in a persistent ChromaDB collection.
    Automatically splits large uploads into safe batches to avoid internal limits.
    Returns the Chroma collection instance.
    """
    db_dir = Path(db_path)
    db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "Knowledge base documents"}
    )

    metadatas = [{"document": Path(chunk["source"]).name} for chunk in chunks]
    documents = [chunk["content"] for chunk in chunks]

    print(f"✅ Preparing to store {len(documents)} documents in ChromaDB...")

    # Split large datasets into smaller safe batches
    batch_size = 5000  # Chroma’s safe upper limit
    total_batches = math.ceil(len(documents) / batch_size)

    for i in range(total_batches):
        start = i * batch_size
        end = min((i + 1) * batch_size, len(documents))
        print(f"📦 Adding batch {i + 1}/{total_batches} ({end - start} docs)...")

        collection.add(
            documents=documents[start:end],
            embeddings=embeddings[start:end].tolist(),
            metadatas=metadatas[start:end],
            ids=[f"doc_{j}" for j in range(start, end)],
        )

    print(f"✅ Total stored documents: {collection.count()}")
    print(f"📚 Sources: {set(Path(m['document']).stem for m in metadatas)}")
    return collection


if __name__ == "__main__":
    # Example test (dummy data)
    sample_chunks = [
        {"content": "Python defines functions with the def keyword.", "source": "sample.txt"},
        {"content": "Loops in Python include for and while statements.", "source": "sample.txt"},
    ]

    embeddings, model = create_embeddings(sample_chunks)
    collection = store_in_chroma(sample_chunks, embeddings)
