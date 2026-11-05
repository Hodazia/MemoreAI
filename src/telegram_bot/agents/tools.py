from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime
from langchain_tavily import TavilySearch
from telegram_bot.services.knowledge_service import (
    search_user_knowledge,
)

import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlparse
from tavily import TavilyClient

from telegram_bot.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

#
@dataclass
class AgentContext:
    user_id: int

def _get_tavily_client() -> TavilyClient:
    if not settings.tavily_api_key:
        raise RuntimeError(
            "Web research is not configured. "
            "Set tavily API KEY in the environment"
        )
    return TavilyClient(api_key=settings.tavily_api_key)


def _validate_public_url(url:str) -> str:
    '''
    basic URL Validation for URL's supplied to extraction/mapping tools.

    This rejects non-HTTP schemes and obvious localhost/private IP
    targets. It is not a complete defense against DNS rebinding.    
    '''

    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http","https"}:
        raise ValueError("Only HTTP and HTTPS urls are allowed")

    if not parsed.hostname:
        raise ValueError("A valid URL hostname is required. ")

    hostname = parsed.hostname.lower()

    if hostname in {"localhost","localhost.localdomain"}:
        raise ValueError("LocalHost URL's are not allowed.")

    try:
        address = ipaddress.ip_address(hostname)
        if not address.is_global:
            raise ValueError(
                "Private, loopback, and reserved IP addresses "
                "are not allowed."
            )
    except ValueError as exc:
        # Preserve our own validation errors. A non-IP hostname
        # is expected and will be checked by the external service.
        if "not allowed" in str(exc):
            raise

    return url.strip()


async def _run_sync(func, *args, **kwargs):
    """
    TavilyClient is synchronous. Run its network operations in a
    worker thread so the asyncio event loop is not blocked.
    """
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_search_results(response: dict) -> str:
    results = response.get("results", [])

    if not results:
        return "No relevant web results were found."

    lines = []

    for index, result in enumerate(results, start=1):
        lines.append(
            f"Result {index}\n"
            f"Title: {result.get('title', 'Untitled')}\n"
            f"URL: {result.get('url', '')}\n"
            f"Score: {result.get('score', 'unknown')}\n"
            f"Content: {result.get('content', '')[:2500]}"
        )

    return "\n\n".join(lines)




