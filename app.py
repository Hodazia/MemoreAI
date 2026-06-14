
from fastapi import FastAPI, Request, HTTPException
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from agents import ask_agent
import os
import requests

from agents import ask_agent

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

app = FastAPI()


llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_KEY)
def get_ai_response(question):
    '''
    Get the response to the question by invoking the LLM
    '''

    response = llm.invoke([
        HumanMessage(content=question)
    ])

    return response.content


def send_whatsapp_message(
    recipient,
    message
):
    '''
    Send the whatsapp message , u have the recipient and the message as well
    '''
    url = (
        f"https://graph.facebook.com/v25.0/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {
            "body": message
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    print(response.json())

def extract_message(payload):

    try:
        message = (
            payload["entry"][0]
            ["changes"][0]
            ["value"]
            ["messages"][0]
        )

        sender = message["from"]
        text = message["text"]["body"]

        return sender, text

    except Exception:
        return None, None


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token == VERIFY_TOKEN
    ):
        return int(hub_challenge)

    raise HTTPException(status_code=403)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    print("POST webhook received! ")

    body = await request.json()

    print(body)
    sender, question = extract_message(body)

    print(sender)
    print(question)

    if not sender:
        return {"status":"ignored"}

    result = ask_agent(question)
    answer = result["answer"]

    tools_used = (
        result["tools_used"]
    )

    # answer = get_ai_response(question)

    tool_text = (
        ", ".join(tools_used)
        if tools_used
        else "None"
    )

    final_message = f"""
        Answer:

        {answer}

        -----------------

        Tools Used:

        {tool_text}
        """

    send_whatsapp_message(sender,final_message)
    return {"status": "ok"}