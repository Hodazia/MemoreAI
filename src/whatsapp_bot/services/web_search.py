'''
Here i have defined a web search service, which will be used as a tool call
by the agent

'''
import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

client = TavilyClient(
    api_key=TAVILY_API_KEY
)

def search_web(
    query:str,
    max_results:int=7
):
    '''
    Search the web for current information

    '''
    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
            include_raw_content=False
        )

        results = []

        for item in response.get("results", []):

            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content")
            })

        return {
            "query": query,
            "answer": response.get("answer"),
            "results": results
        }

    except Exception as e:
        return {
            "error": str(e)
        }