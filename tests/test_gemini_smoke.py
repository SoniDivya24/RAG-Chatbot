"""Smoke test: confirms GOOGLE_API_KEY + langchain-google-genai actually work
end-to-end against the live Gemini API. Not a unit test (makes a real network
call) - run manually while verifying setup, per docs/phases.md Phase 1.
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from app import config


def test_gemini_chat_call_succeeds():
    config.require("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0)

    response = llm.invoke("What is 2+2? Reply with just the number.")
    content = response.content
    text = (
        content
        if isinstance(content, str)
        else "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    )

    # Not asserting exact wording - models phrase things differently even at
    # temperature=0. The point of this smoke test is proving the API key and
    # package work end-to-end, so just check we got a real, on-topic reply.
    assert "4" in text
