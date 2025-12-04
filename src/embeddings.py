from typing import Iterable
import numpy as np
from sentence_transformers import SentenceTransformer

def create_embeddings(
    chunks: Iterable[dict],
    model_name: str = "multi-qa-mpnet-base-dot-v1",
    model: SentenceTransformer | None = None,
) -> tuple[np.ndarray, SentenceTransformer]:
    """
    Encode chunk contents into embeddings, reusing an existing model when provided.
    """
    if model is None:
        print("\n🧠 Loading embedding model...")
        model = SentenceTransformer(model_name)

    texts = [chunk["content"] for chunk in chunks]
    print(f"⚙️ Encoding {len(texts)} chunks into embeddings...")
    embeddings = model.encode(texts)

    print(f"✅ Embeddings created: shape={embeddings.shape}, dim={embeddings.shape[1]}")
    return embeddings, model