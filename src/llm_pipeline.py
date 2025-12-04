# src/llm_pipeline.py
# --------------------------------------------
# Local LLM (Ollama) + retrieval helpers. No hidden state.
# We expose a factory that builds a fresh chain in the caller's process.

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate


def build_llm_chain(model_name: str = "llama3.2:latest", temperature: float = 0.1):
    """
    Factory: build and return a ready-to-use LangChain 'chain' (Prompt -> LLM).
    Must be called in the same process where .invoke() will run.
    """
    print(f"🔧 Initializing LLM model: {model_name}")
    llm = OllamaLLM(model=model_name, temperature=temperature)

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            # "You are a Python programming expert. Based on the provided documentation, "
            # "answer the question clearly and accurately.\n\n"
            # "Documentation:\n{context}\n\n"
            # "Question: {question}\n\n"
            # "Answer (be specific about syntax, keywords, and provide examples when helpful):"
            "You are an ethnobotany researcher. Based on the provided texts, identify and describe plants traditionally used for visionary, lucid-dreaming, or trance-inducing purposes."


        ),
    )

    chain = prompt | llm
    print("🔧 Prompt template and chain created successfully.")
    return chain


def retrieve_context(question: str, model, collection, n_results: int = 5):
    """
    Retrieve relevant text chunks from the Chroma collection.
    Returns (context_string, documents_list).
    """
    query_emb = model.encode([question])
    results = collection.query(
        query_embeddings=query_emb.tolist(),
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    documents = results["documents"][0]
    context = "\n\n---SECTION---\n\n".join(documents)
    return context, documents


def get_llm_answer(chain, question: str, context: str) -> str:
    """
    Generate an answer from LLM given a question and context.
    """
    print("🚀 Sending request to LLM...")
    answer = chain.invoke({"context": context[:2000], "question": question})
    print("✅ LLM responded successfully.")
    return answer


def format_response(question: str, answer: str, sources: list) -> str:
    """
    Format the final markdown response with the question, answer, and top sources.
    """
    response = f"**Question:** {question}\n\n"
    response += f"**Answer:** {answer}\n\n"
    response += "**Sources:**\n"
    for i, chunk in enumerate(sources[:3], 1):
        preview = chunk[:100].replace("\n", " ") + "..."
        response += f"{i}. {preview}\n"
    return response


def enhanced_query_with_llm(question: str, model, collection, chain, n_results: int = 5) -> str:
    """
    Full pipeline (retrieve -> generate -> format). The 'chain' is created by the caller.
    """
    context, documents = retrieve_context(question, model, collection, n_results)
    print("🧩 Retrieved context preview:")
    print(context[:500] + "...\n")
    answer = get_llm_answer(chain, question, context)
    return format_response(question, answer, documents)


if __name__ == "__main__":
    # Direct diagnostic run (optional)
    from sentence_transformers import SentenceTransformer
    import chromadb

    model = SentenceTransformer("multi-qa-mpnet-base-dot-v1")
    client = chromadb.PersistentClient(path="./data/index/chroma_db")
    collection = client.get_or_create_collection(name="python_guide")

    chain = build_llm_chain()
    question = "What is a function in Python?"
    ctx = "A function is a block of code that performs a specific task when called."
    print("🚀 Testing direct LLM invocation...")
    print(get_llm_answer(chain, question, ctx))
