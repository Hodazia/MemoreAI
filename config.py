from dotenv import load_dotenv
import os
load_dotenv()

DATABASE_URL = os.getenv("DB_URL")
OPENAI_KEY = os.getenv("OPENAI_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")