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
    search_bot_knowledge
)

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_KEY")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_KEY
)

tools = [
    calculator,
    github_search,
    current_time,
    solve_equation,
    solve_math_problem,
    sympy_math,
    search_bot_knowledge
]

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

def ask_agent(question: str):

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