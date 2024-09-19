from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, CallbackQueryHandler
from dotenv import load_dotenv
import os

# Storing user data
users = {}
current_game = {
    "buy_in": None,
    "players": [],
    "final_balances": {}
}
game_history = []

# Conversation states
ADD_USERS, GET_BUY_IN, SELECT_PLAYERS, GET_BALANCES, CONFIRM_RESET = range(5)

# Helper function to reset current game
def reset_current_game():
    current_game["buy_in"] = None
    current_game["players"] = []
    current_game["final_balances"] = {}

# /start command to introduce the bot
async def start(update, context):
    message = (
        "Welcome to the Poker Goats! Here's how to use it:\n\n"
        "1.If your group is using this bot for the very first time, use the command `/add_users` to add all potential players.\n"
        "2. Once players are added, use `/start_game` to begin a game.\n"
        "   - You will be prompted to enter the buy-in amount and select players.\n"
        "3. After the game, use `/end_game` to collect final balances from each player.\n"
        "   - The bot will display the final balances and who owes who.\n"
        "4. To clear all records, use `/reset_all_records`.\n\n"
        "Have fun, and let me know if you need help!"
    )
    await update.message.reply_text(message)

# /add_users command
async def add_users(update, context):
    await update.message.reply_text("Please list the users to add (comma-separated):")
    return ADD_USERS

# Handle added users
async def handle_add_users(update, context):
    user_list = update.message.text.split(',')
    user_list = [u.strip() for u in user_list]
    for user in user_list:
        if user not in users:
            users[user] = {"balance": 0}
    await update.message.reply_text(f"Users added: {', '.join(user_list)}")
    return ConversationHandler.END

# /start_game command
async def start_game(update, context):
    await update.message.reply_text("State the buy-in value (in dollars):")
    return GET_BUY_IN

# Handle buy-in value
async def get_buy_in(update, context):
    try:
        buy_in = float(update.message.text)
        current_game["buy_in"] = buy_in

        # Create inline buttons for selecting players
        buttons = [
            [InlineKeyboardButton("Select All", callback_data="all")],
            *[[InlineKeyboardButton(user, callback_data=user)] for user in users]
        ]
        markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text("Select your players:", reply_markup=markup)
        return SELECT_PLAYERS
    except ValueError:
        await update.message.reply_text("Please enter a valid buy-in amount (numeric).")
        return GET_BUY_IN

# Handle player selection via button clicks
async def handle_player_selection(update, context):
    query = update.callback_query
    await query.answer()

    selection = query.data.lower()

    if selection == "all":
        current_game["players"] = list(users.keys())
        await query.edit_message_text(f"All players selected: {', '.join(current_game['players'])}")
    else:
        if selection not in current_game["players"]:
            current_game["players"].append(selection)
        await query.edit_message_text(f"Player {selection} added.")

    # Once players are selected, confirm the selection
    if current_game["players"]:
        await query.message.reply_text(f"Game started with players: {', '.join(current_game['players'])}")
    return ConversationHandler.END

# /end_game command
async def end_game(update, context):
    if not current_game["players"]:
        await update.message.reply_text("No game in progress. Use /start_game to begin.")
        return ConversationHandler.END

    for player in current_game["players"]:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{player}, please enter your final balance:")
    return GET_BALANCES

# Handle final balances
# Handle final balances
async def get_balances(update, context):
    player = update.message.from_user.username
    
    # Check if the player is part of the current game
    if player not in current_game["players"]:
        await update.message.reply_text("You are not part of this game.")
        return GET_BALANCES

    try:
        # Validate that the balance is numeric
        balance = float(update.message.text)
        current_game["final_balances"][player] = balance
        
        # Confirm the balance entry to the player
        await update.message.reply_text(f"{player}, your final balance is recorded as: ${balance}")
        
        # Check if all balances have been collected
        if len(current_game["final_balances"]) == len(current_game["players"]):
            # Display the final balances and save the game history
            table = "\n".join([f"{p}: ${b}" for p, b in current_game["final_balances"].items()])
            await update.message.reply_text(f"Final balances for the game:\n{table}")
            
            # Store the current game in the game history and reset the game
            game_history.append(current_game.copy())
            reset_current_game()
            return ConversationHandler.END
        else:
            # Notify other players to submit their balances if needed
            remaining_players = [p for p in current_game["players"] if p not in current_game["final_balances"]]
            for player in remaining_players:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{player}, please enter your final balance:")
            return GET_BALANCES

    except ValueError:
        # If the balance is invalid, ask the player to re-enter the balance
        await update.message.reply_text("Invalid balance entered. Please enter a valid numeric balance.")
        return GET_BALANCES


# /reset_all_records command
async def reset_all_records(update, context):
    await update.message.reply_text("Are you sure you want to reset all past records? Type 'yes' to confirm.")
    return CONFIRM_RESET

# Handle confirmation to reset
async def confirm_reset(update, context):
    if update.message.text.strip().lower() == 'yes':
        game_history.clear()
        await update.message.reply_text("All records have been reset.")
    else:
        await update.message.reply_text("Reset canceled.")
    return ConversationHandler.END

# Main function to start the bot
def main():
    load_dotenv()
    token = os.getenv("TELE_API_KEY")
    application = Application.builder().token(token).build()

    # Command handlers
    conv_handler_add_users = ConversationHandler(
        entry_points=[CommandHandler("add_users", add_users)],
        states={ADD_USERS: [MessageHandler(filters.TEXT, handle_add_users)]},
        fallbacks=[]
    )

    conv_handler_start_game = ConversationHandler(
        entry_points=[CommandHandler("start_game", start_game)],
        states={
            GET_BUY_IN: [MessageHandler(filters.TEXT, get_buy_in)],
            SELECT_PLAYERS: [CallbackQueryHandler(handle_player_selection)],
        },
        fallbacks=[]
    )

    conv_handler_end_game = ConversationHandler(
        entry_points=[CommandHandler("end_game", end_game)],
        states={GET_BALANCES: [MessageHandler(filters.TEXT, get_balances)]},
        fallbacks=[]
    )

    conv_handler_reset_records = ConversationHandler(
        entry_points=[CommandHandler("reset_all_records", reset_all_records)],
        states={CONFIRM_RESET: [MessageHandler(filters.TEXT, confirm_reset)]},
        fallbacks=[]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler_add_users)
    application.add_handler(conv_handler_start_game)
    application.add_handler(conv_handler_end_game)
    application.add_handler(conv_handler_reset_records)

    print("Telegram Bot started!")
    application.run_polling()

if __name__ == '__main__':
    main()
