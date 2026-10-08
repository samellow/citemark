# Restrict name and email changes

**Note:**

This feature is only available to organization owners and administrators.

## Restrict name changes

By default, any user can change their name. You can instead prevent users from changing their name. This setting is especially useful if user names are managed via an external source, and synced into Zulip via the Zulip API, LDAP or another method.

 **Tip:** Organization administrators can always change anyone’s
name.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **User identity**, select **Prevent users from changing their
name**.
5. Click **Save changes**.

## Restrict email changes

By default, any user can change their email address. However, you can instead prevent users from changing their email address. This setting is especially useful for organizations that are using LDAP or another single sign-on solution to manage user emails.

 **Tip:** Organization administrators can always change their own email
address.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **User identity**, select **Prevent users from changing their
email address**.
5. Click **Save changes**.

## Require unique names

You can require users to choose unique names when joining your organization, or changing their name. This helps prevent accidental creation of duplicate accounts, and makes it harder to impersonate other users.

When you turn on this setting, users who already have non-unique names are not required to change their name.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **User identity**, select **Require unique names**.
5. Click **Save changes**.