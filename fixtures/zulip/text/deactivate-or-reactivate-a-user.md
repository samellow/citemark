# Deactivate or reactivate a user

## Deactivating a user

**Note:**

This feature is only available to organization owners and administrators.

When you deactivate a user:

- The user will be immediately logged out of all Zulip sessions, including desktop, web and mobile apps.
- The user’s credentials for logging in will no longer work, including password login and any other login options enabled in your organization.
- The user’s bots will be deactivated.
- Email invitations and invite links created by the user will be disabled.
- Other users will be able to see that the user has been deactivated (e.g., on their user card). In sidebars and elsewhere, a user’s availability will be replaced with a deactivated icon ().
- Even if your organization allows users to join without an invitation, this user will not be able to rejoin with the same email account.
- You can choose whether to delete the user’s name, profile picture, and messages they’ve sent (e.g., their DMs or channel messages).

**Note:**

You must go through the deactivation process below to fully remove a user’s access to your Zulip organization. Changing a user’s password or removing their single sign-on account will not log them out of their open Zulip sessions, or disable their API keys.

### Deactivate a user

**Via user profile:**

1. Hover over a user’s name in the right sidebar.
2. Click on their avatar or the **ellipsis** () to the right of their name to open their **user card**.
3. Click on the **ellipsis** () in the user card.
4. Click **Manage this user**.
5. Click **Deactivate user** at the bottom of the **Manage user** menu.
6. *(optional)* Select **Notify this user by email?** if desired, and enter a
custom comment to include in the notification email.
7. Choose whether to delete the user’s name, profile picture, and messages they’ve sent (e.g., their DMs or channel messages).
8. Approve by clicking **Deactivate**.

 **Tip:** You can also access the **Manage user** tab by clicking the **pencil and
paper** () icon at the top of the user
profile.

**Via organization settings:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Users**.
4. In the **Actions** column, click the **deactivate user** ()
icon for the user you want to deactivate.
5. *(optional)* Select **Notify this user by email?** if desired, and enter a
custom comment to include in the notification email.
6. Choose whether to delete the user’s name, profile picture, and messages they’ve sent (e.g., their DMs or channel messages).
7. Approve by clicking **Deactivate**.

 **Tip:** Organization administrators cannot deactivate organization owners.

## Reactivating a user

**Note:**

This feature is only available to organization owners and administrators.

A reactivated user will have the same role, channel subscriptions, user group memberships, and other settings and permissions as they did prior to deactivation. They will also have the same API key and bot API keys, but their bots will be deactivated until the user manually reactivates them again.

### Reactivate a user

**Via organization settings:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Users**.
4. Select the **Deactivated** tab.
5. In the **Actions** column, click the **reactivate user** () icon for the user you want to reactivate.

**Via user profile:**

1. Click on a user’s profile picture or name on a message they sent
to open their **user card**.
2. Click **View profile**.
3. Select the **Manage user** tab.
4. Click **Reactivate user** at the bottom of the **Manage user** menu.
5. Approve by clicking **Confirm**.

 **Tip:** You can also access the **Manage user** tab by clicking the **pencil and
paper** () icon at the top of the user
profile.

 **Tip:** You may want to review and adjust
the reactivated user’s channel subscriptions.