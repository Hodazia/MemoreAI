'''

i am using gpt-4o-mini for now, but can switch to other models,
so we store that in .env or .env.example as to how much the cost is fro 1M tokens


'''

from decimal import Decimal, ROUND_HALF_UP
from telegram_bot.core.config import get_settings
from dotenv import load_dotenv

load_dotenv()

settings = get_settings()

#USD per 1 million tokens,
MODEL_PRICING:dict[str, dict[str,Decimal]] = {
    "gpt-4o-mini":{
        "input": settings.llm_input_cost,
        "output": settings.llm_output_cost,
    },
}

def estimate_cost_usd(
    model_name:str | None,
    input_tokens:int | None,
    output_tokens: int |None
) -> float: 
    if not model_name:
        return None
    

    if input_tokens is None or output_tokens is None:
        return None

    rates = MODEL_PRICING.get(model_name)

    #we return None for unknown models or missing usage
    if rates is None:
        return None

    input_cost = (
        Decimal(input_tokens)
        * rates["input"]
        / Decimal("1000000")
    )

    output_cost = (
        Decimal(output_tokens)
        * rates["output"]
        / Decimal("1000000")
    )

    total = (input_cost + output_cost).quantize(
        Decimal("0.00000001"),
        rounding=ROUND_HALF_UP,
    )

    return float(total)