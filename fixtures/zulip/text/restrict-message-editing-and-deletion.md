# Restrict message editing and deletion

**Note:**

This feature is only available to organization owners and administrators.

Zulip lets you separately configure permissions for editing and deleting messages, and you can set time limits for both actions. Regardless of the configuration you select, message content can only ever be modified by the original author.

Note that if a user can edit a message, they can also “delete” it by removing all the message content. This is different from proper message deletion in two ways: the original content will still show up in message edit history, and will be included in data exports. Deletion permanently (and irretrievably) removes the message from Zulip.

## Configure message editing permissions

 **Tip:** Users can only edit their own messages.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Message editing**:
  - Toggle **Allow message editing**.
  - Configure **Time limit for editing messages**.
5. Click **Save changes**.

## Configure message deletion permissions

These permissions can be granted to any combination of roles, groups, and individual users.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Message deletion**:
  - Configure **Who can delete any message**.
  - Configure **Who can delete their own messages everywhere**.
  - Configure **Time limit for deleting messages**. This time limit does not
apply to users who can delete any message.
  - Configure **Who can allow users to delete messages in channels they
administer**.
5. Click **Save changes**.

 **Tip:** A user can delete messages sent by bots that they
own just like messages they sent themself.

## Configure who can delete messages in a specific channel

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Select a channel.
5. Select the **Permissions** tab on the right.
6. Under **Moderation permissions**, configure **Who can delete any message in
this channel** and **Who can delete their own messages in this channel**.
7. Click **Save changes**.

 **Tip:** You can also click on a channel name in the navigation bar at the top of the
app to access its settings, or use the **ellipsis** ()
next to the channel name in the left sidebar.