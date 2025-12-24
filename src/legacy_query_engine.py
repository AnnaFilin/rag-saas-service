# src/query_engine.py
# --------------------------------------------
# Handles semantic querying and result formatting from a ChromaDB index.

from sentence_transformers import util


def format_query_results(question: str, query_embedding, results: dict, model):
    """
    Format and print query results with cosine similarity scores.
    """
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    print(f"\n🔎 Question: {question}\n")

    for i, doc in enumerate(documents):
        # Re-encode each retrieved document for precise similarity
        doc_embedding = model.encode([doc])
        similarity = util.cos_sim(query_embedding, doc_embedding)[0][0].item()
        source = metadatas[i].get("document", "Unknown")

        print(f"Result {i+1} (similarity: {similarity:.3f}) — {source}:")
        print(f"{doc[:300]}...\n")


def query_knowledge_base(question: str, model, collection, n_results: int = 3):
    """
    Query the knowledge base using a natural language question.
    Returns the raw ChromaDB query results.
    """
    # Encode question → embedding
    query_embedding = model.encode([question])

    # Perform semantic search
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    # Pretty-print formatted results
    format_query_results(question, query_embedding, results, model)
    return results


if __name__ == "__main__":
    # Simple demo using dummy data (requires an existing collection)
    from sentence_transformers import SentenceTransformer
    import chromadb

    model = SentenceTransformer("multi-qa-mpnet-base-dot-v1")
    client = chromadb.PersistentClient(path="./data/index/chroma_db")
    collection = client.get_or_create_collection(name="python_guide")

    query_knowledge_base("How do if-else statements work in Python?", model, collection)
