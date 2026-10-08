# Writing interactive bots

Zulip’s API has a powerful framework for interactive bots that react to messages in Zulip. This page will guide you through writing your own interactive bot.

- Installing a development version of the Zulip bots package
- Bot template
- Testing a bot’s output
- Troubleshooting

## Installing a development version of the Zulip bots package

This will provide convenient tooling for developing and testing your bot.

1. Clone the python-zulip-api repository: `git clone https://github.com/zulip/python-zulip-api.git`
2. Navigate into your cloned repository: `cd python-zulip-api`
3. Install all requirements in a Python virtualenv: `python3 ./tools/provision`
4. Run the command provided in the final output of the `provision` process to
enter the new virtualenv. The command will be of the form `source .../activate`.
5. You should now see the name of your virtualenv preceding your prompt (e.g.,
`(zulip-api-py3-venv)`).

**Note:**

`provision` installs the `zulip`, `zulip_bots`, and
`zulip_botserver` packages in developer mode. This enables you to
modify these packages and then run your modified code without
having to first re-install the packages or re-provision.

## Bot template

The only file required for a new bot is `<my-bot>.py`. It has the following
structure:

```
class MyBotHandler(object):
    '''
    A docstring documenting this bot.
    '''
    def usage(self):
        return '''Your description of the bot'''
    def handle_message(self, message, bot_handler):
        # add your code here
handler_class = MyBotHandler
```
The class name (in this case *MyBotHandler*) can be defined by you
and should match the name of your bot. To register your bot’s class,
adjust the last line `handler_class = MyBotHandler` to match your
class name.

Every bot must implement the `usage(self)` and `handle_message(self, message, bot_handler)` functions. They are described in detail in the
interactive bots API documentation.

All the files associated with a bot (e.g., tests, documentation, etc.) should be
placed in the same directory as `<my-bot>.py`.

## Testing a bot’s output

You can see how a bot reacts to a message without setting it up on a server,
using the `zulip-bot-shell` tool.

1. Install all requirements.
2. Run `zulip-bot-shell` to test one of the bots in `zulip_bots/bots`.

Example invocations:

```
> zulip-bot-shell converter
Enter your message: "12 meter yard"
Response: 12.0 meter = 13.12336 yard
> zulip-bot-shell -b ~/followup.conf followup
Enter your message: "Task completed"
Response: stream: followup topic: foo_sender@zulip.com
          from foo_sender@zulip.com: Task completed
```
Note that the `-b` (aka `--bot-config-file`) argument is for an optional third party
config file (e.g., \~/giphy.conf), which only applies to certain types of bots.

## Troubleshooting

### I modified my bot’s code, yet the changes don’t seem to have an effect

Ensure that you restarted the `zulip-run-bot` script.

### My bot won’t start

- Ensure that your API config file is correct (download the config file from the server).
- Ensure that you bot script is located in `zulip_bots/bots/<my-bot>/`
- Are you using your own Zulip development server? Ensure that you run your bot outside the Vagrant environment.