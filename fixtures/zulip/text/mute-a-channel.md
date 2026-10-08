# Mute or unmute a channel

Zulip lets you mute topics and channels to avoid receiving notifications for messages
you are not interested in. Muting a channel effectively mutes all topics in
that channel. You can also manually **mute** a topic in an unmuted channel, or
**unmute** a topic in a muted channel.

In unmuted channels, muted topics are marked with in the left sidebar, inbox, and elsewhere. Muting has the following effects:

- Messages in muted topics do not generate notifications (including alert word notifications), unless you are mentioned.
- Messages in muted topics do not appear in the **Combined
feed** view or the mobile **Inbox** view.
- Muted topics appear in the **Recent conversations** view only if the **Include muted** filter is enabled.
- Unread messages in muted topics do not contribute to channel unread counts.
- Muted topics and channels are grayed out in the left sidebar of the desktop/web app, and in the mobile app.
- In the desktop/web app, muted topics are sorted to the bottom of their channel, and muted channels appear in a collapsible section at the bottom of their channel folder in the left sidebar.

To avoid missing messages you care about, you can choose which topics you’d like to unmute automatically:

- Topics you start.
- Topics you send a message to.
- Topics you participate in by sending a message, reacting with an emoji, or responding to a poll.

You can search muted messages using the `is:muted` search
filter, or exclude them
from search results with `-is:muted`.

**Note**: Some parts of the Zulip experience may start to degrade
if you receive more than a few hundred muted messages a day.

## Viewing muted channels

When you view the channel feed or list of topics for a muted channel, messages and topics are displayed just as they would be in an unmuted channel. Muted topics are hidden by default, just as in unmuted channels.

## Mute or unmute a channel

**Via left sidebar:**

1. Hover over a channel in the left sidebar.
2. Click on the **ellipsis** ().
3. Click **Mute channel** or **Unmute channel**.

**Via channel settings:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select **Channel settings**.
3. Select a channel.
4. Select the **Personal** tab on the right.
5. Under **Notification settings**, toggle **Mute channel**.

 **Tip:** You can also click on a channel name in the navigation bar at the top of the
app to access its settings, or use the **ellipsis** ()
next to the channel name in the left sidebar.

**Mobile:**

Access this feature by following the web app instructions in your mobile device browser.

Implementation of this feature in the mobile app is tracked on GitHub. If you’re interested in this feature, please react to the issue’s description with 👍.

## Reveal or hide muted channels

**Desktop/Web:**

1. In the left sidebar, scroll to the bottom of the list of channels in the folder you’re viewing.
2. Click **inactive or muted** or **muted** to toggle whether muted
channels are hidden. If you don’t see this button, there are no muted
channels.

## Managing muted channels

Zulip works best when most of the messages you receive are not muted. If you find yourself muting a lot of channels, consider unsubscribing from public channels you’ve muted. You can always re-subscribe if you need to, view the channel feed without subscribing, or search for messages in all public channels.