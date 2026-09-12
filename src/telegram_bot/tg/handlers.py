import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.agents.agent import ask_agent
from sqlalchemy.ext.asyncio import AsyncSession

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

logger = logging.getLogger(__name__)
REGISTER_USERNAME = 1
REGISTER_PASSWORD = 2

LOGIN_USERNAME = 3
LOGIN_PASSWORD = 4


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

        "/help\n"
        "Show this help message.\n\n"

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

async def message_handler(
    update,
    context,
):

    if update.message is None:
        return

    telegram_user_id = update.effective_user.id

    user_id = await get_logged_in_user(
        telegram_user_id
    )

    if user_id is None:

        await update.message.reply_text(
            "🔐 You are not logged in.\n\n"
            "Please use /register to create an "
            "account, or /login if you already "
            "have one."
        )

        return

    user_message = update.message.text

    await update.message.chat.send_action(
        "typing"
    )

    async with AsyncSessionLocal() as db:

        conversation = await get_or_create_conversation(
            db,
            user_id,
        )

        history = await get_conversation_messages(
            db,
            conversation.id,
            limit=20,
        )

        await save_message(
            db,
            conversation.id,
            "user",
            user_message,
        )

        messages = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in history
        ]

        messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        response = await ask_agent(
            messages
        )

        await save_message(
            db,
            conversation.id,
            "assistant",
            response,
        )

    await update.message.reply_text(
        response
    )