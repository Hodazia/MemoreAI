import logging
from pathlib import Path
from uuid import uuid4

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError



from telegram_bot.agents.agent import ask_agent
from sqlalchemy.ext.asyncio import AsyncSession

from telegram.ext import ConversationHandler
from telegram_bot.core.database import AsyncSessionLocal
from telegram_bot.services.auth_service import (
    create_telegram_session,
    get_telegram_session,
    authenticate_user,
    register_user,
    logout_telegram_user,
)
from telegram_bot.services.conversation_service import (
    get_or_create_conversation,
    get_conversation_messages,
    save_message,
)
from telegram_bot.models.document import Document
from telegram_bot.models.user import User
from telegram_bot.models.workflow import Workflow
from telegram_bot.models.workflow_runs import WorkflowRun
from telegram_bot.tasks.workflows import next_daily_run , execute_workflow
from telegram_bot.schemas.workflow import WorkflowCreateRequest,WorkflowResponse
from telegram_bot.services.document_upload_service import save_and_index_document, MAX_FILE_SIZE
from telegram_bot.services.document_service import SUPPORTED_EXTENSIONS



logger = logging.getLogger(__name__)
REGISTER_USERNAME = 1
REGISTER_PASSWORD = 2

LOGIN_USERNAME = 3
LOGIN_PASSWORD = 4


WORKFLOW_NAME = 5
WORKFLOW_PROMPT = 6
WORKFLOW_TIME = 7
WORKFLOW_TIMEZONE = 8
WORKFLOW_CHANNELS = 9


async def get_logged_in_user(
    telegram_user_id: int,
):

    async with AsyncSessionLocal() as db:

        session = await get_telegram_session(
            db,
            telegram_user_id,
        )

        if not session:
            return None

        return session.user_id

async def start_handler(
    update,
    context,
):

    telegram_user_id = update.effective_user.id

    user_id = await get_logged_in_user(
        telegram_user_id
    )

    if user_id:

        await update.message.reply_text(
            "👋 Welcome back!\n\n"
            "You are currently logged in.\n\n"
            "Ask me anything and I'll help you.\n\n"
            "Commands:\n"
            "/help - Show commands\n"
            "/logout - Logout"
        )

        return

    await update.message.reply_text(
        "👋 Welcome to the AI Agent!\n\n"

        "I can:\n"
        "🤖 Answer your questions\n"
        "💬 Maintain your conversation history\n"
        "🧠 Remember previous messages in your account\n\n"

        "To get started:\n\n"
        "/register - Create an account\n"
        "/login - Login to your account\n"
        "/help - Show available commands"
    )

async def help_handler(
    update,
    context,
):

    await update.message.reply_text(
        "🤖 AI Agent Commands\n\n"

        "/start\n"
        "Start the bot and see available options.\n\n"

        "/register\n"
        "Create a new account.\n\n"

        "/login\n"
        "Login to your account.\n\n"

        "/logout\n"
        "Logout from your account.\n\n"

        "/documents\n"
        "List the user's uploaded documents.\n\n"

        "/memory\n"
        "View saved long term memories\n\n"

        "/workflow_create\n"
        "Create a daily scheduled AI workflow.\n\n"

        "/workflows\n"
        "List all your scheduled workflows.\n\n"

        "/workflow_enable <id>\n"
        "Enable a workflow.\n\n"

        "/workflow_disable <id>\n"
        "Disable a workflow.\n\n"

        "/workflow_run <id>\n"
        "Execute a workflow immediately.\n\n"

        "/cancel\n"
        "Cancel the current workflow creation process.\n\n"

        "/logout\n"
        "Logout from your account.\n\n"

        "/ai_help\n"
        "List the AI Observability commands.\n\n"

        "After logging in, simply send me "
        "a message to start chatting."
    )

async def register_start(
    update,
    context,
):

    await update.message.reply_text(
        "Let's create your account.\n\n"
        "Please enter your username:"
    )

    return REGISTER_USERNAME

async def register_username(
    update,
    context,
):

    username = update.message.text.strip()

    context.user_data["register_username"] = username

    await update.message.reply_text(
        "Great.\n\n"
        "Now enter your password:"
    )

    return REGISTER_PASSWORD

async def register_password(
    update,
    context,
):

    password = update.message.text

    username = context.user_data.get(
        "register_username"
    )

    async with AsyncSessionLocal() as db:

        try:

            await register_user(
                db,
                username,
                password,
            )

        except ValueError:

            await update.message.reply_text(
                "That username already exists.\n\n"
                "Please use /register again."
            )

            context.user_data.clear()

            return -1

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Registration successful!\n\n"
        "Your account has been created.\n"
        "Now use /login to authenticate."
    )

    return -1

