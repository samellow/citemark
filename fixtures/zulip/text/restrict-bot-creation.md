# Configure who can add bots

**Note:**

This feature is only available to organization owners and administrators.

Zulip lets you create three types of bots:

- **Incoming webhook bots**, which are limited to only sending messages into Zulip.
- **Generic bots**, which act like a normal user account.
- **Outgoing webhook bots**, which are generic bots that also receive
new messages via HTTPS POST requests.

You can configure who can create incoming webhook bots (which are more limited in what they can do), and who can create any bot. Both permissions can be assigned to any combination of roles, groups, and individual users.

**Note:**

These settings only affect new bots. Existing bots will not be deactivated.

## Configure who can create bots that can only send messages (incoming webhook bots)

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Other permissions**, configure **Who can create bots that send messages into Zulip**.
5. Click **Save changes**.

## Configure who can create any type of bot

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Other permissions**, configure **Who can create any bot**.
5. Click **Save changes**.