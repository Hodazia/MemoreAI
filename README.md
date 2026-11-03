## Telegram AI Assistant  

A multi-user Telegram AI Assitant built with Python, FastAPI, LangChain, OpenAI, PostgreSQL, SQLAlchemy  
and Pinecone. it combines general-purpose chat, document-based Retrieval-Augmented Generation (RAG) , user-controlled  
persistent memory, scheduled workflows, and AI observability. 


## Features
#### General-purpose AI Assistant  
- Answers general questions using the configured chat model
- Uses langchain create_agent() to orchestrate the models and tools  
- Passes conversation history and relevant user-approved memories into the agent  
- Builds user-specific tools at invocation time, so document retrieval is scoped to the active user.    
  
#### Document Upload and RAG  
- Receives documents through Telegram  
- Extracts text, splits it into chunks, generates embeddings, and stores vectors in Pinecone.  
- Retrieves relevant chunks to ground answers in a user's uploaded knowledge  
- Stores document metadata and ingestion status in postgreSQL    

#### Persistent user-controlled memory  
- /remember -> saves information explicitly selected by the user.  
- /memory -> list saved memories  
- /memory_edit -> edits a memory  
- /forget <id> -> deletes a selected memory
- /forget all -> starts a confirmation flow to delete all memories
- /forget_confirm -> confirms deletion of all users.
- /forget_cancel -> cancels the pending deletion  

#### Scheduled workflows  
Users can create scheduled workflows with a name, prompt, schedule time, timezone and delivery preferences such  
as Telegram and email. The API validates that at least one delivery channel is enabled and that an email address exists   
when email delivery is selected.  

#### AI Observability  
The observability layer instruments calls made by this application and can record: - Agent traces and status.  
LLM call counts, input/output tokens when provider usage is returned, estimated model/API cost  
Request and model-call latency, failures and error details

#### Tech stack
- Python
- FastAPI and Uvicorn
- Telegram Bot API / python-telegram-bot 
- LangChain and langchain-openai
- OpenAI chat and embedding APIs
- SQLAlchemy async
- PostgreSQL (Neon can be used)
- Pinecone  
  
Prerequisites
1. Python version supported by the project dependencies.
2. PostgreSQL database (local PostgreSQL or Neon).
3. Telegram bot token from BotFather.
4. OpenAI API key.
5. Pinecone account, API key, and index if RAG is enabled.
6. Git.
7. An HTTPS URL for Telegram webhook mode. For local development, a
   tunnel such as ngrok or Cloudflare Tunnel can expose the local
   server.

Local setup
1. Clone the repository
```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_PROJECT_DIRECTORY>
```
Replace the placeholders with your repository URL and directory.  

2. Create a virtual environment
macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
Windows PowerShell:
```bash
py -m venv .venv
.venv\Scripts\Activate.ps1
```  

3. Install dependencies
If the project has requirements.txt:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
If it uses pyproject.toml and a lockfile, use the package manager and
lockfile committed by the project instead.  

4. Configure environment
```bash
cp .env.example .env
```
If there is no .env.example, create .env using the variables
expected by telegram_bot/core/config.py. See
Configuration.  

5. Configure PostgreSQL
An async SQLAlchemy URL commonly looks like:
```bash
postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```
Use the exact URL scheme expected by the project's database engine. For
Neon, copy the connection details from the Neon dashboard and follow its
SSL requirements.
Configuration
telegram_bot/core/config.py and get_settings() are the source of
truth. These are representative variable names based on the
implementation discussed; adjust them to match the actual settings
class.

#### Run locally
The following import path is an example. Replace it with the module
containing your actual FastAPI app instance:  
```bash
uvicorn telegram_bot.main:app --reload --host 0.0.0.0 --port 8000  
ngrok http 8000   
docker run -d --name redis-telegram -p 6379:6379 redis  

```




