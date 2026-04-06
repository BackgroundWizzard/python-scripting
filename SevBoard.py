# ============================================
#         PERSONAL CLI DASHBOARD
#               Stage 1
# ============================================
# HOW TO RUN:
#   python dashboard.py
#
# THINGS TO TRY:
#   - Change YOUR_NAME to your actual name
#   - Add your own quotes to the QUOTES list
#   - Add your own tasks to the TASKS list
# ============================================

import datetime
import random
#import python_weather
# ---- YOUR PERSONAL SETTINGS ----
YOUR_NAME = "Kelvin"   # <-- Change this to your name!

QUOTES = [
    "The secret of getting ahead is getting started. – Mark Twain",
    "It always seems impossible until it's done. – Nelson Mandela",
    "Don't watch the clock; do what it does. Keep going. – Sam Levenson",
    "Push yourself, because no one else is going to do it for you.",
    "Small steps every day lead to big results.",
]

TASKS = [
    "Review Python notes",
    "Do Coding Homework",
    "Go for a walk",
    "Drink more water",
    "Work on dashboard project",
]


# ---- HELPER FUNCTIONS ----
# A "function" is a reusable block of code. You'll use these a lot!

def print_separator():
    """Prints a dividing line to make things look tidy."""
    print("-" * 40)

def show_greeting():
    """Shows a personalized greeting with the current date and time."""
    now = datetime.datetime.now()
    # strftime formats the date/time into a readable string
    date_str = now.strftime("%A, %B %d %Y")   # e.g. Monday, March 10 2025
    time_str = now.strftime("%I:%M %p")        # e.g. 09:30 AM

    print_separator()
    print(f"  👋  Good morning, {YOUR_NAME}!")
    print(f"  📅  {date_str}")
    print(f"  🕐  {time_str}")
    print_separator()

def show_quote():
    """Picks a random quote from the QUOTES list and displays it."""
    quote = random.choice(QUOTES)
    print("\n💬 Quote of the moment:")
    print(f"   {quote}")

def show_tasks():
    """Displays your to-do list."""
    print("\n📋 Today's Tasks:")
    # enumerate() gives us a number alongside each item
    for i, task in enumerate(TASKS, start=1):
        print(f"   {i}. {task}")


# ---- MAIN PROGRAM ----
# This is where the program starts running.
# Think of it as the "director" that calls your functions in order.

def main():
    show_greeting()
    show_quote()
    show_tasks()
    print_separator()
    print("  Have a great day! 🚀")
    print_separator()

# This line means: only run main() if we're running THIS file directly
# (not importing it from another file — you'll learn why this matters later!)
if __name__ == "__main__":
    main()