# Writing tests for interactive bots

This page gives an overview of the unit testing framework for interactive bots.
Bots in the main
`python-zulip-api`
repository are required to include a reasonable set of unit tests, so that
future developers can easily refactor them.

**Note:**

Unit tests for bots make heavy use of mocking. If you want to get comfortable with mocking, mocking strategies, etc. you should check out our mocking guide.

## A simple example

Let’s have a look at a simple test suite for the
`helloworld` bot.

```
from zulip_bots.test_lib import StubBotTestCase
class TestHelpBot(StubBotTestCase):
    bot_name: str = "helloworld"
    def test_bot(self) -> None:
        dialog = [
            ('', 'beep boop'),
            ('help', 'beep boop'),
            ('foo', 'beep boop'),
        ]
        self.verify_dialog(dialog)
```
The `helloworld` bot replies with “beep boop” to every message @-mentioning it.  We
want our test to verify that the bot **actually** does that.

Note that our helper method `verify_dialog` simulates the conversation for us, and
we just need to set up a list of tuples with expected results.

The best way to learn about bot tests is to read all the existing tests in the
`bots` subdirectories.

## Testing your test

Once you have written a test suite, you want to verify that everything works as expected.

- To test a bot in Zulip’s bot directory:
`tools/test-bots <botname>`
- To run all bot tests: `tools/test-bots`

## Advanced testing

This section shows advanced testing techniques for more complicated bots that have
configuration files or interact with third-party APIs.
*The code for the bot testing library can be found here.*

### Testing bots with config files

Some bots, such as Giphy, support or require user configuration options to control how the bot works.

To test such a bot, you can use the following pattern:

```
with self.mock_config_info(dict(api_key=12345)):
    # self.verify_reply(...)
```
`mock_config_info()` replaces the actual step of reading configuration from the file
system and gives your test “dummy data” instead.

### Testing bots with internet access

Some bots, such as Giphy, depend on a third-party service, such as the Giphy web app, in order to work. Because we want our test suite to be reliable and not add load to these third-party APIs, tests for these services need to have “test fixtures”: sample HTTP request/response pairs to be used by the tests. You can specify which one to use in your test code using the following helper method:

```
with self.mock_http_conversation('test_fixture_name'):
    # self.assert_bot_response(...)
```
`mock_http_conversation(fixture_name)` patches `requests.get` and returns the data specified
in the file `fixtures/{fixture_name}.json`. Use the following JSON code as a skeleton for new
fixtures:

```
{
  "request": {
    "api_url": "http://api.example.com/",
    "params": {
    }
  },
  "response": {
  },
  "response-headers": {
  }
}
```
For an example, check out the giphy bot.

**Note:**

You can use requestbin or a similar tool to capture payloads from the service your bot is interacting with.

### Examples

Check out our bots to see examples of bot tests.