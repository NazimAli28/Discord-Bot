import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from dateutil import parser
import os
from reminder_commands import *
from trello_commands import *
from dotenv import load_dotenv

load_dotenv(dotenv_path="./credentials.env")
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot with command prefix for old commands and intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # For slash commands

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to check and send missed reminders on bot startup
async def send_missed_reminders():
    now_utc = datetime.now(UTC)

    # Fetch reminders that were supposed to be sent before the current time
    missed_reminders = get_due_reminders(now_utc.isoformat())

    for reminder in missed_reminders:
        reminder_id, reminder_time, message, user_name, user_id, channel_name, channel_id = reminder

        try:
            # Convert reminder_time from ISO format to a datetime object in UTC
            reminder_time_utc = datetime.fromisoformat(reminder_time)

            # Convert reminder_time from UTC to PST
            reminder_time_pst = reminder_time_utc.astimezone(PST)

            # Format reminder_time in a human-friendly way
            formatted_reminder_time = reminder_time_pst.strftime('%d %b %Y %H:%M %Z')

            # Send the missed reminder
            channel = await bot.fetch_channel(channel_id)
            user = await bot.fetch_user(user_id)
            await channel.send(f"{user.mention} **Missed Reminder:** {message} (was due at {formatted_reminder_time})")

            # Move the reminder to the past_reminders table
            move_reminder_to_past(reminder_id, reminder_time, message, user_name, user_id, channel_name, channel_id)

        except Exception as e:
            print(f"Error sending missed reminder: {e}")

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Event: When the bot is ready
@bot.event
async def on_ready():
    initialize_database()  # Ensure the database and tables are created
    print(f'Bot is online! Logged in as {bot.user}')

    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name} (ID: {guild.id})')

    # Sync the slash commands with Discord
    try:
        await tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")
    
    # Check for and send missed reminders
    await send_missed_reminders()

    # Start the reminder checking loop
    check_reminders.start()

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash Command: Set reminder using /remind with separate date, time, and message
@tree.command(name="reminder", description="Set a reminder")
@app_commands.describe(date="Date in format DD MMM (Year optional)", time="Time in format HH:MM", message="Reminder message")
async def slash_remindme(interaction: discord.Interaction, date: str, time: str, message: str):
    try:
        # Get user and channel details from the interaction
        user_name = interaction.user.name
        user_id = interaction.user.id
        channel_name = interaction.channel.name
        channel_id = interaction.channel.id

        # Call save_reminder to save the reminder and get the result
        success, response = save_reminder(date, time, message, user_name, user_id, channel_name, channel_id)

        if success:
            await interaction.response.send_message(f"Reminder set for {response.strftime('%d %b %Y %H:%M %Z')}!")
        else:
            await interaction.response.send_message(response, ephemeral=True)  # Send the error message to the user

    except ValueError as e:
        print(f"Error parsing date or time: {e}")
        await interaction.response.send_message("Invalid date or time format. Please try again.", ephemeral=True)

