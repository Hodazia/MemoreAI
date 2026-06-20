from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_classic.agents import (
    create_tool_calling_agent,
    AgentExecutor
)
import os
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from tools import (
    calculator,
    github_search,
    current_time,
    solve_equation,
    solve_math_problem,
    sympy_math,
    web_search_content,
    search_bot_knowledge
)
from TOOLS.document_search_tool import (
    create_document_search_tool
)

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_KEY")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_KEY
)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a helpful AI assistant.

            TOOL RULES:

            1. Use calculator for arithmetic.

            Examples:
            - 45 * 90
            - 100 / 4
            - sqrt(144)

            2. Use sympy_math for:

            - algebra
            - equations
            - calculus
            - derivatives
            - integrals
            - limits
            - factorization

            3. Use github_search whenever
            the user asks about:

            - GitHub repositories
            - open source projects
            - source code projects

            4. Use search_bot_knowledge whenever
            the user asks about:

            - who are you
            - tell me about yourself
            - what can you do
            - your capabilities
            - your features
            - your tools
            - your version
            - how you work

            5.use web_search_content
            - Searches the internet for current information.
            - Use when the question depends on recent events, current affairs, live information, product releases, 
            company updates, technology news, market news, or information that may have changed recently.

            Always use web_search_content for requests such as:

            - Search for ...
            - Look up ...
            - Find information about ...
            - What's happening with ...
            - Latest news about ...
            - Recent developments in ...
            - Current state of ...
            - Today's updates on ...
            - What happened recently ...
            - Trending topics related to ...

            After receiving web_search_tool results:

            - Read all returned search results.
            - Use the answer field as a quick summary.
            - Validate information using the search results.
            - Summarize findings clearly.
            - Cite source URLs when relevant.
            - Do not dump raw JSON unless explicitly requested.



            6. Use search_documents whenever:

            - user asks about a document
            - user asks about a file they uploaded
            - user asks questions that may require information from uploaded files

            Examples:

            - summarize my document
            - what is written in the pdf
            - explain the contract
            - what does my resume say
            - tell me about the uploaded file

            Always use search_documents before answering document-related questions.

            IMPORTANT:

            After using search_bot_knowledge,
            answer in a friendly assistant style.
            Use emojis where appropriate.

            If no tool is needed,
            answer directly using your own knowledge.
            """
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ]
)

def ask_agent(question: str,sender:str):
    document_tool = (create_document_search_tool(sender))

    tools = [
        calculator,
        github_search,
        current_time,
        solve_equation,
        solve_math_problem,
        sympy_math,
        web_search_content,
        search_bot_knowledge,
        document_tool
    ]

    agent = create_tool_calling_agent(
        llm,
        tools,
        prompt
    )

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True
    )

    response = agent_executor.invoke(
        {
            "input": question
        }
    )

    answer = response["output"]

    tools_used = []

    for step in response["intermediate_steps"]:

        action, observation = step

        tools_used.append(
            action.tool
        )

    return {
        "answer": answer,
        "tools_used": list(
            set(tools_used)
        )
    }