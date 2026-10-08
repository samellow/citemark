# Link to a message or conversation

Zulip makes it easy to share links to messages, topics, and channels. You can link from one Zulip conversation to another, or share links to Zulip conversations in issue trackers, emails, or other external tools.

## Link to a channel within Zulip

Channel links are automatically formatted as #channel name.

**Desktop/Web:**

1. Open the compose box.
2. Type `#` followed by a few letters from the channel name.
3. Pick the desired channel from the autocomplete.
4. Pick the top option from the autocomplete to link to the channel without selecting a topic.

 **Tip:** To link to the channel you’re composing to, type `#>`, and pick the
top option from the autocomplete.

In the web and desktop apps, when you paste a channel link into Zulip,
it’s automatically formatted as `#**channel name**`. You can use
`Ctrl` + `Shift` +
`V` to paste as plain text if you prefer.

You can create a channel link manually by typing `#**channel name**`.

## Link to a topic within Zulip

Topic links are automatically formatted as #channel > topic.

**Desktop/Web:**

1. Open the compose box.
2. Type `#` followed by a few letters from the channel name.
3. Pick the desired channel from the autocomplete.
4. Type a few letters from the topic name.
5. Pick the desired topic from the autocomplete.

 **Tip:** To link to a topic in the channel you’re composing to, type `#>`
followed by a few letters from the topic name, and pick the desired
topic from the autocomplete.

In the web and desktop apps, when you paste a topic link into Zulip, it’s
automatically formatted as `#**channel name>topic name**`. You can use
`Ctrl` + `Shift` +
`V` to paste as plain text if you prefer.

You can create a topic link manually by typing `#**channel name>topic name**`.

## Link to Zulip from anywhere

All URLs in Zulip are designed to be **shareable**, including:

- Links to messages, topics, and channels.
- Search URLs, though note that personal
filters (e.g., `is:followed`) will
be applied according to the user who’s viewing the URL.

In addition, links to messages, topics, and channels are **permanent**:

- Message links will still work even when the message is moved to another topic or channel, or if its topic is resolved. Zulip uses the same permanent link syntax when quoting a message.
- Topic links will still work even when the
topic is renamed, moved to another
channel, or
resolved.
 **Tip:** When some messages are moved out of a
topic and others are left in place,
links to that topic will follow the location of the message whose ID is
encoded in the topic URL (usually the first or last message in the topic).
- Channel links will still work even when a channel is renamed or archived.

When you copy a Zulip link in the web and desktop apps, and paste it anywhere that
accepts HTML formatting (e.g., your email, GitHub, docs, etc.), the link will be
formatted as it would be in Zulip (e.g., #channel > topic).
To paste the plain URL, you can paste without formatting (likely `Ctrl` +
`Shift` + `V` in your browser).

**Note:**

Due to a Safari quirk, pasting Zulip links from Safari into GitHub and some other apps may result in incorrect formatting. You can paste without formatting, or use a different browser.

### Get a link to a specific message

This copies to your clipboard a permanent link to the message, displayed in the context of its conversation. To preserve your reading status, messages won’t be automatically marked as read when you view a conversation via a message link.

In the web and desktop apps, when you paste a message link into the compose box, it gets automatically formatted to be easy to read:

`#**channel name>topic name@message ID**`
When you send your message, the link will appear as #channel > topic @ 💬.

**Desktop/Web:**

1. Hover over a message to reveal three icons on the right.
2. Click on the **ellipsis** ().
3. Click **Copy link to message**.

 **Keyboard tip:** You can also use `L` to copy a link to the selected message.

 **Tip:** If using Zulip in a browser, you can also click on the timestamp
of a message, and copy the URL from your browser’s address bar.

**Mobile:**

1. Press and hold a message until the long-press menu appears.
2. Tap **Copy link to message**.

In the web and desktop apps, when you paste a message link into Zulip,
it is automatically formatted for you. You can use
`Ctrl` + `Shift` +
`V` to paste as plain text if you prefer.

### Get a link to a specific topic

**Via message recipient bar:**

1. Click the **copy link to topic** () icon in the message
recipient bar.

 **Tip:** If using Zulip in a browser, you can also click on a topic name,
and copy the URL from your browser’s address bar.

**Via left sidebar:**

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Click **Copy link to topic**.

 **Tip:** If using Zulip in a browser, you can also click on a topic name,
and copy the URL from your browser’s address bar.

**Mobile:**

1. Press and hold a topic until the long-press menu appears.
2. Tap **Copy link to topic**.

### Get a link to a specific channel

**Desktop/Web:**

1. Hover over a channel in the left sidebar.
2. Click on the **ellipsis** ().
3. Click **Copy link to channel**.

**Mobile:**

1. Press and hold a channel until the long-press menu appears.
2. Tap **Copy link to channel**.

## View links to and from a conversation

Zulip can show you how a conversation is connected to others through links, making it easy to navigate between related discussions.

- **Links to** shows the conversations that messages in the current conversation
link to.
- **Linked from** shows the conversations whose messages link to the current
conversation.

**Desktop/Web:**

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Click **View links**.

The **View links** option appears only when a conversation has links to or from
it.

 **Tip:** These lists are built from messages Zulip has loaded in your current session,
so they may be incomplete until you have visited the relevant conversations.