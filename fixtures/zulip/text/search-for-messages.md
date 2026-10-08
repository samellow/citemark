# Searching for messages

It’s easy to find the right conversation with Zulip’s powerful search. When you find the message you were looking for, go directly to its topic for full context.

Whenever you need a reminder of the search filters that Zulip offers, check out
the convenient **search filters** reference
in the Zulip web and desktop apps.

## Search for messages

**Desktop/Web:**

1. Click the **search** () icon in the top bar to open the search box.
2. Type your query, and press `Enter`.

 **Keyboard tip:** You can also use the `/` or `Ctrl` + `K`
keyboard shortcut to start searching messages.

**Mobile:**

1. Tap the **menu** () tab in the bottom right corner of the app.
2. Tap  **Search**.
3. Type your query, and tap **search** or
 on your device’s
keyboard.

## Keyword search

Zulip lets you search messages and topics by keyword. For example:

- `new logo`: Search for messages with both `new` and `logo` in the message or
its topic.
- `"new logo"`: Search for messages with the phrase “`new logo`” in the message
or its topic.

Some details to keep in mind:

- Keywords are case-insensitive, so `wave` will also match `Wave`.
- Zulip will find messages containing similar keywords (keywords with the same
stem), so, e.g., `wave` will match `waves` and `waving`.
- Zulip search ignores very common words like `a`, `the`, and about 100 others.
- Emoji in messages (but not emoji
reactions) are included in searches, so if you search
for `thumbs_up`, your results will include messages with the `:thumbs_up:` emoji (👍).

## Search filters

Zulip also offers a wide array of search filters, which can be used on their own, or in combination with keywords. For example:

- `channel:design`: Navigate to **#design**.
- `channel:design logo`: Search for the keyword `logo` within **#design**.
- `channel:design has:image new logo`: Search for messages in **#design** that
include an image and contain the keywords `new` and `logo`. The keywords can
appear in the message itself or its topic.

 **Tip:** As you start typing into the search box, Zulip will suggest search filters
you can use.

### Search by location

Sometimes you know approximately where the message you are looking for was sent. Zulip offers the following filters based on the location of the message.

- `channel:design`: Search within the channel **#design**.
- `channel:design topic:"new logo"`: Search within the topic “new logo” in **#design**.
- `topic:"new logo"`: Search within the topic “new logo” in all subscribed
channels.
- `is:dm`: Search all your direct messages.
- `dm:Bo Lin`: Search 1-on-1 direct messages between you and Bo.
- `dm:Bo Lin, Elena García`: Search group direct messages
between you, Bo, and Elena.
- `dm-including:Bo Lin`: Search all direct message conversations
(1-on-1 and group) that include you and Bo, as well as any other users.
- `channels:archived`: Search the messages you received in archived
channels.

### Search shared history

To avoid cluttering your search results, by default, Zulip searches just the
messages you received. You can use the `channel:` filter, and some `channels:`
filters, to search additional messages.

- `channels:public`: Search messages in all
public and
web-public channels.
- `channels:web-public`: Search messages in all
web-public channels in the organization,
including channels you are not subscribed to.
- `channel:design`: Search all messages in **#design**, including messages sent
before you were a subscriber.

### Search by sender

- `sender:Elena García`: Search messages sent by Elena.
- `sender:me`: Search messages you’ve sent.

 **Tip:** You can also access all messages someone has sent via their **user
card**.

### Search for attachments or links

- `has:link`: Search messages that contain URLs.
- `has:attachment`: Search messages that contain an uploaded
file.
- `has:image`: Search messages that contain uploaded or linked images or videos.

 **Tip:** You can also view all the files you
have uploaded or browse all the images and
videos in the current view.

### Search your important messages

- `is:alerted`: Search messages that contain your alert
words. Messages are
included in the search results based on the alerts you had configured when you
received the message.
- `is:mentioned`: Search messages where you were
mentioned.
- `mentions:Elena García`: Search messages where Elena is
mentioned.
- `is:starred`: Search your starred messages.

### Search by message status

- `is:followed`: Search messages in followed topics.
- `is:resolved`: Search messages in resolved topics.
- `-is:resolved`: Search messages in unresolved topics.
- `is:unread`: Search your unread messages.
- `is:muted`: Search muted messages.
- `-is:muted`: Search only unmuted messages. By default,
both muted and unmuted messages are included in keyword search results.
- `has:reaction`: Search messages with emoji reactions.

### Search by message ID

Each message in Zulip has a unique ID, which is used for linking to a specific message. You can use the search bar to navigate to a message by its ID.

- `near:12345`: Show messages around the message with ID `12345`.
- `id:12345`: Show only message `12345`.
- `channel:design near:1` Show the oldest messages in the **#design** channel.

### Exclude filters

All of Zulip’s search filters can be negated to **exclude** messages matching
the specified rule. For example:

- `channel:design -is:resolved -has:image`: Search messages in unresolved
topics in the **#design** channel that don’t contain
images.

## Linking to search results

When you search Zulip, the URL shown in the address bar of the Zulip web app is a
permanent link to your search. You can share this link with others, and they
will see *their own* search results for your query.

## Search filters reference

A summary of the search filters above is available in the Zulip app.

**Desktop/Web:**

1. Click on the **help menu** () icon in the upper right corner of the app.
2. Select **Search filters**.