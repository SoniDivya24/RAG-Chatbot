from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app import config
from app.rag_engine import RagEngine

RETRIEVAL_K = 5
MAX_HISTORY_TURNS = 20


def get_text(response) -> str:
    """Gemini responses sometimes come back as a plain string, and sometimes as
    a list of content blocks (e.g. text + an internal thought-signature block).
    Normalize either shape to plain text.
    """
    content = response.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


class ChatSession:
    """One chat turn: retrieval (RagEngine) + conversation history combined
    into a single LLM call. Deliberately stateless — the caller passes in
    prior turns and gets the reply back, storing nothing server-side. The
    browser (localStorage) is the source of truth for conversation history.
    """

    def __init__(self, rag_engine: RagEngine) -> None:
        self.rag_engine = rag_engine
        self._llm: ChatGoogleGenerativeAI | None = None

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            config.require("GOOGLE_API_KEY")
            self._llm = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0.7)
        return self._llm

    def ask(self, user_message: str, history: list[dict] | None = None) -> dict:
        history = history or []
        has_documents = self.rag_engine.has_documents()
        relevant_chunks = (
            self.rag_engine.retrieve(user_message, RETRIEVAL_K) if has_documents else []
        )
        context = "\n\n".join(chunk["text"] for chunk in relevant_chunks)

        if has_documents:
            system_content = (
                "You are a helpful assistant answering questions about the uploaded "
                "documents. Use the CONTEXT below if it's relevant to the question. "
                "If the answer isn't in the context AND isn't something already "
                "established earlier in this conversation, say you don't have that "
                "information in the documents. Do not make up details.\n\n"
                f"CONTEXT:\n{context}"
            )
        else:
            system_content = (
                "You are a helpful assistant. No documents have been uploaded yet, "
                "so let the user know you can only answer general questions until "
                "they upload one."
            )

        prior_messages = [
            AIMessage(content=turn["content"])
            if turn.get("role") == "assistant"
            else HumanMessage(content=turn["content"])
            for turn in history[-MAX_HISTORY_TURNS:]
        ]

        messages = [
            SystemMessage(content=system_content),
            *prior_messages,
            HumanMessage(content=user_message),
        ]
        response = self.llm.invoke(messages)
        reply = get_text(response)

        return {
            "reply": reply,
            "sources": [
                {
                    "text": chunk["text"],
                    "score": chunk["score"],
                    "source": chunk["metadata"].get("source"),
                }
                for chunk in relevant_chunks
            ],
        }
