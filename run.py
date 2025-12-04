# # run.py
# # --------------------------------------------
# # Entry point for the memory-archive RAG system.
# # Two modes:
# #   - USE_UI = True  -> launch Gradio UI
# #   - USE_UI = False -> console mode (prints answers using enhanced_query_with_llm)

# from pathlib import Path
# import chromadb

# from src.load_docs import load_local_documents
# from src.process_texts import split_into_chunks, analyze_chunks
# from src.build_index import create_embeddings, store_in_chroma
# from src.llm_pipeline import build_llm_chain, enhanced_query_with_llm
# from src.stream_interface import launch_demo

# # ======= CONFIG =======
# USE_UI = True                      # переключай режимы тут
# COLLECTION_NAME = "python_guide"
# INDEX_PATH = Path("./data/index/chroma_db")
# DOC_FILES = [
#     "documents/9241545178.pdf",
#     "documents/TheEncyclopediaOfPsychoactivePlants.pdf",
# ]
# MAX_CHUNKS = 2000                  # мягкий лимит для тихой индексации
# EMBED_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"
# # =======================


# def _load_existing_index():
#     """Load existing Chroma collection and SentenceTransformer model."""
#     print("⚡ Using existing Chroma index — skipping regeneration.")
#     from sentence_transformers import SentenceTransformer

#     model = SentenceTransformer(EMBED_MODEL_NAME)
#     client = chromadb.PersistentClient(path=str(INDEX_PATH))
#     collection = client.get_or_create_collection(name=COLLECTION_NAME)
#     return model, collection


# def _build_index_from_documents():
#     """Full pipeline: load docs -> split -> (limit) -> embed -> store -> return (model, collection)."""
#     # 1) Load local PDFs
#     all_docs = load_local_documents(DOC_FILES)

#     # 2) Split into chunks
#     all_chunks = []
#     for doc in all_docs:
#         chunks = split_into_chunks(doc["content"], doc["source"])
#         all_chunks.extend(chunks)
#     analyze_chunks(all_chunks)

#     # 3) Safety limit to reduce fan noise (first run)
#     if len(all_chunks) > MAX_CHUNKS:
#         print(f"⚠️ Limiting processing to first {MAX_CHUNKS} chunks out of {len(all_chunks)} total for safety.")
#         all_chunks = all_chunks[:MAX_CHUNKS]

#     # 4) Embeddings + Chroma (batched)
#     embeddings, model = create_embeddings(all_chunks)
#     collection = store_in_chroma(
#         all_chunks,
#         embeddings,
#         db_path=str(INDEX_PATH),
#         collection_name=COLLECTION_NAME
#     )
#     return model, collection


# def main():
#     # 0) Prepare model+collection
#     if INDEX_PATH.exists():
#         model, collection = _load_existing_index()
#     else:
#         # создаём индекс один раз (с лимитом), дальше будет переиспользоваться
#         model, collection = _build_index_from_documents()

#     # 1) Build LLM chain (в том же процессе)
#     chain = build_llm_chain()
#     print("🦙 LLM initialized.")

#     if USE_UI:
#         # 2A) UI-режим (Gradio)
#         print("🌐 Launching Gradio interface…")
#         launch_demo(model, collection, chain)
#     else:
#         # 2B) Консольный режим (используем enhanced_query_with_llm)
#         question = "List specific plants mentioned in these books that are said to induce visionary or dream states. Include short notes about each."
#         response = enhanced_query_with_llm(question, model, collection, chain)
#         print("\n" + response)


# if __name__ == "__main__":
#     main()


# run.py
# --------------------------------------------
# Entry point for the Memory Archive RAG system.
# Modes:
#   - USE_UI = True  → launch Gradio interface
#   - USE_UI = False → run console mode (prints answers via enhanced_query_with_llm)

from pathlib import Path
import chromadb

from src.load_docs import load_local_documents
from src.process_texts import split_into_chunks, analyze_chunks
from src.build_index import create_embeddings, store_in_chroma
from src.llm_pipeline import build_llm_chain, enhanced_query_with_llm
from src.stream_interface import launch_demo

# ======= CONFIG =======
USE_UI = True                      # Toggle between UI and console modes
COLLECTION_NAME = "python_guide"   # Name of Chroma collection
INDEX_PATH = Path("./data/index/chroma_db")  # Persistent index path
DOC_FILES = [
    "documents/9241545178.pdf",
    "documents/TheEncyclopediaOfPsychoactivePlants.pdf",
]
MAX_CHUNKS = 2000                  # Soft limit to prevent heavy first-run embedding
EMBED_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"
# =======================


def _load_existing_index():
    """Load an existing Chroma index and SentenceTransformer model."""
    print("⚡ Using existing Chroma index — skipping regeneration.")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL_NAME)
    client = chromadb.PersistentClient(path=str(INDEX_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return model, collection


def _build_index_from_documents():
    """
    Full index creation pipeline:
    1. Load local documents
    2. Split them into chunks
    3. Limit total chunks (optional)
    4. Create embeddings
    5. Store in Chroma
    """
    # 1) Load local PDFs
    all_docs = load_local_documents(DOC_FILES)

    # 2) Split into semantic chunks
    all_chunks = []
    for doc in all_docs:
        chunks = split_into_chunks(doc["content"], doc["source"])
        all_chunks.extend(chunks)
    analyze_chunks(all_chunks)

    # 3) Apply a safety limit for the initial run
    if len(all_chunks) > MAX_CHUNKS:
        print(f"⚠️ Limiting processing to first {MAX_CHUNKS} chunks out of {len(all_chunks)} total for safety.")
        all_chunks = all_chunks[:MAX_CHUNKS]

    # 4) Generate embeddings and store them in Chroma
    embeddings, model = create_embeddings(all_chunks)
    collection = store_in_chroma(
        all_chunks,
        embeddings,
        db_path=str(INDEX_PATH),
        collection_name=COLLECTION_NAME
    )
    return model, collection


def main():
    """Main entry point — loads or builds index, initializes LLM, and runs UI or console mode."""
    # 0) Prepare model and collection
    if INDEX_PATH.exists():
        model, collection = _load_existing_index()
    else:
        # Build index once, then reuse it for future runs
        model, collection = _build_index_from_documents()

    # 1) Initialize the LLM chain
    chain = build_llm_chain()
    print("🦙 LLM initialized.")

    if USE_UI:
        # 2A) Launch Gradio-based UI mode
        print("🌐 Launching Gradio interface…")
        launch_demo(model, collection, chain)
    else:
        # 2B) Console mode — directly query the RAG system
        question = "List specific plants mentioned in these books that are said to induce visionary or dream states. Include short notes about each."
        response = enhanced_query_with_llm(question, model, collection, chain)
        print("\n" + response)


if __name__ == "__main__":
    main()
