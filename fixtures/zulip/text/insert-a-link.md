# Insert a link

In Zulip, you can insert a named link using Markdown formatting. In addition, Zulip automatically creates links for you when you enter:

- A URL
- A reference to a channel, topic, or specific message (see also Link to a message or conversation)
- Text that matches a custom linkifier set up by your organization

## Insert a link

**Via paste:**

1. Open the compose box.
2. Select the text you want to linkify.
3. Paste a URL to turn the selected text into a named link.

 **Keyboard tip:** You can also use `Ctrl` + `Shift` + `L`
to insert link formatting.

**Via compose box button:**

1. Open the compose box.
2. Select the text you want to linkify.
3. Click the **link** () icon at the
bottom of the compose box.
4. Replace `url` with a valid URL.

 **Keyboard tip:** You can also use `Ctrl` + `Shift` + `L`
to insert link formatting.

**Via Markdown:**

1. Open the compose box.
2. To create a named link, use `[ ]` around the link text, and `( )` around the
URL: `[Link text](URL)`.

 **Keyboard tip:** You can also use `Ctrl` + `Shift` + `L`
to insert link formatting.

## Examples

### What you type

```
Named link: [Zulip homepage](zulip.com)
A URL (links automatically): zulip.com
Channel link: #**channel name**
Topic link: #**channel name>topic name**
Message link: #**channel name>topic name@123**
Custom linkifier: For example, #2468 can automatically link to an issue in your tracker.
```