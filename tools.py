from langchain.tools import tool
from langchain_community.vectorstores import FAISS 
from langchain_community.embeddings import ( HuggingFaceBgeEmbeddings )
from datetime import date, datetime
import requests
import math 
import sympy as sp

embeddings = HuggingFaceBgeEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

db = FAISS.load_local(
    "bot_knowledge_db",
    embeddings,
    allow_dangerous_deserialization=True
)


@tool
def calculator(expression:str)-> str:
    '''
    Perform mathematical calculations.
    Example: 
    45*90
    sqrt(144)
    2**10

    '''

    allowed = {
        "sqrt": math.sqrt,
        "pow": pow,
        "abs": abs,
        "round": round,
    }

    try:
        result = eval(expression,
                    {"__builtins__": {}},
                    allowed)

        return str(result)

    except Exception as e:
        return str(e)

@tool
def solve_equation(equation: str) -> str:
    """
    Solve algebraic equations.

    Example:
    x**2 + 5*x + 6 = 0
    """

    try:

        x = sp.Symbol("x")

        left, right = equation.split("=")

        expr = (
            sp.sympify(left)
            - sp.sympify(right)
        )

        solution = sp.solve(
            expr,
            x
        )

        return str(solution)

    except Exception as e:
        return f"Error: {e}"


@tool
def solve_math_problem(problem: str) -> str:
    """
    Solve natural language math problems.

    Use this tool whenever the user provides
    a mathematical word problem.
    """

    return problem

@tool
def github_search(query: str) -> str:
    """
    Search GitHub repositories.
    """

    url = (
        "https://api.github.com/search/repositories"
        f"?q={query}"
    )
    # update the way of filtering through repo's
    response = requests.get(url)

    data = response.json()

    # only 5 repos are returned , it can be extended too!!
    repos = data.get("items", [])[:5]

    if not repos:
        return "No repositories found"

    output = []

    for repo in repos:

        output.append(
            f"""
            Name: {repo['full_name']}
            Stars: {repo['stargazers_count']}
            URL: {repo['html_url']}
            """
        )

    return "\n".join(output)


'''
this will return the current time of your device, not the user's device
'''
@tool
def current_time(query:str)-> str:
    '''
    Returns the current time,
    '''
    return "the current time is " +  str(datetime.now())

'''
built a simple sympy tool which can handle all kinds of mathematical tasks
'''
@tool
def sympy_math(query:str)->str:
    """
    Solve advanced mathematical problems.

    Supported formats:

    Arithmetic:
        calculate: 45*90

    Derivative:
        derivative: x**3 + 5*x

    Integral:
        integral: x**2

    Equation:
        solve: x**2 + 5*x + 6 = 0

    Limit:
        limit: sin(x)/x, x, 0

    Factor:
        factor: x**2 - 9

    Expand:
        expand: (x+3)*(x+5)
    """

    try:

        x = sp.Symbol("x")

        operation = operation.strip()

        # --------------------
        # Arithmetic
        # --------------------
        if operation.startswith("calculate:"):

            expr = operation.replace(
                "calculate:",
                ""
            ).strip()

            return str(
                sp.sympify(expr)
            )

        # --------------------
        # Derivative
        # --------------------
        elif operation.startswith(
            "derivative:"
        ):

            expr = operation.replace(
                "derivative:",
                ""
            ).strip()

            return str(
                sp.diff(
                    sp.sympify(expr),
                    x
                )
            )

        # --------------------
        # Integral
        # --------------------
        elif operation.startswith(
            "integral:"
        ):

            expr = operation.replace(
                "integral:",
                ""
            ).strip()

            return str(
                sp.integrate(
                    sp.sympify(expr),
                    x
                )
            )

        # --------------------
        # Equation Solving
        # --------------------
        elif operation.startswith(
            "solve:"
        ):

            equation = operation.replace(
                "solve:",
                ""
            ).strip()

            left, right = equation.split("=")

            expr = (
                sp.sympify(left)
                - sp.sympify(right)
            )

            result = sp.solve(
                expr,
                x
            )

            return str(result)

        # --------------------
        # Limit
        # --------------------
        elif operation.startswith(
            "limit:"
        ):

            args = operation.replace(
                "limit:",
                ""
            ).strip()

            expr, var, point = [
                a.strip()
                for a in args.split(",")
            ]

            symbol = sp.Symbol(var)

            return str(
                sp.limit(
                    sp.sympify(expr),
                    symbol,
                    sp.sympify(point)
                )
            )

        # --------------------
        # Factor
        # --------------------
        elif operation.startswith(
            "factor:"
        ):

            expr = operation.replace(
                "factor:",
                ""
            ).strip()

            return str(
                sp.factor(
                    sp.sympify(expr)
                )
            )

        # --------------------
        # Expand
        # --------------------
        elif operation.startswith(
            "expand:"
        ):

            expr = operation.replace(
                "expand:",
                ""
            ).strip()

            return str(
                sp.expand(
                    sp.sympify(expr)
                )
            )

        return (
            "Unsupported operation."
        )

    except Exception as e:

        return f"Error: {str(e)}"


@tool
def search_bot_knowledge(
    query: str
) -> str:
    """
    Search information about the assistant,
    its identity, capabilities, tools,
    features, personality, and version.
    """

    docs = db.similarity_search(
        query,
        k=3
    )

    # optional we can add a llm layer again here as well since this too is a mini-RAG only
    return "\n\n".join(
        [
            doc.page_content
            for doc in docs
        ]
    )