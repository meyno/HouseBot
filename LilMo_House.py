""" Lil Mo is a slack bot that takes input from slack and executes automation scripts
"""

import time
import datetime
import re
from slackclient import SlackClient
import json
import calendar
from bs4 import BeautifulSoup
from selenium import webdriver
import dateutil.parser

class LilMoHouseBot:

    def __init__(self, saved_state=False):

        # TODO: 5. Create a time tracking object that takes in rent due date and calculates all the needed relative times to interface with the Bot object class.
        # TODO: 3. Save state when using shutdown cmd and allow to open last state when starting up.
        #  TODO: 1. Scrape web for chores/parking spot each monday/and with call cmd.
        # TODO: 2. Track stats on who pays rent the fastest with a rent_stats cmd.
        # TODO: 4. Allow for a list of Admins.
        # TODO: 6. Use onion style architecture to allow cmds to be imported via driver. Would need big overhaul...

        # Yes, we wana run.
        self.bot_run = True

        # Open config and grab the json file
        with open('config.json') as json_data_file:
            data = json.load(json_data_file)

        # Instantiate Slack client
        slack_bot_token = data['SlackBotToken']
        self.slack_client = SlackClient(slack_bot_token)

        # Grab slack channels for bot to post to
        self.list_of_channels = data["channels"]

        # Grab the channel admin
        self.bot_admin = data["admin"]

        # Grab sel driver location
        self.sel_driver_path = data["seldriver"]

        # Grab people names
        self.usernames = data["usernames"]

        # starterbot's user ID in Slack: value is assigned after the bot starts up
        self.starterbot_id = None

        # Set relative datetime checks
        self.seven_days = datetime.timedelta(days=6, hours=7)  # 5 oclock seven days
        self.four_days = datetime.timedelta(days=3, hours=7)  # 5 oclock three days

        self.seven_hours = datetime.timedelta(hours=7)

        self.nine_hours = datetime.timedelta(hours=9)
        self.twelve_hours = datetime.timedelta(hours=12)  # 12pm oclock
        self.seventeen_hours = datetime.timedelta(hours=17)  # 5pm oclock
        self.twenty_two_hours = datetime.timedelta(hours=22)  # 10pm oclock

        # If we have a saved_state then we'll get all our needed vars from that state.
        if saved_state:
            self.__read_saved_state()

        # Else let's set them up
        else:
            # Set up structures for tracking renters, renters paid, and renters not paid. Grabbing renters from config.
            self.renters = data["users"]
            self.renters_paid = {}
            self.renters_not_paid = {}

            # Set all our relative times and ping flags for this month
            self.__reset_relative_times_and_pings()
            self.__reset_emergency_times_and_pings()


        # TODO: Add chore tracking for state saves?
        self.__reset_chore_pings()

        # constants
        self.rtm_read_delay = 1 # 1 second delay between reading from RTM
        self.command_keyword = "-run"
        self.input_keyword = '-in'
        self.help_keyword = '-help'
        self.mention_regex = "^<@(|[WU].+?)>(.*)"

        # cmd list
        self.command_list = ['paid', 'not_paid', 'show_paid', 'show_not_paid', 'shutdown']

        # INIT PRINTS

        print(self.renters)
        print(self.renters_paid)
        print(self.renters_not_paid)

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
                    return message, event["channel"], event["user"]
        return None, None, None

    def parse_direct_mention(self, message_text):
        """
            Finds a direct mention (a mention that is at the beginning) in message text
            and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(self.mention_regex, message_text)
        # the first group contains the username, the second group contains the remaining message
        return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

    def handle_command(self, command, channel, user):
        """
            Executes bot command if the command is known
        """
        # Default response is help text for the user
        default_response = "Not sure what you mean. Try *{}*.".format(self.command_keyword)

        # Finds and executes the given command, filling in response
        response = None

        if command.startswith(self.command_keyword + ' paid'):
            if self.__check_if_admin(user):
                response = self.__cmd_remove_renter_from_renters_not_paid(command)
            else:
                response = 'Admin cmd only... sorry.'

        if command.startswith(self.command_keyword + ' not_paid'):
            if self.__check_if_admin(user):
                response = self.__cmd_add_renter_to_renters_not_paid(command)
            else:
                response = 'Admin cmd only... sorry.'

        if command.startswith(self.command_keyword + ' shutdown'):
            if self.__check_if_admin(user):
                response = self.__cmd_shutdown()
            else:
                response = 'Admin cmd only... sorry.'

        if command.startswith(self.command_keyword + ' show_paid'):
            response = self.__cmd_show_renters_paid()
            if not response:
                response = 'No one has paid!'

        if command.startswith(self.command_keyword + ' show_not_paid'):
            response = self.__cmd_show_renters_not_paid()
            if not response:
                response = 'Everyone has paid!'

        if command == self.help_keyword:
            response = f"Here's a list of commands {self.command_list}"

        # Sends the response back to the channel
        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response or default_response
        )

    def chores_reminder(self, channels,):

        # If today is monday and we haven't pinged about chores, then ping about chores
        if datetime.date.today().isoweekday() == 1 and not self.chore_ping:
            self.__send_chores_reminder(channels)

        # If we've sent out a ping and it isn't monday, reset the ping
        if datetime.date.today().isoweekday() != 1 and self.chore_ping:
            self.__reset_chore_pings()

        return None

    def rent_reminder(self, channel,):
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
            self.__reset_relative_times_and_pings()
            self.__reset_emergency_times_and_pings()

        # Check if ping within the set window and check if it has pinged already for the window
        self.__check_to_send_message(right_now, channel)

        # If not everyone has paid and we're in a new month, uh oh! We need to ping them a bunch every day till they pay
        if self.renters_not_paid and right_now > self.first_day_of_next_month:

            # If we're in a new day, reset emergency pings and relative times!
            if right_now > self.end_of_relative_today:
                self.__reset_emergency_times_and_pings()

            # If we're still in the same day, let's check to see if we should send a reminder ping out.
            self.__check_to_send_emergency_message()

        return None

    def save_state(self):

        state_dict = {

            "renters": self.renters,
            "renters_paid": self.renters_paid,
            "renters_not_paid": self.renters_not_paid,
            "last_day_of_relative_month": self.last_day_of_relative_month,
            # Reminder info
            "first_day_of_next_month": self.first_day_of_next_month,
            "seven_days_ping": self.seven_days_ping,
            "four_days_ping": self.four_days_ping,
            "one_days_ping": self.one_days_ping,
            "nine_day_of_ping": self.nine_day_of_ping,
            "twelve_day_of_ping": self.twelve_day_of_ping,
            "five_day_of_ping": self.five_day_of_ping,
            "ten_day_of_ping": self.ten_day_of_ping,

            # Emergency info
            "relative_today": self.relative_today,
            "end_of_relative_today": self.end_of_relative_today,
            "relative_today_nine_am": self.relative_today_nine_am,
            "relative_today_twelve_pm": self.relative_today_twelve_pm,
            "relative_today_five_pm": self.relative_today_five_pm,
            "relative_today_ten_pm": self.relative_today_ten_pm,
            "relative_today_nine_am_ping": self.relative_today_nine_am_ping,
            "relative_today_twelve_pm_ping": self.relative_today_twelve_pm_ping,
            "relative_today_five_pm_ping": self.relative_today_five_pm_ping,
            "relative_today_ten_pm_ping":  self.relative_today_ten_pm_ping

            # Could add in chore information below

        }

        with open('StateSaves/botstate.json', 'w') as outfile:
            json.dump(state_dict, fp=outfile, indent=4, sort_keys=True, default=str)

        return None

    def __read_saved_state(self):

        with open('StateSaves/botstate.json') as infile:
            new_state = json.load(infile)

            # Renters
            self.renters = new_state["renters"]
            self.renters_paid = new_state["renters_paid"]
            self.renters_not_paid = new_state["renters_not_paid"]

            # Rent reminder rel times
            self.last_day_of_relative_month = self.__dict_str_to_datetime(new_state, "last_day_of_relative_month")
            self.first_day_of_next_month = self.__dict_str_to_datetime(new_state, "first_day_of_next_month")

            # Pings
            self.seven_days_ping = new_state["seven_days_ping"]
            self.four_days_ping = new_state["four_days_ping"]
            self.one_days_ping = new_state["one_days_ping"]
            self.nine_day_of_ping = new_state["nine_day_of_ping"]
            self.twelve_day_of_ping = new_state["twelve_day_of_ping"]
            self.five_day_of_ping = new_state["five_day_of_ping"]
            self.ten_day_of_ping = new_state["ten_day_of_ping"]

            # Emergency info
            self.relative_today = self.__dict_str_to_datetime(new_state, "relative_today")
            self.end_of_relative_today = self.__dict_str_to_datetime(new_state, "end_of_relative_today")
            self.relative_today_nine_am = self.__dict_str_to_datetime(new_state, "relative_today_nine_am")
            self.relative_today_twelve_pm = self.__dict_str_to_datetime(new_state, "relative_today_twelve_pm")
            self.relative_today_five_pm = self.__dict_str_to_datetime(new_state, "relative_today_five_pm")
            self.relative_today_ten_pm = self.__dict_str_to_datetime(new_state, "relative_today_ten_pm")

            # Pings
            self.relative_today_nine_am_ping = new_state["relative_today_nine_am_ping"]
            self.relative_today_twelve_pm_ping = new_state["relative_today_twelve_pm_ping"]
            self.relative_today_five_pm_ping = new_state["relative_today_five_pm_ping"]
            self.relative_today_ten_pm_ping = new_state["relative_today_ten_pm_ping"]

    def __dict_str_to_datetime(self, a_dict, key):
        return dateutil.parser.parse(a_dict[key])
        # return datetime.datetime.strptime(a_dict[key], '%Y-%m-%d %H:%M%S')

    def __check_to_send_message(self, current_datetime, channels):
        """ Check if ping within the set window and check if it has pinged already for the window. Send message otherwise.

        :param current_datetime: The current datetime use to compare against conditions if ping should be sent.
        :param channel: Channel to send reminder to.
        :return: None
        """

        right_now = current_datetime

        # Seven day window
        if right_now > (self.last_day_of_relative_month - self.seven_days) < (self.last_day_of_relative_month - self.four_days) and not self.seven_days_ping:

            message = 'Rent due in seven days!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.seven_days_ping = True

        # Four day window
        if right_now > (self.last_day_of_relative_month - self.four_days) < (self.last_day_of_relative_month - self.seven_hours) and not self.four_days_ping:
            message = 'Rent due in four days!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.four_days_ping = True

        # Day before window
        if right_now > (self.last_day_of_relative_month - self.seven_hours) < (self.last_day_of_relative_month + self.nine_hours) and not self.one_days_ping:
            message = 'Rent due tomorrow!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.one_days_ping = True

        # Day of 9am ping
        if right_now > (self.last_day_of_relative_month + self.nine_hours) < (self.last_day_of_relative_month + self.twelve_hours) and not self.nine_day_of_ping:
            message = 'Rent due today!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.nine_day_of_ping = True

        # Day of 12pm ping
        if right_now > (self.last_day_of_relative_month + self.twelve_hours) < (self.last_day_of_relative_month + self.seventeen_hours) and not self.twelve_day_of_ping:
            message = 'Rent due today plzzz!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.twelve_day_of_ping = True

        # Day of 5pm ping
        if right_now > (self.last_day_of_relative_month + self.seventeen_hours) < (self.last_day_of_relative_month + self.twenty_two_hours) and not self.five_day_of_ping:
            message = 'R3nt duee rn!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.five_day_of_ping = True

        # Day of 10pm ping
        if right_now > (self.last_day_of_relative_month + self.twenty_two_hours) and not self.ten_day_of_ping:
            message = 'Okay.. seriously pay rent!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.ten_day_of_ping = True

        return None

    def __check_to_send_emergency_message(self, current_datetime, channels):

        right_now = current_datetime

        if right_now.hour > self.relative_today_nine_am and not self.relative_today_nine_am_ping:
            message = 'Rent is pass due, please pay!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.relative_today_nine_am_ping = True

        if right_now.hour > self.relative_today_twelve_pm and not self.relative_today_twelve_pm_ping:
            message = 'Rent is pass due, please pay!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.relative_today_twelve_pm_ping = True

        if right_now.hour > self.relative_today_five_pm and not self.relative_today_five_pm_ping:
            message = 'Rent is pass due, please pay!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.relative_today_nine_am_ping = True

        if right_now.hour > self.relative_today_ten_pm and not self.relative_today_ten_pm_ping:
            message = 'Rent is pass due, please pay!'
            self.__send_rent_reminder(channel_list=channels, reminder_message=message)
            self.relative_today_ten_pm_ping = True

    def __send_rent_reminder(self, channel_list, reminder_message):
        """ Check renters_not_paid. Send one message @ing all users in that dictionary

        :param channel_list: Channel list to send reminder to.
        :param reminder_message: Message to include after users have been @ed
        :return: None
        """

        list_of_renters_not_paid = self.renters_not_paid.keys()
        users_with_tag = []

        for user in list_of_renters_not_paid:
            users_with_tag.append('<@' + user +'> ')

        users_with_ping = ' '.join(users_with_tag)

        users_with_reminder_message = users_with_ping + reminder_message

        # Loop through channel_list to send reminder to channels
        for channel in channel_list:

            self.slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                text=users_with_reminder_message
            )

        print(f'Reminder sent: {users_with_reminder_message}')
        return None

    def __send_chores_reminder(self, channels):

        # Start the WebDriver and load the page
        wd = webdriver.Firefox(executable_path=self.sel_driver_path)
        wd.get("http://www.chorechart.xyz/")

        # Let's wait for this shit to show up
        time.sleep(5)

        # And grab the page HTML source
        html_page = wd.page_source
        wd.quit()

        # Now you can use html_page as you like
        soup = BeautifulSoup(html_page, "lxml")

        list_of_chore_doers = []

        # print(soup.prettify())
        for heading in soup.find_all('h3'):
            list_of_chore_doers.append(heading.text)

        dict_of_users = self.usernames

        # Loop over scraped users, get users names from dictonary to assemble @. Add chore name in front
        # and create single string.

        # Cleaning the scrapped data
        clean_list_of_chore_doers = []

        for scraped_people in list_of_chore_doers:
            clean_list_of_chore_doers.append(scraped_people.replace(' ', ''))

        clean_surfaces = clean_list_of_chore_doers[0]
        swipe_clean_floors = clean_list_of_chore_doers[1]
        trash_and_recycle = clean_list_of_chore_doers[2]
        clean_bathroom = clean_list_of_chore_doers[3]
        parking_spot = clean_list_of_chore_doers[4]

        clean_surfaces_cleaned = clean_surfaces.split("&")
        swipe_clean_floors_cleaned = swipe_clean_floors.split("&")
        trash_and_recycle_cleaned = trash_and_recycle.split("&")
        clean_bathroom_cleaned = clean_bathroom.split("&")
        parking_spot_cleaned = parking_spot.split("&")

        # Let's assemble the needed strings
        clean_surfaces_string = ''

        for users in clean_surfaces_cleaned:
            userid = dict_of_users.get(users)
            clean_surfaces_string += '<@' + userid + '> '

        clean_surfaces_string = '\nClean surfaces: ' + clean_surfaces_string

        swipe_clean_floors_string = ''

        for users in swipe_clean_floors_cleaned:
            userid = dict_of_users.get(users)
            swipe_clean_floors_string += '<@' + userid + '> '

        swipe_clean_floors_string = '\nClean floors: ' + swipe_clean_floors_string

        trash_and_recycle_string = ''

        for users in trash_and_recycle_cleaned:
            userid = dict_of_users.get(users)
            trash_and_recycle_string += '<@' + userid + '> '

        trash_and_recycle_string = '\nTrash and recycle: ' + trash_and_recycle_string

        clean_bathroom_string = ''

        for users in clean_bathroom_cleaned:
            userid = dict_of_users.get(users)
            clean_bathroom_string += '<@' + userid + '> '

        clean_bathroom_string = '\nClean bathroom: ' + clean_bathroom_string

        parking_spot_string = ''

        for users in parking_spot_cleaned:
            userid = dict_of_users.get(users)
            parking_spot_string += '<@' + userid + '> '

        parking_spot_string = '\nParking spot: ' + parking_spot_string

        chore_string = clean_surfaces_string + swipe_clean_floors_string + trash_and_recycle_string + clean_bathroom_string + parking_spot_string

        # Post to channels
        for channel in channels:

            self.slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                text=chore_string
            )

        self.chore_ping = True

    def __reset_relative_times_and_pings(self):
        # Get last day of the month from today's date.
        relative_day = datetime.datetime.today()
        x, last_day_of_month_int = calendar.monthrange(relative_day.year, relative_day.month)

        self.last_day_of_relative_month = datetime.datetime(year=relative_day.year, month=relative_day.month,
                                                            day=last_day_of_month_int)

        # One Day
        one_day = datetime.timedelta(days=1)

        # Set first day of next month
        self.first_day_of_next_month = self.last_day_of_relative_month + one_day

        # Reset standard pings
        self.seven_days_ping = False
        self.four_days_ping = False
        self.one_days_ping = False
        self.nine_day_of_ping = False
        self.twelve_day_of_ping = False
        self.five_day_of_ping = False
        self.ten_day_of_ping = False

        # Reset renters not paid
        self.__reset_renters_not_paid()

        print('Normal Pings and rel. times reset')
        return None

    def __reset_renters_not_paid(self):
        # Reset the renters_not_paid dict by copying self.renters
        self.renters_not_paid = self.renters.copy()
        return None

    def __reset_emergency_times_and_pings(self):
        """ Resets relative times and pings for the daily four pings that will be sent to slack if someone hasn't paid
        past the due date.
        :return: None
        """

        # relative times
        self.relative_today = datetime.datetime.today()
        self.end_of_relative_today = self.relative_today.replace(hour=23, minute=59, second=59,)

        # relative times for pings
        self.relative_today_nine_am = self.relative_today.replace(hour=9, minute=0, second=0, microsecond=0, )
        self.relative_today_twelve_pm = self.relative_today.replace(hour=12, minute=0, second=0, microsecond=0, )
        self.relative_today_five_pm = self.relative_today.replace(hour=17, minute=0, second=0, microsecond=0, )
        self.relative_today_ten_pm = self.relative_today.replace(hour=22, minute=0, second=0, microsecond=0, )

        # ping flags
        self.relative_today_nine_am_ping = False
        self.relative_today_twelve_pm_ping = False
        self.relative_today_five_pm_ping = False
        self.relative_today_ten_pm_ping = False

        print('Emergency Pings reset')
        return None

    def __reset_chore_pings(self):
        self.chore_ping = False

    def __check_if_admin(self, user):
        if user == self.bot_admin:
            return True
        else:
            return False

    def __cmd_add_renter_to_renters_not_paid(self, command):
        """ Adds user to the renters not paid dict

        :param command: Command to be parsed
        :return: string of the user name added
        """

        # First we need to parse the command to grab the user that is being requested to remove
        run, not_paid, user_mentioned = command.split()
        user_parsed = user_mentioned[2:11]  # parsing out the user tag with 2:11

        # Pop and add it onto renters_paid dict
        try:
            self.renters_not_paid.update({user_parsed: self.renters_paid.pop(user_parsed)})
            print(f'Removed from renters_paid : {self.renters_paid}')
            print(f'Added to renters_not_paid : {self.renters_not_paid}')
            return 'Renter added to renters not paid list'
        except KeyError:
            print('User does not exist in renters paid list')
            return 'User does not exist in renters paid list'

    def __cmd_remove_renter_from_renters_not_paid(self, command):
        """ Removes user from the renters not paid dict

        :param command: Command to be parsed
        :return: string of the user name removed
        """

        # First we need to parse the command to grab the user that is being requested to remove
        run, paid, user_mentioned = command.split()
        user_parsed = user_mentioned[2:11]  # parsing out the user tag with 2:11

        # Pop and add it onto renters_paid dict
        try:
            self.renters_paid.update({user_parsed: self.renters_not_paid.pop(user_parsed)})
            print(f'Added to renters_paid : {self.renters_paid}')
            print(f'Removed from renters_not_paid : {self.renters_not_paid}')
            return 'Renter removed from renters not paid list'
        except KeyError:
            print('User does not exist in renters not paid list')
            return 'User does not exist in renters_not_paid'

    def __cmd_show_renters_not_paid(self):
        return list(self.renters_not_paid.values())

    def __cmd_show_renters_paid(self):
        return list(self.renters_paid.values())

    def __cmd_shutdown(self):

        print("Shutting Down")
        self.save_state()
        print("State Saved")
        self.bot_run = False
        return "State saved, shutting down!"

    def run(self):
        if self.slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            self.starterbot_id = self.slack_client.api_call("auth.test")["user_id"]
            while self.bot_run:
                try:
                    command, channel, user = self.parse_bot_commands(self.slack_client.rtm_read())
                    if command:
                        self.handle_command(command, channel, user)
                    self.rent_reminder(self.list_of_channels)
                    self.chores_reminder(self.list_of_channels)
                except ConnectionResetError:
                    print('ConnectionResetError : Retrying connection')
                    self.slack_client.rtm_connect(with_team_state=False)
                finally:
                    log_time = datetime.datetime.now()
                    print('Log Time: ', log_time.day, log_time.hour, log_time.minute, log_time.second)
                    time.sleep(self.rtm_read_delay)
        else:
            print("Connection failed. Exception traceback printed above.")


if __name__ == "__main__":
    bot = LilMoHouseBot(saved_state=True)
    bot.run()



