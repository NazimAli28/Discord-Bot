from datetime import datetime
import sqlite3
import pytz
from dateutil import parser

# Time zone for PST
PST = pytz.timezone('Asia/Karachi')
UTC = pytz.UTC

DB_PATH = "./database/reminders.db"

# Function to initialize the database and create tables if they don't exist
def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create reminders table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_time TEXT,
            message TEXT,
            user_name TEXT,
            user_id INTEGER,
            channel_name TEXT,
            channel_id INTEGER
        )
    ''')

    # Create past_reminders table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS past_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_time TEXT,
            message TEXT,
            user_name TEXT,
            user_id INTEGER,
            channel_name TEXT,
            channel_id INTEGER
        )
    ''')

    conn.commit()
    conn.close()

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to check for reminders due at a certain time or missed
def get_due_reminders(before_time):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch reminders that are due (i.e., `reminder_time` is less than or equal to `before_time`)
    cursor.execute('''SELECT id, reminder_time, message, user_name, user_id, channel_name, channel_id 
                      FROM active_reminders WHERE reminder_time <= ?''', (before_time,))
    
    due_reminders = cursor.fetchall()
    
    conn.close()
    return due_reminders

# Function to move a reminder to the past_reminders table
def move_reminder_to_past(reminder_id, reminder_time, message, user_name, user_id, channel_name, channel_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Insert reminder into past_reminders table
        cursor.execute('''
            INSERT INTO past_reminders (reminder_time, message, user_name, user_id, channel_name, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (reminder_time, message, user_name, user_id, channel_name, channel_id))
        
        # Remove reminder from reminders table after moving it to past_reminders
        cursor.execute('DELETE FROM active_reminders WHERE id = ?', (reminder_id,))
        
        conn.commit()
    except Exception as e:
        print(f"Error moving reminder to past_reminders: {e}")
    finally:
        conn.close()

# Function to save reminders in database
def save_reminder(date_str, time_str, message, user_name, user_id, channel_name, channel_id):
    conn = None  # Initialize conn variable here
    try:
        # Combine date and time into a single string
        date_time_str = f"{date_str} {time_str}"

        # Parse the date and time, allowing flexible input (e.g., "1 Dec", "1", etc.)
        reminder_time_pst = parser.parse(date_time_str, dayfirst=True)  # Handle day-first formats
        
        # If only the day was provided, use current month/year by default
        now = datetime.now(PST)
        if reminder_time_pst.year == 1900:  # If no year provided
            reminder_time_pst = reminder_time_pst.replace(year=now.year)
        if reminder_time_pst.month == 1 and reminder_time_pst.day == 1:  # If no month/day provided
            reminder_time_pst = reminder_time_pst.replace(month=now.month, day=now.day)

        # Localize to PST
        reminder_time_pst = PST.localize(reminder_time_pst, is_dst=None)

        # Check if the reminder time is in the past
        if reminder_time_pst < now:
            print(f"Cannot set a reminder in the past: {reminder_time_pst.strftime('%d %b %Y %H:%M %Z')}")
            return False, "You can't set a reminder for the past time."

        # Convert PST time to UTC for storage
        reminder_time_utc = reminder_time_pst.astimezone(UTC)

        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Insert the new reminder into the reminders table
        cursor.execute('''
            INSERT INTO active_reminders (reminder_time, message, user_name, user_id, channel_name, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (reminder_time_utc.isoformat(), message, user_name, user_id, channel_name, channel_id))

        conn.commit()
        print(f"Reminder saved successfully for {reminder_time_pst.strftime('%d %b %Y %H:%M %Z')}.")
        return True, reminder_time_pst  # Return success and the localized reminder time for confirmation

    except Exception as e:
        print(f"Error saving reminder: {e}")
        return False, f"Error saving reminder: {e}"

    finally:
        # Only close the connection if it was successfully established
        if conn:
            conn.close()

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to fetch active reminders (future reminders)
def get_active_reminders():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch reminders that are due after the specified time (i.e., future reminders)
    cursor.execute('''SELECT id, reminder_time, message, user_name, user_id, channel_name, channel_id 
                      FROM active_reminders''')
    
    # Convert tuples to dictionaries
    columns = [column[0] for column in cursor.description]  # Get column names
    active_reminders = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    conn.close()
    return active_reminders

# Function to fetch past reminders (already triggered)
def get_past_reminders():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch all reminders from past_reminders table
    cursor.execute('''SELECT id, reminder_time, message, user_name, user_id, channel_name, channel_id 
                      FROM past_reminders''')
    
    # Convert tuples to dictionaries
    columns = [column[0] for column in cursor.description]  # Get column names
    past_reminders = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    conn.close()
    return past_reminders

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to remove active reminder from database using id
def remove_reminder(reminder_id):
    conn = None
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Delete the reminder from the active_reminders table
        cursor.execute('DELETE FROM active_reminders WHERE id = ?', (reminder_id,))

        if cursor.rowcount > 0:
            conn.commit()
            return True, "Reminder removed successfully."
        else:
            return False, "No reminder found with the given index."

    except Exception as e:
        return False, f"Error removing reminder: {e}"

    finally:
        if conn:
            conn.close()

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/

# Function to edit active reminder from database using id
def edit_reminder(reminder_id, new_date=None, new_time=None, new_message=None):
    conn = None
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Fetch the current reminder details
        cursor.execute('SELECT reminder_time, message FROM active_reminders WHERE id = ?', (reminder_id,))
        reminder = cursor.fetchone()

        if not reminder:
            return False, "No reminder found with the given index."

        current_time_utc = reminder[0]
        current_message = reminder[1]

        # Parse new reminder time if provided
        if new_date or new_time:
            current_reminder_time = parser.parse(current_time_utc).astimezone(PST)

            # Use provided date or time or fallback to current ones
            date_to_use = new_date if new_date else current_reminder_time.strftime("%d %b %Y")
            time_to_use = new_time if new_time else current_reminder_time.strftime("%H:%M")

            date_time_str = f"{date_to_use} {time_to_use}"
            reminder_time_pst = parser.parse(date_time_str, dayfirst=True)
            reminder_time_pst = PST.localize(reminder_time_pst)

            # Convert reminder time to UTC
            new_reminder_time_utc = reminder_time_pst.astimezone(UTC)
        else:
            new_reminder_time_utc = current_time_utc

        # Use provided message or fallback to current one
        new_message = new_message if new_message else current_message

        # Update the reminder in the active_reminders table
        cursor.execute('''
            UPDATE active_reminders
            SET reminder_time = ?, message = ?
            WHERE id = ?
        ''', (new_reminder_time_utc.isoformat(), new_message, reminder_id))

        conn.commit()
        return True, "Reminder updated successfully."

    except Exception as e:
        return False, f"Error editing reminder: {e}"

    finally:
        if conn:
            conn.close()

# /xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/