async def login_start(
    update,
    context,
):

    await update.message.reply_text(
        "Please enter your username:"
    )

    return LOGIN_USERNAME

async def login_username(
    update,
    context,
):

    context.user_data["login_username"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        "Now enter your password:"
    )

    return LOGIN_PASSWORD

async def login_password(
    update,
    context,
):

    username = context.user_data.get(
        "login_username"
    )

    password = update.message.text

    telegram_user_id = update.effective_user.id

    async with AsyncSessionLocal() as db:

        user = await authenticate_user(
            db,
            username,
            password,
        )

        if not user:

            await update.message.reply_text(
                "❌ Invalid username or password.\n\n"
                "Please try /login again."
            )

            context.user_data.clear()

            return -1

        await create_telegram_session(
            db,
            telegram_user_id,
            user.id,
        )

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ Welcome back, {user.username}!\n\n"
        "You are now logged in.\n\n"
        "Your conversations will now be "
        "associated with your account."
    )

    return -1

async def logout_handler(
    update,
    context,
):

    telegram_user_id = update.effective_user.id

    async with AsyncSessionLocal() as db:

        await logout_telegram_user(
            db,
            telegram_user_id,
        )

    await update.message.reply_text(
        "You have been logged out."
    )


# async def message_handler(
#     update,
#     context,
# ):

#     if update.message is None:
#         return

#     telegram_user_id = update.effective_user.id

#     user_id = await get_logged_in_user(
#         telegram_user_id
#     )

#     if user_id is None:

#         await update.message.reply_text(
#             "🔐 You are not logged in.\n\n"
#             "Please use /register to create an "
#             "account, or /login if you already "
#             "have one."
#         )

#         return

#     user_message = update.message.text

#     await update.message.chat.send_action(
#         "typing"
#     )

#     async with AsyncSessionLocal() as db:

#         conversation = await get_or_create_conversation(
#             db,
#             user_id,
#         )

#         history = await get_conversation_messages(
#             db,
#             conversation.id,
#             limit=20,
#         )

#         await save_message(
#             db,
#             conversation.id,
#             "user",
#             user_message,
#         )

#         messages = [
#             {
#                 "role": message.role,
#                 "content": message.content,
#             }
#             for message in history
#         ]

#         messages.append(
#             {
#                 "role": "user",
#                 "content": user_message,
#             }
#         )

#         response = await ask_agent(
#             messages
#         )

#         await save_message(
#             db,
#             conversation.id,
#             "assistant",
#             response,
#         )

#     await update.message.reply_text(
#         response
#     )


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message  = update.effective_message
    telegram_user = update.effective_user # this return the current telegram user which sends the message now

    if message is None or telegram_user is None:
        return

    user_text = message.text  # extract the text field from the message 

    if not user_text or not user_text.strip():
        await message.reply_text(
            "Please send a text message."
        )
        return

    telegram_user_id = telegram_user.id  # get the id from the telegram_user to authenticate it

    await message.chat.send_action("typing")
    #user_text = update.message.text

    async with AsyncSessionLocal() as db:

        # --------------------------------
        # 1. Check Telegram authentication
        # --------------------------------

        session = await get_telegram_session(
            db,
            telegram_user_id,
        )

        if not session:
            await update.message.reply_text(
                "You are not logged in. "
                "Please use /login first."
            )

            return

        user_id = session.user_id

        # --------------------------------
        # 2. Get/create user's conversation
        # --------------------------------

        conversation = await get_or_create_conversation(
            db,
            user_id=session.user_id,
        )

        # --------------------------------
        # 3. Load previous conversation
        # --------------------------------

        history = await get_conversation_messages(
            db,
            conversation.id,
            limit=20,
        )

        # --------------------------------
        # 4. Convert DB Message objects into Langchain-compatible (role,content) tuples
        # --------------------------------

        langchain_messages = [
            (item.role, item.content) for item in history if item.role in ["user", "assistant"]
        ]

        # append the current message exactly once
        langchain_messages.append(("user", user_text))

        #persist the incoming message
        await save_message(
            db,
            conversation.id,
            role="user",
            content=user_text,
        )

        await db.commit()

    # 8. Invoke the agent after releasing the DB session.
    try:
        response = await ask_agent(
            messages=langchain_messages,
            user_id=user_id,
        )

    except Exception:
        logger.exception(
            "Agent invocation failed for user_id=%s",
            user_id,
        )

        await message.reply_text(
            "Sorry, I couldn't process your message. "
            "Please try again."
        )
        return

    # 9. Persist the agent's response.
    async with AsyncSessionLocal() as db:
        conversation = await get_or_create_conversation(
            db,
            user_id=user_id,
        )

        await save_message(
            db,
            conversation.id,
            role="assistant",
            content=response,
        )

        await db.commit()

    # 10. Send the response to Telegram.
    await message.reply_text(response)

        # --------------------------------
        # 5. Ask LangChain agent
        # --------------------------------

        # response = await ask_agent(
        #     messages=history + [
        #         {
        #             "role": "user",
        #             "content": user_text,
        #         }
        #     ],
        #     user_id=session.user_id,
        # )

        # # --------------------------------
        # # 6. Save AI response
        # # --------------------------------

        # await save_message(
        #     db,
        #     conversation.id,
        #     role="assistant",
        #     content=response,
        # )

        # # --------------------------------
        # # 7. Send response to Telegram
        # # --------------------------------

        # await update.message.reply_text(
        #     response
        # )


async def document_upload_handler(
    update:Update,
    context:ContextTypes.DEFAULT_TYPE
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or message.document is None:
        return

    tg_document = message.document
    filename = tg_document.file_name or "uploaded_file"
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        await message.reply_text(
            "Unsupported format. Please upload PDF, DOCX, or TXT."
        )
        return

    if tg_document.file_size and tg_document.file_size > MAX_FILE_SIZE:
        await message.reply_text("The maximum file size is 10 MB.")
        return

    temporary_path = Path("uploads") / f"tmp-{uuid4().hex}{extension}"
    temporary_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with AsyncSessionLocal() as db:
            session = await get_telegram_session(
                db,
                telegram_user.id,
            )

            if not session:
                await message.reply_text(
                    "Please /login before uploading documents."
                )
                return

            telegram_file = await context.bot.get_file(
                tg_document.file_id
            )

            await telegram_file.download_to_drive(
                custom_path=str(temporary_path)
            )

            document, result = await save_and_index_document(
                db,
                user_id=session.user_id,
                original_filename=filename,
                file_size=tg_document.file_size or temporary_path.stat().st_size,
                downloaded_path=str(temporary_path),
            )

        await message.reply_text(
            f"✅ Document indexed successfully!\n\n"
            f"Name: {document.original_filename}\n"
            f"Document ID: {document.id}\n"
            f"Chunks indexed: {result['chunks_created']}\n\n"
            f"You can now ask me questions about its contents."
        )

    except ValueError as exc:
        await message.reply_text(str(exc))

    except Exception:
        logger.exception("Telegram document upload failed")
        await message.reply_text(
            "I couldn't process that document. Please try again."
        )

    finally:
        temporary_path.unlink(missing_ok=True)


async def documents_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    async with AsyncSessionLocal() as db:
        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

        if not session:
            await message.reply_text(
                "Please /login to see your documents."
            )
            return

        result = await db.execute(
            select(Document)
            .where(Document.user_id == session.user_id)
            .order_by(Document.created_at.desc())
            .limit(20)
        )
        documents = result.scalars().all()

    if not documents:
        await message.reply_text(
            "You haven't uploaded any documents yet. "
            "Send me a PDF, DOCX, or TXT file to get started."
        )
        return

    lines = ["📚 Your documents:\n"]

    for document in documents:
        lines.append(
            f"#{document.id} — {document.original_filename}\n"
            f"Status: {document.status}\n"
            f"Type: {document.file_type}\n"
        )

    await message.reply_text("\n".join(lines))


async def workflow_create_start(
    update:Update,
    context:ContextTypes
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return -1

    async with AsyncSessionLocal() as db:
        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

    if not session:
        await message.reply_text(
            "Please /login before creating a workflow."
        )
        return -1

    context.user_data["workflow_data"] = {}

    await message.reply_text(
        "Let's create a scheduled workflow.\n\n"
        "Enter a name for your workflow.\n"
        "Example: Daily research report"
    )

    return WORKFLOW_NAME


async def workflow_name_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None or not message.text:
        return WORKFLOW_NAME

    name = message.text.strip()

    if not 1 <= len(name) <= 150:
        await message.reply_text(
            "Name must contain between 1 and 150 characters."
        )
        return WORKFLOW_NAME

    context.user_data["workflow_data"]["name"] = name

    await message.reply_text(
        "Great! Now describe what the AI should do.\n\n"
        "Example:\n"
        "Analyse my latest five documents, identify important "
        "findings, and prepare a concise report."
    )

    return WORKFLOW_PROMPT


async def workflow_prompt_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None or not message.text:
        return WORKFLOW_PROMPT

    prompt = message.text.strip()

    if not 5 <= len(prompt) <= 3000:
        await message.reply_text(
            "Your instructions must contain 5 to 3000 characters."
        )
        return WORKFLOW_PROMPT

    context.user_data["workflow_data"]["prompt"] = prompt

    await message.reply_text(
        "At what time should this workflow run every day?\n\n"
        "Use 24-hour format: HH:MM\n"
        "Example: 09:30"
    )

    return WORKFLOW_TIME


async def workflow_time_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None or not message.text:
        return WORKFLOW_TIME

    schedule_time = message.text.strip()

    try:
        datetime.strptime(schedule_time, "%H:%M")
    except ValueError:
        await message.reply_text(
            "Invalid time. Please enter HH:MM, e.g. 09:30."
        )
        return WORKFLOW_TIME

    context.user_data["workflow_data"]["schedule_time"] = (
        schedule_time
    )

    await message.reply_text(
        "Enter your timezone.\n\n"
        "Default: Asia/Kolkata\n"
        "Examples: Asia/Kolkata, Europe/London, UTC"
    )

    return WORKFLOW_TIMEZONE


async def workflow_timezone_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message is None or not message.text:
        return WORKFLOW_TIMEZONE

    timezone_name = message.text.strip()

    try:
        ZoneInfo(timezone_name)
    except Exception:
        await message.reply_text(
            "Invalid timezone. Try Asia/Kolkata or UTC."
        )
        return WORKFLOW_TIMEZONE

    context.user_data["workflow_data"]["timezone"] = (
        timezone_name
    )

    await message.reply_text(
        "Where should I send the report?\n\n"
        "Reply with one of:\n"
        "1 - Telegram only\n"
        "2 - Email only\n"
        "3 - Both Telegram and email"
    )

    return WORKFLOW_CHANNELS


async def workflow_channels_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None or not message.text:
        return WORKFLOW_CHANNELS

    choice = message.text.strip()

    channels = {
        "1": (True, False),
        "2": (False, True),
        "3": (True, True),
    }

    # Step 1: Validate channel selection.
    if choice not in channels:
        await message.reply_text(
            "Please select 1, 2, or 3.\n\n"
            "1 - Telegram only\n"
            "2 - Email only\n"
            "3 - Both Telegram and email"
        )
        return WORKFLOW_CHANNELS

    telegram_enabled, email_enabled = channels[choice]

    # Step 2: Retrieve previously collected workflow data.
    data = context.user_data.get("workflow_data")

    if not data:
        await message.reply_text(
            "Your workflow creation session has expired. "
            "Please use /workflow_create again."
        )
        return ConversationHandler.END

    # Step 3: Validate workflow configuration.
    try:
        request = WorkflowCreateRequest(
            **data,
            telegram_enabled=telegram_enabled,
            email_enabled=email_enabled,
        )

    except ValidationError as exc:
        await message.reply_text(
            f"Invalid workflow configuration: {exc}"
        )
        return WORKFLOW_CHANNELS

    # Step 4: Authenticate Telegram user and check email.
    async with AsyncSessionLocal() as db:

        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

        if not session:
            await message.reply_text(
                "Your login session has expired. Please /login."
            )

            context.user_data.pop("workflow_data", None)
            return ConversationHandler.END

        if email_enabled:

            user = await db.get(User, session.user_id)

            if not user or not getattr(user, "email", None):

                await message.reply_text(
                    "Your account has no email address configured.\n\n"
                    "Choose Telegram only, or configure your email first.\n\n"
                    "Reply with:\n"
                    "1 - Telegram only\n"
                    "2 - Email only\n"
                    "3 - Both Telegram and email"
                )

                # CRITICAL FIX:
                # Preserve workflow_data and keep the conversation alive.
                return WORKFLOW_CHANNELS

        # Step 5: Calculate the next scheduled execution.
        next_run_at = next_daily_run(
            request.schedule_time,
            request.timezone,
        )

        # Step 6: Create workflow in PostgreSQL.
        workflow = Workflow(
            user_id=session.user_id,
            name=request.name,
            prompt=request.prompt,
            schedule_time=request.schedule_time,
            timezone=request.timezone,
            next_run_at=next_run_at,
            telegram_enabled=request.telegram_enabled,
            email_enabled=request.email_enabled,
            enabled=True,
        )

        db.add(workflow)

        await db.commit()
        await db.refresh(workflow)

        workflow_id = workflow.id

    # Step 7: Clear temporary conversation data only after success.
    context.user_data.pop("workflow_data", None)

    # Step 8: Confirm workflow creation.
    await message.reply_text(
        "✅ Workflow created successfully!\n\n"
        f"ID: {workflow_id}\n"
        f"Name: {request.name}\n"
        f"Schedule: {request.schedule_time}\n"
        f"Timezone: {request.timezone}\n"
        f"Next execution: {next_run_at.isoformat()}\n"
        f"Telegram: {'Enabled' if telegram_enabled else 'Disabled'}\n"
        f"Email: {'Enabled' if email_enabled else 'Disabled'}\n\n"
        "Use /workflows to see all your workflows."
    )

    return ConversationHandler.END



async def workflows_list_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    async with AsyncSessionLocal() as db:
        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

        if not session:
            await message.reply_text("Please /login first.")
            return

        result = await db.execute(
            select(Workflow)
            .where(Workflow.user_id == session.user_id)
            .order_by(Workflow.created_at.desc())
        )

        workflows = result.scalars().all()

        if not workflows:
            await message.reply_text(
                "You don't have any workflows yet.\n\n"
                "Use /workflow_create to create one."
            )
            return

        lines = ["📋 Your scheduled workflows:\n"]

        for workflow in workflows:
            lines.append(
                f"ID: {workflow.id}\n"
                f"Name: {workflow.name}\n"
                f"Schedule: {workflow.schedule_time} "
                f"({workflow.timezone})\n"
                f"Next run: {workflow.next_run_at.isoformat()}\n"
                f"Status: {'Enabled' if workflow.enabled else 'Disabled'}\n"
                f"Telegram: {workflow.telegram_enabled}\n"
                f"Email: {workflow.email_enabled}\n"
                "-------------------------"
            )

    await message.reply_text("\n".join(lines))


async def workflow_toggle_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    enabled: bool,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    if len(context.args) != 1:
        command = "workflow_enable" if enabled else "workflow_disable"
        await message.reply_text(
            f"Usage: /{command} <workflow_id>"
        )
        return

    try:
        workflow_id = int(context.args[0])
    except ValueError:
        await message.reply_text("Workflow ID must be a number.")
        return

    async with AsyncSessionLocal() as db:
        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

        if not session:
            await message.reply_text("Please /login first.")
            return

        result = await db.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.user_id == session.user_id,
            )
        )

        workflow = result.scalar_one_or_none()

        if not workflow:
            await message.reply_text(
                "Workflow not found."
            )
            return

        workflow.enabled = enabled

        if enabled:
            # Recalculate the next occurrence when re-enabled.
            workflow.next_run_at = next_daily_run(
                workflow.schedule_time,
                workflow.timezone,
            )

        await db.commit()

    status = "enabled" if enabled else "disabled"

    await message.reply_text(
        f"✅ Workflow {workflow_id} has been {status}."
    )


