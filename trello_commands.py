import requests
from dotenv import load_dotenv
import os
import re
import pytz
import aiohttp
import io
import discord

# Trello API credentials (You can move these to a config file if needed)
load_dotenv(dotenv_path="./credentials.env")
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_TOKEN = os.getenv('TRELLO_TOKEN')
TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')

# Set Pakistan Standard Time (PST) timezone
pst = pytz.timezone('Asia/Karachi')

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to search for an order in Trello
def search_order_in_trello(order_num, return_details=False):
    try:
        # Log the order number for debugging
        print(f"Searching for order number: {order_num}")

        # URL to fetch all lists from the board
        url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/lists?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        response = requests.get(url)

        if response.status_code != 200:
            return "Error: Unable to fetch lists from Trello. Please check your API key and token."

        lists = response.json()

        # Iterate over each list in the Trello board
        for list_ in lists:
            list_id = list_['id']
            # Fetch cards in each list
            cards_url = f"https://api.trello.com/1/lists/{list_id}/cards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            cards_response = requests.get(cards_url)

            if cards_response.status_code != 200:
                return f"Error: Unable to fetch cards for list {list_['name']}."

            cards = cards_response.json()

            # Iterate over the cards and extract the order number from each card's name
            for card in cards:
                card_name = card['name'].strip()
                print(f"Checking card: {card_name} in list: {list_['name']}")

                # Use regex to find the exact order number pattern
                # This looks for the pattern "# 1234" or similar
                card_num_match = re.search(r'#\s*(\d+)', card_name, re.IGNORECASE)

                if card_num_match:
                    card_num = int(card_num_match.group(1))  # Extract the numeric order number

                    # Compare order_num (int) with extracted card_num (int)
                    if order_num == card_num:
                        if return_details:
                            return f"**{card['name']}** found in list **{list_['name']}**."
                        return card

        return None  # If no match is found
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    
# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to move the order to another list
def move_order_in_trello(order_num, target_list_id, target_list_name):
    try:
        # Fetch the lists from the Trello board
        lists_url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/lists?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        lists_response = requests.get(lists_url)
        if lists_response.status_code != 200:
            return "Error: Unable to fetch lists from Trello."

        lists = lists_response.json()

        card_id = None
        card_name = None
        current_list_name = None

        # Search for the card in the lists
        for list_ in lists:
            list_id = list_['id']
            cards_url = f"https://api.trello.com/1/lists/{list_id}/cards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            cards_response = requests.get(cards_url)

            if cards_response.status_code != 200:
                return f"Error: Unable to fetch cards for list {list_['name']}."

            cards = cards_response.json()

            for card in cards:
                card_name = card['name'].strip()
                card_num_match = re.search(r'#\s*(\d+)', card_name, re.IGNORECASE)
                if card_num_match:
                    card_num = int(card_num_match.group(1))

                    if order_num == card_num:
                        card_id = card['id']
                        current_list_name = list_['name']
                        break
            if card_id:
                break

        if not card_id:
            return f"Order {order_num} not found."

        # Move the card to the new list
        move_url = f"https://api.trello.com/1/cards/{card_id}?idList={target_list_id}&key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        move_response = requests.put(move_url)

        if move_response.status_code == 200:
            return f"**{card_name}** moved from **{current_list_name}** to **{target_list_name}**."
        else:
            return f"Error: Unable to move order {order_num}."
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    
# Function to fetch Trello lists and cache them
def fetch_trello_lists():
    try:
        # Fetch all lists from Trello
        lists_url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/lists?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        lists_response = requests.get(lists_url)

        if lists_response.status_code != 200:
            return None, "Error: Unable to fetch lists from Trello."

        # Cache the lists
        cached_lists = lists_response.json()

        return cached_lists, None
    except requests.exceptions.RequestException as e:
        return None, f"Error: {e}"

# Function to get the current list of the order, using cached lists
def get_current_list_name(order_num, cached_lists):
    try:
        card_id = None
        card_name = None
        current_list_name = None

        # Search for the card in the cached lists
        for list_ in cached_lists:
            list_id = list_['id']
            cards_url = f"https://api.trello.com/1/lists/{list_id}/cards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            cards_response = requests.get(cards_url)

            if cards_response.status_code != 200:
                return None, f"Error: Unable to fetch cards for list {list_['name']}."

            cards = cards_response.json()

            for card in cards:
                card_name = card['name'].strip()
                card_num_match = re.search(r'#\s*(\d+)', card_name, re.IGNORECASE)
                if card_num_match:
                    card_num = int(card_num_match.group(1))
                    if order_num == card_num:
                        card_id = card['id']
                        current_list_name = list_['name']
                        break
            if card_id:
                break

        if not card_id:
            return None, f"Order {order_num} not found."

        return current_list_name, None

    except requests.exceptions.RequestException as e:
        return None, f"Error: {e}"

# Function to get available lists excluding the current one, using cached lists
def get_available_trello_lists(current_list_name, cached_lists):
    try:
        # Exclude the current list
        available_lists = [list_ for list_ in cached_lists if list_['name'] != current_list_name]

        return available_lists, None
    except Exception as e:
        return None, f"Error: {str(e)}"
    
# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to fetch the latest comments from a Trello card and download attachments
def fetch_latest_comments(order_num):
    try:
        # Search for the card by order number
        card = search_order_in_trello(order_num)

        if not card:
            return f"Order {order_num} not found.", None

        card_id = card['id']

        # URL to fetch actions (comments) for the card
        url = f"https://api.trello.com/1/cards/{card_id}/actions?filter=commentCard&key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
        response = requests.get(url)

        if response.status_code != 200:
            return "Error: Unable to fetch comments for this card.", None

        comments = response.json()

        if len(comments) == 0:
            return "No comments available for this card.", None

        # Extract the latest 3 comments
        latest_comments = comments[:3]
        comments_text = ""
        files = []

        for idx, comment in enumerate(latest_comments):
            comment_text = comment['data']['text']
            comments_text += f"{idx + 1}. {comment_text}\n"

            # Check if the comment has attachments
            comment_id = comment['id']

            # Fetch the attachments of the card
            attachment_url = f"https://api.trello.com/1/cards/{card_id}/attachments?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            attachment_response = requests.get(attachment_url)

            if attachment_response.status_code == 200:
                attachment_data = attachment_response.json()

                for attachment in attachment_data:
                    # Check if the attachment's date is near the comment's date (to match attachments to comments)
                    attachment_created = attachment['date']
                    comment_created = comment['date']

                    if is_attachment_near_comment_time(attachment_created, comment_created):
                        # Add the attachment name to the comment text
                        comments_text += f"    - Attachment: {attachment['name']}\n"

                        # Download the attachment
                        download_url = f"https://api.trello.com/1/cards/{card_id}/attachments/{attachment['id']}/download/{attachment['name']}"
                        download_response = requests.get(download_url, headers={
                            "Authorization": f"OAuth oauth_consumer_key=\"{TRELLO_API_KEY}\", oauth_token=\"{TRELLO_TOKEN}\""
                        })

                        if download_response.status_code == 200:
                            # Create a Discord File object
                            discord_file = discord.File(io.BytesIO(download_response.content), filename=attachment['name'])
                            files.append(discord_file)
                        else:
                            comments_text += f"    - Failed to download attachment: {attachment['name']}\n"

        return comments_text, files

    except requests.exceptions.RequestException as e:
        return f"Error: {e}", None

# Helper function to compare timestamps of comment and attachment
def is_attachment_near_comment_time(attachment_time, comment_time, time_threshold_minutes=5):
    from datetime import datetime, timedelta

    # Convert the strings into datetime objects
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    attachment_time_dt = datetime.strptime(attachment_time, fmt)
    comment_time_dt = datetime.strptime(comment_time, fmt)

    # Calculate the time difference
    time_difference = abs((attachment_time_dt - comment_time_dt).total_seconds() / 60.0)

    # Return True if the attachment was created within the threshold window
    return time_difference <= time_threshold_minutes

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to add a comment with an optional attachment to a Trello card
async def add_comment_with_attachment_in_trello(order_num, comment_text=None, attachment=None):
    try:
        # Search for the card by order number
        card = search_order_in_trello(order_num)

        if not card:
            return f"Order {order_num} not found."

        card_id = card['id']

        # If neither comment nor attachment is provided
        if not comment_text and not attachment:
            return "You need to provide either a comment, an attachment, or both."

        attachment_info = None

        # Handle the file upload if an attachment is provided
        if attachment:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as attachment_response:
                    if attachment_response.status != 200:
                        return f"Error: Failed to download attachment from Discord. Status code: {attachment_response.status}"

                    # Trello free limit is 10 MB
                    file_size_limit = 10 * 1024 * 1024  # 10 MB in bytes
                    if attachment.size > file_size_limit:
                        return f"Error: Attachment exceeds the 10 MB size limit allowed by Trello."

                    file_data = await attachment_response.read()

                    files = {
                        'file': (attachment.filename, file_data, attachment.content_type)  # Specify the MIME type
                    }

                    # Upload the file as an attachment to the card
                    url = f"https://api.trello.com/1/cards/{card_id}/attachments?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
                    response = requests.post(url, files=files)

                    if response.status_code == 200:
                        attachment_info = response.json()  # Get the attachment info from Trello

                    else:
                        return f"Error: Failed to upload attachment to Trello. Status code: {response.status_code}, Response: {response.text}"

        # Prepare the comment
        if comment_text:
            comment_to_add = comment_text
            if attachment_info and 'url' in attachment_info:
                comment_to_add += f"\n ![{attachment_info['name']}]({attachment_info['url']})"
        else:
            if attachment_info and 'url' in attachment_info:
                comment_to_add = f"Attachment: ![{attachment_info['name']}]({attachment_info['url']})"
            else:
                comment_to_add = None

        # Add the comment to the card
        if comment_to_add:
            url = f"https://api.trello.com/1/cards/{card_id}/actions/comments?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            response = requests.post(url, data={'text': comment_to_add})

            if response.status_code != 200:
                return f"Error: Unable to add comment. Status code: {response.status_code}, Response: {response.text}"

        return f"Comment and/or attachment added to order # **{order_num}**."

    except Exception as e:
        return f"Error: {e}"

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to set the due date for a Trello card
def set_order_due_date_in_trello(order_num, due_datetime):
    try:
        # Convert the provided datetime to UTC from PST
        due_datetime_pst = pst.localize(due_datetime)  # Localize to PST
        due_datetime_utc = due_datetime_pst.astimezone(pytz.utc)  # Convert to UTC
        
        # Search for the card by order number
        card = search_order_in_trello(order_num)

        if card:
            card_id = card['id']

            # Trello API endpoint for updating a card's due date
            url = f"https://api.trello.com/1/cards/{card_id}?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
            query = {
                'due': due_datetime_utc.isoformat(),  # ISO format in UTC
            }

            # Send request to Trello API
            response = requests.put(url, params=query)

            if response.status_code == 200:
                print(f"Due date for order {order_num} set to {due_datetime_utc}. (PST: {due_datetime})")
                return True
            else:
                print(f"Failed to set due date for order {order_num}. Status code: {response.status_code}")
                return False
        else:
            print(f"Order {order_num} not found in Trello.")
            return False

    except Exception as e:
        print(f"Error setting due date: {e}")
        return False

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxx/