import os

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from config import (
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    LLM_PROVIDER,
    MODEL_ID,
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MAX_TOKENS,
    QWEN_MODEL,
    VLLM_BASE_URL,
)
from coffee_tools import COFFEE_TOOLS
from sync_tools import SYNC_TOOLS
from usb_sync import USB_TOOLS
from tools import TOOLS

SYSTEM_PROMPT = (
    "You are a local file and paperwork assistant. You can search the user's "
    "workspace for files, read documents (.txt/.md/.pdf/.docx/.xlsx/.xls) to "
    "summarize or answer questions about them, and draft new documents when "
    "asked. Always use search_files first if you don't already know the exact "
    "path of a file. Be concise and mention the file paths you used.\n\n"
    "You can also manage the user's coffee-can bean and brew-session tracker. "
    "When asked to register beans or brew sessions from a spreadsheet, CSV, or "
    "text file: read it with read_document, work out the fields yourself from "
    "its contents, then call create_coffee_bean / create_coffee_brew_session "
    "for each record. When given a photo (e.g. a bag label or a handwritten "
    "brew note), call extract_text_from_image to OCR it via the Claude API, "
    "then parse the fields out of that transcribed text the same way -- this "
    "needs ANTHROPIC_API_KEY set, so tell the user to set it if the tool "
    "reports it's missing. If the photo was of a bean's bag/label (not a "
    "brew note), also call add_coffee_bean_image with that same photo path "
    "against the bean you just created or updated, so the profile keeps the "
    "picture it was filled in from. OCR and file parsing are both best-effort "
    "-- briefly show what you extracted and check with the user "
    "before registering anything that looks incomplete or ambiguous. Use "
    "list_coffee_beans / list_coffee_brew_sessions to check for an existing "
    "profile before creating a duplicate.\n\n"
    "You can also sync coffee-can with the user's Android phone, through a "
    "bundle file they carry between the two devices themselves -- there is no "
    "server in this path, and you should never offer to upload anything. "
    "Both directions work, and if the phone is plugged in over USB you can "
    "do the whole transfer yourself -- prefer that over making the user "
    "carry a file. send_coffee_data_to_phone packages this machine's data, "
    "copies it across and tells the app to import it. "
    "fetch_coffee_data_from_phone does the reverse and leaves the bundle "
    "here for you to inspect_coffee_bundle -- it does NOT import it, so "
    "carry on with the conflict conversation below. If either reports no "
    "phone connected, fall back to export_coffee_bundle and tell the user "
    "to open the .zip on the phone from Profile -> 'Sync with desktop' -> "
    "'Receive from desktop'. Either way, say what "
    "the phone will do with it: it ADDS beans whose names are new and LEAVES "
    "ALONE any bean already on the phone -- it never overwrites, so an edit "
    "made here will not reach a bean the phone already has. Do not call it a "
    "backup, and do not tell the user it cannot be imported. "
    "To take a bundle the phone produced: ALWAYS call "
    "inspect_coffee_bundle first and show what it reports. "
    "If it names conflicts, ask the user about them one at a time "
    "-- for each, say which fields differ and which side has what -- and only "
    "then call apply_coffee_bundle with a resolutions JSON object mapping each "
    "conflicted bean name to 'phone', 'desktop' or 'skip'. Never guess a "
    "resolution or pass 'phone' wholesale: 'phone' deletes the local bean and "
    "everything hanging off it. Beans are matched by name, so mention that a "
    "bean renamed on one device will import as a second bean."
)


def build_llm() -> BaseChatModel:
    if LLM_PROVIDER == "anthropic":
        # Qwen (an OpenAI-compatible API) takes priority over Claude whenever
        # both QWEN_API_KEY and QWEN_MODEL are set -- this is not a third
        # LLM_PROVIDER value, just a swap-in replacement for the Claude call
        # within the "anthropic" branch. Unset either one to fall back to Claude.
        if QWEN_API_KEY and QWEN_MODEL:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=QWEN_MODEL,
                base_url=QWEN_BASE_URL,
                api_key=QWEN_API_KEY,
                max_tokens=QWEN_MAX_TOKENS,
            )

        # Imported lazily so the local-only setup doesn't need langchain-anthropic.
        from langchain_anthropic import ChatAnthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ValueError(
                "LLM_PROVIDER=anthropic but neither QWEN_API_KEY/QWEN_MODEL nor "
                "ANTHROPIC_API_KEY is set. Set one pair in .env or export it in "
                "your shell."
            )

        # No temperature/top_p here: Claude Opus 5 rejects sampling parameters.
        # Thinking is on by default; effort controls how much of it you pay for.
        return ChatAnthropic(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
        )

    if LLM_PROVIDER == "vllm":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=MODEL_ID,
            base_url=VLLM_BASE_URL,
            api_key="EMPTY",
            temperature=0.2,
        )

    raise ValueError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Use 'vllm' or 'anthropic'.")


def build_agent():
    return create_react_agent(build_llm(), TOOLS + COFFEE_TOOLS + SYNC_TOOLS + USB_TOOLS, prompt=SYSTEM_PROMPT)