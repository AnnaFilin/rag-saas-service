# src/llm_pipeline.py
# --------------------------------------------
# Local LLM (Ollama) + retrieval helpers. No hidden state.
# We expose a factory that builds a fresh chain in the caller's process.

import os

from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


def build_llm_chain(
    role_prompt: str,
    model_name: str = "llama3.2:latest",
    temperature: float = 0.1,
):
    """
    Factory: build and return a ready-to-use LangChain 'chain' (Prompt -> LLM).
    Must be called in the same process where .invoke() will run.
    """
    backend = os.getenv("LLM_BACKEND", "ollama").lower()
    configured_model = os.getenv("LLM_MODEL", model_name)
    configured_temperature = float(os.getenv("LLM_TEMPERATURE", temperature))

    print(
        f"🔧 Initializing LLM backend={backend} model={configured_model} "
        f"temperature={configured_temperature}"
    )

    if backend == "ollama":
        llm = OllamaLLM(model=configured_model, temperature=configured_temperature)


    elif backend == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when using the OpenAI backend.")
        llm = ChatOpenAI(
            model=configured_model,
            temperature=configured_temperature,
            openai_api_key=api_key,
        )
    else:
        raise ValueError(
            'Unsupported LLM_BACKEND; only "ollama" and "openai" are implemented.'
        )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            role_prompt
            + "\n\n"
            "Context:\n{context}\n\n"
            "Question:\n{question}\n\n"
            "Rules:\n"
            "- Use ONLY the provided context.\n"
            "- Answer the question as fully as the context allows.\n"
            "- If some part of the question is not answered by the context, say:\n"
            "  \"I do not know based on the provided context.\""
        ),
    )

    chain = prompt | llm
    print("🔧 Prompt template and chain created successfully.")
    return chain


def get_llm_answer(chain, question: str, context: str) -> str:
    """
    Run the chain and always return a plain string answer,
    regardless of whether the LLM returns a string or an AIMessage-like object.
    """
    result = chain.invoke({"question": question, "context": context})

    # If the result is an AIMessage (has a .content) — take the content.
    if hasattr(result, "content"):
        return result.content

    # Otherwise just cast to string (in case it's already str or something similar).
    return str(result)


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
