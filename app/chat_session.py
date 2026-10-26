from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app import config
from app.rag_engine import RagEngine

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
    into a single LLM call. Deliberately stateless - the caller passes in
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
            self._llm = ChatGoogleGenerativeAI(
                model=config.CHAT_MODEL,
                temperature=self.rag_engine.profile.temperature,
                timeout=config.LLM_TIMEOUT,
            )
        return self._llm

    def ask(self, user_message: str, history: list[dict] | None = None) -> dict:
        history = history or []
        profile = self.rag_engine.profile
        has_documents = self.rag_engine.has_documents()
        if has_documents:
            canned = profile.precheck(user_message, self.rag_engine.store)
            if canned:
                return {"reply": canned, "sources": []}
        relevant_chunks = self.rag_engine.retrieve(user_message) if has_documents else []

        sources: list[dict] = []
        context = ""
        if relevant_chunks:
            # The mode's profile decides how hits become context and sources, and
            # which grounding instructions frame them.
            context, sources = profile.build_context(relevant_chunks, self.rag_engine.store)
            system_content = f"{profile.grounded_instructions}\n\nCONTEXT:\n{context}"
        elif has_documents:
            # Documents exist, but nothing relevant enough to this specific
            # message was found (retrieve() already filtered out low-score
            # matches). An empty CONTEXT block alone isn't a strong enough
            # signal - without this explicit branch the model tends to fall
            # back to its own general knowledge instead of declining, even
            # more so for well-known facts (e.g. capital cities). A soft
            # "say you don't know" instruction wasn't reliable across
            # repeated tries, and an unconditional forced refusal wrongly
            # declined plain greetings/small talk too - so this branch first
            # tells the model to tell those apart, and only forces the exact
            # refusal for genuine factual questions.
            system_content = (
                "The uploaded documents do not contain anything relevant to this "
                "message.\n\n"
                "First, decide: is this small talk / a greeting / a meta question "
                "about the conversation itself (e.g. \"hi\", \"thanks\", \"what can "
                "you do?\")? If so, just respond naturally and briefly - do not "
                "mention the documents.\n\n"
                "Otherwise, this is a real question you're expected to answer from "
                "the documents, and you have no relevant content for it. You MUST "
                "NOT use your own general knowledge to answer it, no matter how "
                "simple, common, or well-known the answer might seem (this applies "
                "even to basic facts like geography or dates). Reply with only this "
                "sentence, with no additions: "
                f"\"{profile.refusal}\""
            )
        else:
            # Deliberately no instruction to mention the lack of documents:
            # that produced a "reminder" disclaimer on every single reply,
            # including plain greetings. Capability explanation lives in the
            # UI's help dialog instead; only bring it up if actually asked.
            system_content = (
                "You are a helpful, concise assistant. If the user asks something "
                "that would require looking at an uploaded document and none has "
                "been uploaded yet, let them know - otherwise just answer normally."
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

        if profile.drop_sources_on_refusal and reply.strip().startswith(profile.refusal):
            sources = []  # the passages didn't inform a refusal, so don't present them as sources

        return {"reply": reply, "sources": sources, "contextTokens": len(context) // 4 + 1 if context else 0}
