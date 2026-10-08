# Restrict moving messages

**Note:**

Organization admins can always edit message topics and move topics between channels via the API.

Zulip lets you configure who can edit message topics and move topics between channels. These permissions can be granted to any combination of roles, groups, and individual users.

In addition to granting organization-wide permissions, you can configure permissions for each channel. For example, you could allow the “engineering” group to move messages just in the #engineering channel.

In general, allowing all organization members to edit message topics is highly recommended because:

- It allows the community to keep conversations organized, even if some members are still learning how to use topics effectively.
- It makes it possible to fix a typo in the topic of a message you just sent.

You can let users edit topics without a time limit, or prohibit topic editing on older messages to avoid potential abuse. The time limit will never apply to administrators and moderators.

Permissions for moving messages between channels can be configured separately.

## Configure who can edit topics in any channel

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Moving messages**, configure **Who can edit topics in any channel**.
5. Click **Save changes**.

## Configure who can edit topics in a specific channel

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Select a channel.
5. Select the **Permissions** tab on the right.
6. Under **Moderation permissions**, configure **Who can move messages inside this
channel**.
7. Click **Save changes**.

 **Tip:** You can also click on a channel name in the navigation bar at the top of the
app to access its settings, or use the **ellipsis** ()
next to the channel name in the left sidebar.

## Set a time limit for editing topics

 **Tip:** The time limit you set will not apply to administrators and moderators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Moving messages**, configure **Time limit for editing topics**.
5. Click **Save changes**.

## Configure who can move messages out of any channel

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Moving messages**, configure **Who can move messages out of any channel**.
5. Click **Save changes**.

## Configure who can move messages to another channel from a specific channel

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Select a channel.
5. Select the **Permissions** tab on the right.
6. Under **Moderation permissions**, configure **Who can move messages out of this
channel**.
7. Click **Save changes**.

## Set a time limit for moving messages between channels

 **Tip:** The time limit you set will not apply to administrators and moderators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Moving messages**, configure **Time limit for  moving messages
between channels**.
5. Click **Save changes**.