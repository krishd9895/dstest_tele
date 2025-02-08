import telebot
import ds
import logging
import os
from session_manager import session_manager

# Initialize bot with your token
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User input handling
ds.user_inputs = {}


# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    if session_manager.is_user_busy(user_id):
        bot.reply_to(message,
                     "⚠️ session is already active. Please wait for the current operation to complete or use /logout to reset.")
        return

    ds.clear_status(user_id)  # Clear any existing status
    ds.set_bot_instance(bot, user_id)
    session_manager.get_session(user_id)
    bot.reply_to(message, '👋 Welcome! I\'m ready to help you. Use /login to begin.')


# Login command handler
@bot.message_handler(commands=['login'])
def handle_login(message):
    user_id = message.chat.id
    if session_manager.is_user_busy(user_id):
        bot.reply_to(message,
                     "⚠️ session is already active. Please wait for the current operation to complete or use /logout to reset.")
        return

    ds.clear_status(user_id)  # Clear any existing status
    ds.set_bot_instance(bot, user_id)
    session_manager.set_user_busy(user_id, True)
    try:
        success = ds.handle_login_attempt(user_id)
        if not success:
            session_manager.close_session(user_id)
    except Exception as e:
        bot.reply_to(message, f"❌ Error during login: {str(e)}")
        session_manager.close_session(user_id)
    finally:
        session_manager.set_user_busy(user_id, False)


# Logout command handler
@bot.message_handler(commands=['logout'])
def handle_logout(message):
    user_id = message.chat.id
    ds.clear_status(user_id)  # Clear any existing status
    session_manager.close_session(user_id)
    bot.reply_to(message, '👋 Logged out successfully.')


# Operations command handler
@bot.message_handler(commands=['operations'])
def handle_operations(message):
    user_id = message.chat.id
    if session_manager.is_user_busy(user_id):
        bot.reply_to(message,
                     "⚠️session is already active. Please wait for the current operation to complete or use /logout to reset.")
        return

    ds.clear_status(user_id)  # Clear any existing status
    ds.set_bot_instance(bot, user_id)
    session_manager.set_user_busy(user_id, True)
    try:
        ds.post_login_operations(user_id)
    except Exception as e:
        bot.reply_to(message, f"❌ Error during operations: {str(e)}")
    finally:
        session_manager.set_user_busy(user_id, False)


# Update the input handler
@bot.message_handler(func=lambda message: True)
def handle_user_input(message):
    user_id = message.chat.id
    if user_id in ds.user_inputs and ds.user_inputs[user_id] is None:
        ds.user_inputs[user_id] = message.text
        bot.reply_to(message, '✅ Input received!')


# Start the bot
if __name__ == '__main__':
    logger.info('Starting bot...')
    bot.infinity_polling()
