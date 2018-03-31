""" Lil Mo is a slack bot that takes input from slack and executes automation scripts
"""

import time
import re
from slackclient import SlackClient
import json


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

        # Sends the response back to the channel
        self.slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=response or default_response
        )

    def run(self):
        if self.slack_client.rtm_connect(with_team_state=False):
            print("Starter Bot connected and running!")
            # Read bot's user ID by calling Web API method `auth.test`
            self.starterbot_id = self.slack_client.api_call("auth.test")["user_id"]
            while True:
                command, channel = self.parse_bot_commands(self.slack_client.rtm_read())
                if command:
                    self.handle_command(command, channel)
                time.sleep(self.rtm_read_delay)
        else:
            print("Connection failed. Exception traceback printed above.")


if __name__ == "__main__":
    bot = LilMoHouseBot()
    bot.run()

