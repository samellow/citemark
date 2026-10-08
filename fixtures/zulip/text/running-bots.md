# Running interactive bots

Zulip’s API has a powerful framework for interactive bots that react to messages in Zulip. You can write and run a custom bot, or run an existing Zulip bot.

## Running a bot

**Note:**

Please be considerate when testing experimental bots on public servers such as chat.zulip.org.

You’ll need:

- An account in a Zulip organization (e.g., the Zulip development community, or a Zulip organization on your own development or production server).
- A computer where you’re running the bot from.

**Existing bot:**

1. Create a bot, making sure to select
**Generic bot** as the **Bot type**.
2. Download the bot’s `zuliprc` file.
3. Use the following command to install the
`zulip_bots` Python package:
`pip3 install zulip_bots`
4. Use the following command to start the bot process *(replacing `<bot-name>`
with the bot’s name from the
Zulip bots directory
and `~/path/to/zuliprc` with the path to the `zuliprc` file you downloaded above)*:
`zulip-run-bot <bot-name> --config-file ~/path/to/zuliprc`
5. Check the output of the command above to make sure your bot is running. It should include the following line: `INFO:root:starting message handling...`
6. Test your setup by starting a new direct message with the bot or mentioning the bot on a channel.

**Custom bot:**

1. Write the code for your custom bot, and note the path
to the `<my-bot>.py` file you created.
2. Create a bot, making sure to select
**Generic bot** as the **Bot type**.
3. Download the bot’s `zuliprc` file.
4. Use the following command to install the
`zulip_bots` Python package:
`pip3 install zulip_bots`
5. Use the following command to start the bot process *(replacing
`~/path/to/my_bot.py` with the path to your bot file and
`~/path/to/zuliprc` with the path to the `zuliprc` file you downloaded above)*:
`zulip-run-bot ~/path/to/my_bot.py --config-file ~/path/to/zuliprc` If your bot requires a third-party configuration file, you can specify
it with the `--bot-config-file` option.
6. Check the output of the command above to make sure your bot is running. It should include the following line: `INFO:root:starting message handling...`
7. Test your setup by starting a new direct message with the bot or mentioning the bot on a channel.

**Note:**

To use the latest development version of the `zulip_bots` package, follow
these steps.

You can now play around with the bot and get it configured the way you like. Eventually, you’ll probably want to run it in a production environment where it’ll stay up, by deploying it on a server using the Zulip Botserver.