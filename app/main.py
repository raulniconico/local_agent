import os

from rich.console import Console
from rich.markdown import Markdown

from .config import ANTHROPIC_MODEL, LLM_PROVIDER, VLLM_BASE_URL
from .graph import build_agent

console = Console()


def explain(exc: Exception) -> str:
    """Turn an SDK exception into one actionable line.

    Matches on class name rather than importing both SDKs, so this stays
    provider-agnostic.
    """
    name = type(exc).__name__

    if name == "APIConnectionError" or isinstance(exc, ConnectionError):
        if LLM_PROVIDER == "vllm":
            return (
                f"Can't reach the vLLM server at {VLLM_BASE_URL}.\n"
                "Start it in another terminal with ./serve_vllm.sh (give it a minute "
                "to load weights), or switch to LLM_PROVIDER=anthropic in .env."
            )
        return "Can't reach the Claude API — check your network connection."
    if name == "AuthenticationError":
        return "Anthropic rejected the API key. Check ANTHROPIC_API_KEY in .env."
    if name == "NotFoundError":
        return f"Model '{ANTHROPIC_MODEL}' not found. Check ANTHROPIC_MODEL in .env."
    if name == "RateLimitError":
        return "Rate limited by the Anthropic API. Wait a moment and retry."
    if name == "BadRequestError":
        return f"The API rejected the request: {exc}"

    return f"{name}: {exc}"


def main() -> None:
    try:
        agent = build_agent()
    except ValueError as exc:  # misconfiguration — no point entering the loop
        console.print(f"[bold red]Configuration error:[/] {exc}")
        raise SystemExit(1) from None

    backend = "Claude API" if LLM_PROVIDER == "anthropic" else "local vLLM"
    console.print(
        f"[bold green]File & paperwork agent[/] ([dim]{backend}[/]) — type 'exit' to quit.\n"
    )

    history: list[tuple[str, str]] = []
    while True:
        try:
            user_input = console.input("[bold cyan]you>[/] ")
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.strip().lower() in {"exit", "quit"}:
            break

        history.append(("user", user_input))
        try:
            result = agent.invoke({"messages": history})
        except Exception as exc:
            if os.environ.get("AGENT_DEBUG"):
                raise
            # Drop the unanswered turn so the next request isn't malformed.
            history.pop()
            console.print(f"[bold red]Error:[/] {explain(exc)}")
            console.print("[dim]Set AGENT_DEBUG=1 for the full traceback.[/]\n")
            continue

        reply = result["messages"][-1]
        # .content is a plain string on some backends but a list of content
        # blocks on Claude (thinking + text). .text normalizes both to a string.
        text = str(reply.text)
        history.append(("assistant", text))
        if text.strip():
            console.print(Markdown(text))
        else:
            console.print("[dim](the model returned no text)[/]")


if __name__ == "__main__":
    main()