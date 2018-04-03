""" Lil Mo is a slack bot that takes input from slack and executes automation scripts
"""

import time
import datetime
import re
from slackclient import SlackClient
import json
import calendar


class LilMoHouseBot:

    def __init__(self,):

        # Open config and grab the json file
        with open('config.json') as json_data_file:
            data = json.load(json_data_file)

        # instantiate Slack client
        slack_bot_token = data['SlackBotToken']
        self.slack_client = SlackClient(slack_bot_token)

        # starterbot's user ID in Slack: value is assigned after the bot starts up
        self.starterbot_id = None

        # Set up structures for tracking renters, renters paid, and renters not paid. Grabbing renters from config.
        self.renters = data["Users"]

        self.renters_paid = {}

        self.renters_not_paid = {}

        # Setting this low to reset in functions
        self.last_day_of_relative_month = datetime.datetime(year=1900, month=1,
                                                            day=1)

        one_day = datetime.timedelta(days=1)
        self.first_day_of_next_month = self.last_day_of_relative_month + one_day

        # Set ping flags
        self.seven_days_ping = False
        self.four_days_ping = False
        self.one_days_ping = False
        self.nine_day_of_ping = False
        self.twelve_day_of_ping = False
        self.five_day_of_ping = False
        self.ten_day_of_ping = False

        self.__reset_emergency_pings()

        # constants
        self.rtm_read_delay = 1 # 1 second delay between reading from RTM
        self.command_keyword = "-run"
        self.input_keyword = '-in'
        self.help_keyword = '-help'
        self.mention_regex = "^<@(|[WU].+?)>(.*)"

    def parse_bot_commands(self, slack_events):
        """
            Parses a list of events coming from the Slack RTM API to find bot commands.
            If a bot command is found, this function returns a tuple of command and channel.
            If its not found, then this function returns None, None.
        """
        for event in slack_events:
            if event["type"] == "message" and not "subtype" in event:
                user_id, message = self.parse_direct_mention(event["text"])
                if user_id == self.starterbot_id:
                    return message, event["channel"]
        return None, None

    def parse_direct_mention(self, message_text):
        """
            Finds a direct mention (a mention that is at the beginning) in message text
            and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(self.mention_regex, message_text)
        # the first group contains the username, the second group contains the remaining message
        return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

    def handle_command(self, command, channel):
        """
            Executes bot command if the command is known
        """
        # Default response is help text for the user
        default_response = "Not sure what you mean. Try *{}*.".format(self.command_keyword)

        # Finds and executes the given command, filling in response
        response = None

        if command.startswith(self.command_keyword + ' remove'):
            response = 'Removing xxx'

        # Sends the response back to the channel
        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response or default_response
        )

    def send_rent_reminder(self, channel, rent_due_date):
        """ Handles rent reminders for each month. Reminds once a week before rent due (end of the month),
        reminds a second time four days before rent due, and finally three times the day before, five times
        day off and six times a day after.... Listen... I know it's a lot.. but people just don't pay rent...

        :param channel: Channel to post reminders to
        :param rent_due_date: Set the day of the month rent will be due
        :return:
        """

        relative_datetime = self.__check_datetime()

        if relative_datetime == 7:
            __send_reminder

        if relative_datetime == 4:
            __send_reminder

        if relative_datetime == #First date of the month:
            __reset_renters_not_paid



        # If 1 week out send a reminder to all members of self.renters_not_paid.

    def send_rent_reminder(self, channel,):
        """ Handles rent reminders for each month. Reminds once a week before rent due (end of the month),
        reminds a second time four days before rent due, and finally three times the day before, five times
        day off and six times a day after.... Listen... I know it's a lot.. but people just don't pay rent...

        :param channel: Channel to post reminders to
        :return:
        """

        right_now = datetime.datetime.today()

        # If everyone has paid for this month we're good to go, cut it here!
        if not self.renters_not_paid and right_now < self.first_day_of_next_month:
            return None

        # If everyone has paid and we're in a new month, reset all our relative vars and renters not paid.
        if not self.renters_not_paid and right_now > self.first_day_of_next_month:
            # Get last day of the month from today's date.
            relative_day = datetime.datetime.today()
            x , last_day_of_month_int = calendar.monthrange(relative_day.year, relative_day.month)

            self.last_day_of_relative_month = datetime.datetime(year=relative_day.year, month=relative_day.month, day=last_day_of_month_int)

            # Set relative datetime checks
            seven_days = datetime.timedelta(days=6,hours=7) # 5 oclock seven days
            four_days = datetime.timedelta(days=3,hours=7)  # 5 oclock three days

            seven_hours = datetime.timedelta(hours=7)

            nine_hours = datetime.timedelta(hours=9)
            twelve_hours = datetime.timedelta(hours=12)               # 12pm oclock
            seventeen_hours = datetime.timedelta(hours=17)            # 5pm oclock
            twenty_two_hours = datetime.timedelta(hours=22)           # 10pm oclock

            # One Day
            one_day = datetime.timedelta(days=1)

            # Set first day of next month
            self.first_day_of_next_month = self.last_day_of_relative_month + one_day

            # Reset renters not paid
            self.__reset_renters_not_paid()

        # Check if ping within the set window and check if it has pinged already for the window
        # Seven day window
        if right_now > (self.last_day_of_relative_month - seven_days) < (self.last_day_of_relative_month - four_days) and not self.seven_days_ping:

            message = 'Rent due in seven days!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.seven_days_ping = True

        # Four day window
        if right_now > (self.last_day_of_relative_month - four_days) < (self.last_day_of_relative_month - seven_hours) and not self.four_days_ping:
            message = 'Rent due in four days!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.four_days_ping = True

        # Day before window
        if right_now > (self.last_day_of_relative_month - seven_hours) < (self.last_day_of_relative_month + nine_hours) and not self.one_days_ping:
            message = 'Rent due tomorrow!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.one_days_ping = True

        # Day of 9am ping
        if right_now > (self.last_day_of_relative_month + nine_hours) < (self.last_day_of_relative_month + twelve_hours) and not self.nine_day_of_ping:
            message = 'Rent due today!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.nine_day_of_ping = True

        # Day of 12pm ping
        if right_now > (self.last_day_of_relative_month + twelve_hours) < (self.last_day_of_relative_month + seventeen_hours) and not self.twelve_day_of_ping:
            message = 'Rent due today plzzz!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.twelve_day_of_ping = True

        # Day of 5pm ping
        if right_now > (self.last_day_of_relative_month + seventeen_hours) < (self.last_day_of_relative_month + twenty_two_hours) and not self.five_day_of_ping:
            message = 'R3nt duee rn!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.five_day_of_ping = True

        # Day of 10pm ping
        if right_now > (self.last_day_of_relative_month + twenty_two_hours) and not self.ten_day_of_ping:
            message = 'Okay.. seriously pay rent!'
            self.__send_reminder(channel=channel, reminder_message=message)
            self.ten_day_of_ping = True


        # If not everyone has paid and we're in a new month, uh oh! We need to ping them a bunch every day till they pay
        if self.renters_not_paid and right_now > self.first_day_of_next_month:

            # if we're in a new day, reset pings and relative times!
            if right_now > self.end_of_relative_today:
                self.__reset_emergency_pings()

            # If
            if right_now.hour > self.relative_today_nine_am and not self.relative_today_nine_am_ping:
                message = 'Rent is pass due, please pay!'
                self.__send_reminder(channel=channel, reminder_message=message)
                self.relative_today_nine_am_ping = True



            pass
            # Look at today's hour if today's
            # if right_now.hour



        return None

    def __send_reminder(self, channel, reminder_message):
        # Check renters_not_paid0
        # Send one message @ing all users in that dictionary
        list_of_renters_not_paid = self.renters_not_paid.keys()
        users_with_tag = []

        for user in list_of_renters_not_paid:
            users_with_tag.append('<@' + user +'> ')

        users_with_ping = ' '.join(users_with_tag)

        users_with_reminder_message = users_with_ping + reminder_message

        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=users_with_reminder_message
        )

        print(f'Reminder sent: {users_with_reminder_message}')
        return None

    def __reset_renters_not_paid(self):
        # Reset the renters_not_paid dict by copying self.renters
        self.renters_not_paid = self.renters.copy()

        # Reset standard pings
        self.seven_days_ping = False
        self.four_days_ping = False
        self.one_days_ping = False
        self.nine_day_of_ping = False
        self.twelve_day_of_ping = False
        self.five_day_of_ping = False
        self.ten_day_of_ping = False

        # Reset daily emergency pings
        return None

    def __reset_emergency_pings(self):
        """ Resets relative times and pings for the daily four pings that will be sent to slack if someone hasn't paid
        past the due date.
        :return: None
        """

        # relative times
        self.relative_today = datetime.datetime.today()
        self.end_of_relative_today = self.relative_today.replace(hour=23, minute=59, second=59, microsecond=999999, )

        # relative times for pings
        self.relative_today_nine_am = self.relative_today.replace(hour=9, minute=0, second=0, microsecond=0, )
        self.relative_today_twelve_pm = self.relative_today.replace(hour=12, minute=0, second=0, microsecond=0, )
        self.relative_today_five_pm = self.relative_today.replace(hour=17, minute=0, second=0, microsecond=0, )
        self.relative_today_ten_pm = self.relative_today.replace(hour=22, minute=0, second=0, microsecond=0, )

        # ping flags
        self.relative_today_nine_am_ping = False
        self.relative_today_twelve_pm_ping = False
        self.relative_today_five_pm = False
        self.relative_today_ten_pm = False

        print('emergency Pings reset')
        return None

    def run(self):
        if self.slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            self.starterbot_id = self.slack_client.api_call("auth.test")["user_id"]
            while True:
                command, channel = self.parse_bot_commands(self.slack_client.rtm_read())
                if command:
                    self.handle_command(command, channel)
                # self.send_rent_reminder()
                time.sleep(self.rtm_read_delay)
        else:
            print("Connection failed. Exception traceback printed above.")


if __name__ == "__main__":
    bot = LilMoHouseBot()
    bot.run()