def build_agent_tools(user_id: int):
    '''
    build the tools available to the current authenticated user.

    user-specific:
        - search_my_documents

    shared
        - search_web
    Every document search is scoped to the authenticated user.
    Web search is shared because it searches public internet data.
    
    '''
    tools = []

    @tool
    async def search_my_documents(query: str) -> str:
        """Search the authenticated user's uploaded documents
        for information relevant to a question.
        Use this tool when the user asks about:
        - Their uploaded files.
        - Their personal knowledge base.
        - Information contained in their documents.
        - Previously uploaded research or reports.

        This tool searches only the authenticated user's data.

        """
        results = await search_user_knowledge(
            user_id=user_id,
            query=query,
            k=4,
        )

        if not results:
            return "No relevant information was found in your documents."

        formatted_results = []

        for index, doc in enumerate(results, start=1):
            source = doc.metadata.get(
                "source",
                doc.metadata.get("filename", "Unknown document"),
            )

            formatted_results.append(
                f"Document result {index}\n"
                f"Source: {source}\n"
                f"Content: {doc.page_content}"
            )

        return "\n\n".join(formatted_results)

    tools.append(search_my_documents)

    # --------------------------------------------------
    # 2. Public internet search using Tavily
    # --------------------------------------------------
    if not settings.tavily_api_key:
        return tools

    #Reuse one client for this set of tools.
    client = _get_tavily_client()

    @tool
    async def search_web(
        query: str,
        topic: str = "general",
        search_depth: str = "advanced",
    ) -> str:
        """Search current public web information.

        Use for current events, recent AI developments, current
        software documentation, versions, product information,
        regulations, and facts that may have changed.

        topic must be general or news.
        search_depth must be basic or advanced.
        Include source URLs in the final response.
        """

        if topic not in {"general", "news"}:
            return "Invalid topic. Use general or news."

        if search_depth not in {"basic", "advanced"}:
            return "Invalid search depth. Use basic or advanced."

        response = await _run_sync(
            client.search,
            query=query,
            topic=topic,
            search_depth=search_depth,
            max_results=max(1, min(settings.tavily_max_results, 10)),
        )

        return _format_search_results(response)

    tools.append(search_web)

    # --------------------------------------------------
    # 3. Extract content from explicit URLs
    # --------------------------------------------------

    @tool
    async def extract_url(urls: list[str]) -> str:
        """Extract readable content from one or more specific URLs.

        Use after web search when the answer requires more detail
        than a search snippet. Supply HTTP/HTTPS URLs only.
        Provide no more than 5 URLs per call.
        """

        if not urls or len(urls) > 5:
            return "Provide between 1 and 5 URLs."

        try:
            validated_urls = [
                _validate_public_url(url)
                for url in urls
            ]
        except ValueError as exc:
            return f"URL validation failed: {exc}"

        response = await _run_sync(
            client.extract,
            urls=validated_urls,
            extract_depth="basic",
        )

        results = response.get("results", [])
        failed = response.get("failed_results", [])

        sections = []

        for result in results:
            sections.append(
                f"URL: {result.get('url', '')}\n"
                f"Content:\n"
                f"{(result.get('raw_content') or '')[:6000]}"
            )

        if failed:
            sections.append(
                "Some URLs could not be extracted:\n"
                + "\n".join(
                    f"- {item.get('url')}: {item.get('error', 'Unknown error')}"
                    for item in failed
                )
            )

        return "\n\n".join(sections) or "No page content could be extracted."

    tools.append(extract_url)

    # --------------------------------------------------
    # 4. Map a website
    # --------------------------------------------------

    @tool
    async def map_website(url: str, limit: int = 20) -> str:
        """Discover URLs inside a website.

        Use when the user wants to explore a documentation site,
        find relevant sections, or plan a knowledge-base ingestion.
        This returns URLs; it does not extract full page contents.
        """

        try:
            validated_url = _validate_public_url(url)
        except ValueError as exc:
            return f"URL validation failed: {exc}"

        limit = max(1, min(limit, 50))

        response = await _run_sync(
            client.map,
            url=validated_url,
            max_depth=2,
            limit=limit,
        )

        urls = response.get("results", [])

        if not urls:
            return "No site URLs were discovered."

        return "Discovered website URLs:\n" + "\n".join(
            f"- {item}" for item in urls
        )

    tools.append(map_website)

    # --------------------------------------------------
    # 5. Crawl a website (requires Tavily access)
    # --------------------------------------------------

    @tool
    async def crawl_website(
        url: str,
        instructions: str,
        limit: int = 10,
    ) -> str:
        """Traverse a website and extract content from multiple pages.

        Use only for a focused website-ingestion or documentation
        exploration task. Tavily Crawl may require account approval.
        Limit the number of pages to avoid excessive results.
        """

        try:
            validated_url = _validate_public_url(url)
        except ValueError as exc:
            return f"URL validation failed: {exc}"

        limit = max(1, min(limit, 20))

        try:
            response = await _run_sync(
                client.crawl,
                url=validated_url,
                max_depth=2,
                limit=limit,
                instructions=instructions[:1000],
            )
        except Exception:
            logger.exception("Tavily crawl failed")
            return (
                "Website crawling failed. Check whether Crawl is "
                "enabled for your Tavily account and inspect the "
                "application logs."
            )

        results = response.get("results", [])

        if not results:
            return "The crawl returned no pages."

        return "\n\n".join(
            f"URL: {item.get('url', '')}\n"
            f"Content: {(item.get('raw_content') or '')[:3000]}"
            for item in results
        )

    tools.append(crawl_website)

    # --------------------------------------------------
    # 6. Multi-source research - this tool consumes a lot of API Credits, we can choose not to activate this also

    @tool
    async def research_topic(topic: str) -> str:
        """Create an in-depth research report on a topic using
        Tavily Research.

        Use for broad research, technology comparisons, market
        research, and comprehensive reports that need multiple
        sources. This is slower than ordinary web search.
        """

        if len(topic.strip()) < 5:
            return "Please provide a more specific research topic."

        try:
            # Start the research task.
            started = await _run_sync(
                client.research,
                input=topic[:4000],
                model=settings.tavily_research_model,
                citation_format="apa",
            )

            request_id = started.get("request_id")

            if not request_id:
                return "Tavily did not return a research request ID."

            # Poll for a bounded period. Research can take longer
            # than a normal search request.
            deadline = time.monotonic() + 90
            result = None

            while time.monotonic() < deadline:
                result = await _run_sync(
                    client.get_research,
                    request_id,
                )

                status = result.get("status", "").lower()

                if status in {"completed", "complete", "success"}:
                    break

                if status in {"failed", "error", "cancelled"}:
                    return (
                        "The research task did not complete. "
                        f"Status: {status}"
                    )

                await asyncio.sleep(3)

            else:
                return (
                    "Research is taking longer than the interactive "
                    "request window. Request ID: "
                    f"{request_id}. Run long research through a "
                    "background Celery task."
                )

            content = result.get("content", "")
            sources = result.get("sources", [])

            source_lines = []

            for source in sources[:20]:
                if isinstance(source, dict):
                    title = source.get("title", "Source")
                    url = source.get("url", "")
                    source_lines.append(f"- {title}: {url}")
                else:
                    source_lines.append(f"- {source}")

            return (
                f"Research report:\n{content[:12000]}\n\n"
                "Sources:\n"
                + ("\n".join(source_lines) if source_lines else "No source list returned.")
            )

        except Exception:
            logger.exception("Tavily research failed")
            return (
                "The research operation failed. Check the application "
                "logs and Tavily account configuration."
            )

    tools.append(research_topic)

    return tools


# Backward compatibility for existing imports.
def build_document_tools(user_id: int):
    return build_agent_tools(user_id=user_id)