async def workflow_enable_handler(update, context):
    await workflow_toggle_handler(
        update, context, enabled=True
    )


async def workflow_disable_handler(update, context):
    await workflow_toggle_handler(
        update, context, enabled=False
    )


async def workflow_run_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    telegram_user = update.effective_user

    if message is None or telegram_user is None:
        return

    if len(context.args) != 1:
        await message.reply_text(
            "Usage: /workflow_run <workflow_id>"
        )
        return

    try:
        workflow_id = int(context.args[0])
    except ValueError:
        await message.reply_text(
            "Workflow ID must be a number."
        )
        return

    async with AsyncSessionLocal() as db:
        session = await get_telegram_session(
            db,
            telegram_user.id,
        )

        if not session:
            await message.reply_text("Please /login first.")
            return

        result = await db.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.user_id == session.user_id,
                Workflow.enabled.is_(True),
            )
        )

        workflow = result.scalar_one_or_none()

        if not workflow:
            await message.reply_text(
                "Enabled workflow not found."
            )
            return

        run = WorkflowRun(
            workflow_id=workflow.id,
            status="queued",
        )

        db.add(run)
        await db.commit()
        await db.refresh(run)

        run_id = run.id

    # Enqueue after the database commit.
    execute_workflow.delay(workflow_id, run_id)

    await message.reply_text(
        f"🚀 Workflow {workflow_id} has been queued.\n"
        f"Run ID: {run_id}\n\n"
        "I'll send the report when execution finishes."
    )

async def workflow_cancel_handler(update, context):
    context.user_data.pop("workflow_data", None)

    await update.effective_message.reply_text(
        "Workflow creation cancelled."
    )

    return ConversationHandler.END