# Task: Checks every 10 seconds for due reminders
@tasks.loop(seconds=10)
async def check_reminders():
    now_utc = datetime.now(UTC)

    # Get reminders that are currently due
    due_reminders = get_due_reminders(now_utc.isoformat())

    for reminder in due_reminders:
        reminder_id, reminder_time, message, user_name, user_id, channel_name, channel_id = reminder

        try:
            # Send the reminder
            channel = await bot.fetch_channel(channel_id)
            user = await bot.fetch_user(user_id)
            await channel.send(f"{user.mention} **Reminder:** {message}")

            # Move the reminder to the past_reminders table
            move_reminder_to_past(reminder_id, reminder_time, message, user_name, user_id, channel_name, channel_id)

        except Exception as e:
            print(f"Error sending reminder: {e}")

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash Command: List reminders based on user selection
@tree.command(name="reminders_list", description="List reminders (active, past, or both)")
@app_commands.choices(reminder_type=[
    app_commands.Choice(name="Active", value="active"),
    app_commands.Choice(name="Past", value="past"),
    app_commands.Choice(name="Both", value="both")
])
async def slash_reminders_list(interaction: discord.Interaction, reminder_type: app_commands.Choice[str]):
    try:
        # Load active reminders and past reminders from files
        active_reminders = get_active_reminders()  # Load active reminders
        past_reminders = get_past_reminders()  # Load past reminders

        # Function to safely convert time strings to datetime objects
        def convert_to_datetime(time_value):
            if isinstance(time_value, str):
                return parser.parse(time_value)  # Convert string to datetime
            elif isinstance(time_value, datetime):
                return time_value  # Already a datetime object
            else:
                raise ValueError("Unsupported time format.")

        # Paginate reminders based on user's choice
        active_pages = []
        past_pages = []
        current_page = ""

        if reminder_type.value == "active" or reminder_type.value == "both":
            # Paginate active reminders
            for reminder in active_reminders:
                reminder_time_utc = convert_to_datetime(reminder['reminder_time'])
                reminder_time_pst = reminder_time_utc.astimezone(pst)
                reminder_str = f"**ID:** {reminder['id']}\n**Reminder Message:** {reminder['message']}\n**Time:** {reminder_time_pst.strftime('%d %b %Y %H:%M %Z')}\n**User:** {reminder['user_name']}\n**Channel:** {reminder['channel_name']}\n\n"
                if len(current_page) + len(reminder_str) > 1900:
                    active_pages.append(current_page)
                    current_page = reminder_str
                else:
                    current_page += reminder_str

            if current_page:
                active_pages.append(current_page)

        current_page = ""

        if reminder_type.value == "past" or reminder_type.value == "both":
            # Paginate past reminders
            for past_reminder in past_reminders:
                past_reminder_time_utc = convert_to_datetime(past_reminder['reminder_time'])
                past_reminder_time_pst = past_reminder_time_utc.astimezone(pst)
                past_reminder_str = f"**ID:** {past_reminder['id']}\n**Reminder Message:** {past_reminder['message']}\n**Time:** {past_reminder_time_pst.strftime('%d %b %Y %H:%M %Z')}\n**User:** {past_reminder['user_name']}\n**Channel:** {past_reminder['channel_name']}\n\n"
                if len(current_page) + len(past_reminder_str) > 1900:
                    past_pages.append(current_page)
                    current_page = past_reminder_str
                else:
                    current_page += past_reminder_str

            if current_page:
                past_pages.append(current_page)

        # Handle responses based on the reminder_type
        if reminder_type.value == "active":
            if active_pages:
                await interaction.response.send_message(f"**Active Reminders (Page 1/{len(active_pages)})**\n```\n{active_pages[0]}\n```", ephemeral=True)
                for i, page in enumerate(active_pages[1:]):
                    await interaction.followup.send(f"**Active Reminders (Page {i + 2}/{len(active_pages)})**\n```\n{page}\n```", ephemeral=True)
            else:
                await interaction.response.send_message("No active reminders.", ephemeral=True)

        elif reminder_type.value == "past":
            if past_pages:
                await interaction.response.send_message(f"**Past Reminders (Page 1/{len(past_pages)})**\n```\n{past_pages[0]}\n```", ephemeral=True)
                for i, page in enumerate(past_pages[1:]):
                    await interaction.followup.send(f"**Past Reminders (Page {i + 2}/{len(past_pages)})**\n```\n{page}\n```", ephemeral=True)
            else:
                await interaction.response.send_message("No past reminders.", ephemeral=True)

        elif reminder_type.value == "both":
            # Combine both active and past reminders
            initial_message_sent = False

            if active_pages:
                await interaction.response.send_message(f"**Active Reminders (Page 1/{len(active_pages)})**\n```\n{active_pages[0]}\n```", ephemeral=True)
                for i, page in enumerate(active_pages[1:]):
                    await interaction.followup.send(f"**Active Reminders (Page {i + 2}/{len(active_pages)})**\n```\n{page}\n```", ephemeral=True)
                initial_message_sent = True

            if past_pages:
                if not initial_message_sent:
                    await interaction.response.send_message(f"**Past Reminders (Page 1/{len(past_pages)})**\n```\n{past_pages[0]}\n```", ephemeral=True)
                else:
                    await interaction.followup.send(f"**Past Reminders (Page 1/{len(past_pages)})**\n```\n{past_pages[0]}\n```", ephemeral=True)
                for i, page in enumerate(past_pages[1:]):
                    await interaction.followup.send(f"**Past Reminders (Page {i + 2}/{len(past_pages)})**\n```\n{page}\n```", ephemeral=True)

            if not active_pages and not past_pages:
                await interaction.response.send_message("No active or past reminders.", ephemeral=True)

    except Exception as e:
        print(f"Error loading or displaying reminders: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while fetching reminders.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while fetching reminders.", ephemeral=True)

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash Command to remove a reminder
@tree.command(name="reminder_remove", description="Remove an existing reminder")
@app_commands.describe(idx="The reminder index to remove")
async def removereminder(interaction: discord.Interaction, idx: int):
    # Call the function in reminder_commands.py to remove the reminder
    _, message = remove_reminder(idx)
    
    # Respond with the message returned from remove_reminder
    await interaction.response.send_message(message, ephemeral=True)

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash Command: Edit an existing reminder (date, time, and/or message)
@tree.command(name="reminder_edit", description="Edit an existing reminder")
@app_commands.describe(idx="The reminder index to edit", new_date="New date (optional, in format DD MMM YYYY)", new_time="New time (optional, in format HH:MM)", new_message="New message for the reminder (optional)")
async def editreminder(interaction: discord.Interaction, idx: int, new_date: str = None, new_time: str = None, new_message: str = None):
    # Call the function in reminder_commands.py to edit the reminder
    _, message = edit_reminder(idx, new_date, new_time, new_message)
    
    # Respond with the message returned from edit_reminder
    await interaction.response.send_message(message, ephemeral=True)

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash command to find the order in Trello
@tree.command(name="order_status", description="Find an order in Trello")
@app_commands.describe(order_num="The order number you want to search")
async def find_order(interaction: discord.Interaction, order_num: int):
    try:
        # Defer the interaction with timeout (to prevent "This interaction failed")
        await interaction.response.defer()

        # Search for the order in Trello
        result = search_order_in_trello(order_num, return_details=True)

        # Send a follow-up message with the result
        if result:
            await interaction.followup.send(f"**Order Status:** {result}")
        else:
            await interaction.followup.send(f"Order **{order_num}** not found.", ephemeral=True)

    except Exception as e:
        # Handle errors gracefully
        try:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        except discord.errors.NotFound:
            print("Interaction expired, cannot send the result.")

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash command to move the order to another list in Trello (asynchronous version)
@tree.command(name="order_move", description="Move an order to another list in Trello")
@app_commands.describe(order_num="The order number you want to move")
async def move_order(interaction: discord.Interaction, order_num: int):
    await interaction.response.defer()  # Defer the response to allow time for processing

    try:
        # Immediately send a placeholder message to avoid interaction expiration
        await interaction.followup.send("Fetching Trello data, please wait...", ephemeral=True)

        # Fetch Trello lists asynchronously
        cached_lists, error = fetch_trello_lists()
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        # Get the current list name for the order using the cached lists
        current_list_name, error = get_current_list_name(order_num, cached_lists)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        # Get available lists, excluding the current one
        available_lists, error = get_available_trello_lists(current_list_name, cached_lists)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        # Create select menu options using the list name and id
        options = [
            discord.SelectOption(label=list_info['name'], value=list_info['id'])
            for list_info in available_lists
        ]

        # Define select menu for choosing a list
        class ListSelect(discord.ui.Select):
            def __init__(self, options):
                super().__init__(placeholder="Choose a target list...", min_values=1, max_values=1, options=options)

            async def callback(self, select_interaction: discord.Interaction):
                # Get the selected target list ID
                target_list_id = self.values[0]
                target_list_name = next((opt.label for opt in options if opt.value == target_list_id), None)

                if not target_list_name:
                    await select_interaction.response.send_message("Error: Could not determine the target list name.", ephemeral=True)
                    return

                # Disable the select menu after selection
                self.disabled = True

                # Indicate processing status to the user
                await select_interaction.response.edit_message(content="Moving order... Please wait.", view=self.view)

                # Move the card using the selected list ID and name
                result = move_order_in_trello(order_num, target_list_id, target_list_name)

                # Send the result to the user
                await select_interaction.followup.send(result)

        # In the move_order command, create a view instance before sending the select menu
        view = discord.ui.View(timeout=180)
        view.add_item(ListSelect(options))

        # Send the select menu to the user
        await interaction.followup.send(f"Order # **{order_num}** from list **{current_list_name}** is selected:", view=view, ephemeral=True)

    except Exception as e:
        try:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        except discord.errors.NotFound:
            print("Interaction expired, cannot send the result.")

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash command to get the latest comments for an order
@tree.command(name="order_comments", description="Get the latest comments on an order")
@app_commands.describe(order_num="The order number you want to get comments for")
async def get_comments(interaction: discord.Interaction, order_num: int):
    try:
        # Defer the interaction to prevent timeouts
        await interaction.response.defer()

        # Fetch the latest comments and attachments from Trello
        comments, attachments = fetch_latest_comments(order_num)

        if attachments:  # If attachments exist
            # Send comments with files as attachments in Discord
            await interaction.followup.send(content=f"**Latest Comments for Order {order_num}:**\n{comments}", files=attachments)
        else:
            # If no attachments, just send the comments
            await interaction.followup.send(content=f"**Latest Comments for Order {order_num}:**\n{comments}")

    except Exception as e:
        await interaction.followup.send(f"Error fetching comments: {str(e)}", ephemeral=True)

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash command to add a comment with an attachment to an order in Trello
@tree.command(name="add_order_comment", description="Add a comment and/or attach a file to an order in Trello")
@app_commands.describe(order_num="The order number you want to comment on", comment_text="The comment you want to add", attachment="The file you want to attach (optional)")
async def add_comment_with_attachment(interaction: discord.Interaction, order_num: int, comment_text: str = None, attachment: discord.Attachment = None):
    try:
        # Defer the interaction to prevent timeouts
        await interaction.response.defer()

        # Call the function to add comment and attachment in Trello
        result = await add_comment_with_attachment_in_trello(order_num, comment_text, attachment)

        # Send the result back to the user
        await interaction.followup.send(result, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"Error adding comment or attachment: {str(e)}", ephemeral=True)

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Slash command to set or edit due date for an order in Trello
@tree.command(name="set_order_due_date", description="Set or edit the due date for an order in Trello")
@app_commands.describe(order_num="The order number you want to set the due date for", date="The due date (e.g., '27 Sep', 'Sep 27 2024', etc.)", time="The time in HH:MM 24-hour format")
async def set_order_due_date(interaction: discord.Interaction, order_num: int, date: str, time: str):
    try:
        # Acknowledge the interaction first
        await interaction.response.defer()

        # Get current date for default year or month if needed
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Try to parse the date string flexibly
        try:
            due_date = parser.parse(date, default=datetime(current_year, current_month, 1))
        except ValueError:
            raise ValueError("Invalid date format. Please provide a recognizable date like '27 Sep' or 'Sep 27 2024'.")

        # Time is required, parse it
        try:
            due_time = datetime.strptime(time, "%H:%M").time()  # Only parse time in HH:MM format
        except ValueError:
            raise ValueError("Invalid time format. Please provide time in HH:MM 24-hour format.")

        # Combine the date and time into a single datetime object
        due_datetime = datetime.combine(due_date, due_time)

        # Call the function from trello_commands to set the due date
        if set_order_due_date_in_trello(order_num, due_datetime):
            await interaction.followup.send(f"Due date for order **# {order_num}** has been set to **{due_datetime.strftime('%d %b %Y %H:%M')}** PST.")
        else:
            await interaction.followup.send(f"Failed to set due date for order **# {order_num}**.")
    
    except ValueError as e:
        await interaction.followup.send(str(e))

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Run the bot
bot.run(DISCORD_TOKEN)