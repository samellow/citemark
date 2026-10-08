# Move content to another channel

Zulip makes it possible to move messages, or an entire topic, to another channel. Organization administrators can configure who can move messages between channels.

To help others find moved content, you can have Notification Bot send automated notices to the source topic, the destination topic, or both. These notices include:

- A link to the source or destination topic.
- How many messages were moved, or whether the whole topic was moved.
- Who moved the content.

## Move a topic to another channel

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Select **Move topic**. If you do not see this option, you do not have permission
to move this topic.
4. Select the destination channel for the topic from the channels dropdown list.
5. *(optional)* Change the topic name.
6. Toggle whether automated notices should be sent.
7. Click **Confirm** to move the topic to another channel.

**Note**: When a topic is moved to a private channel with protected history,
messages in the topic will be visible to all the subscribers.

## Move messages to another channel

1. Hover over a message to reveal three icons on the right.
2. Click on the **ellipsis** ().
3. Select **Move messages**. If you do not see this option, you do not have permission
to move this message.
4. Select the destination channel from the channels dropdown list. If the channel input is disabled, you do not have permission to move this message to a different channel.
5. *(optional)* Change the topic name.
6. From the dropdown menu, select which messages to move.
7. Toggle whether automated notices should be sent.
8. Click **Confirm** to move the selected content to another channel.

**Note**: You cannot edit content of a message while changing its channel.

## Moving content to private channels

Access to messages moved to another channel will immediately be controlled by the access policies for the destination channel. Content moved to a private channel will thus appear to be deleted to users who are not subscribers of the destination channel.

Content moved to a private channel with protected history will only be accessible to users who both:

- Were subscribed to the *original* channel when the content was *sent*.
- Are subscribed to the *destination* channel when the content is *moved*.

## Moving content out of private channels

In private channels with protected history, Zulip determines whether to treat the entire topic as moved using the access permissions of the user requesting the topic move. This means that the automated notices sent by Notification Bot will report that the entire topic was moved if the requesting user moved every message in the topic that they can access, regardless of whether older messages exist that they cannot access.

Similarly, muted topics will be migrated to the new channel and topic if the requesting user moved every message in the topic that they can access.

This model ensures that the topic editing feature cannot be abused to determine any information about the existence of messages or topics that one does not have permission to access.