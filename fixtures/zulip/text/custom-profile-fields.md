# Custom profile fields

**Note:**

This feature is only available to organization owners and administrators.

User cards show basic information about a user, and user profiles provide additional details. You can add custom profile fields to user cards and user profiles, making it easy for users to share information, such as their pronouns, job title, or team.

Zulip supports many types of profile fields, such as dates, lists of options, account links, and more. You can choose which custom profile fields to display on user cards. Custom profile fields can be optional or required.

You can configure
**External account** and **Short text** custom profile fields to be used for
@-mention suggestions. For example, users could
be mentioned by their GitHub or Mastodon usernames.

Zulip supports synchronizing custom profile fields from an external user database such as LDAP or SAML. See the authentication methods documentation for details.

## Add a custom profile field

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. Click **Add a new profile field**.
5. Fill out profile field information as desired, and click **Add**.
6. In the **Labels** column, click and drag the vertical dots to reorder the
list of custom profile fields.

## Edit a custom profile field

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **edit** ()
icon for the profile field you want to edit.
5. Edit profile field information as desired, and click **Save changes**.

## Delete a custom profile field

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **delete** () icon for the profile field you want to delete.
5. Approve by clicking **Confirm**.

## Reorder custom profile fields

Users will see custom profile fields in the specified order.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Labels** column, click and drag the vertical dots to reorder the
list of custom profile fields.

## Display custom fields on user card

Organizations may find it useful to display additional fields on the user card, such as pronouns, GitHub username, job title, team, etc.

All field types other than “Person” have a checkbox option that controls whether to display a custom field on the user card. There’s a limit to the number of custom profile fields that can be displayed at a time. If the maximum number of fields is already selected, all unselected checkboxes will be disabled.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **edit** ()
icon for the profile field you want to edit.
5. Toggle **Display on user card**.
6. Click **Save changes**.

 **Tip:** You can also choose which custom profile fields will be displayed by toggling
the checkboxes in the **Card** column of the **Custom profile fields** table.

## Make a custom profile field required

If a custom profile field is required, users who have left it blank will see a banner every time they open the Zulip web or desktop app prompting them to fill it out.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **edit** ()
icon for the profile field you want to edit.
5. Toggle **Required field**.
6. Click **Save changes**.

 **Tip:** You can also choose which custom profile fields are required by toggling the
checkboxes in the **Required** column of the **Custom profile fields** table.

## Use a custom profile field in @-mention suggestions

**External account** and **Short text** custom profile fields can be used for
@-mention suggestions.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **edit** ()
icon for the profile field you want to edit.
5. Toggle **Use in @-mention suggestions**.
6. Click **Save changes**.

## Configure whether users can edit custom profile fields

You can configure whether users in your organization can edit custom profile fields for their own account. For example, you may want to restrict editing if syncing profile fields from an employee directory.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom profile fields**.
4. In the **Actions** column, click the **edit** ()
icon for the profile field you want to configure.
5. Toggle **Users can edit this field for their own account**.
6. Click **Save changes**.

## Profile field types

Choose the profile field type that’s most appropriate for the requested information.

- **Date**: For dates (e.g., birthdays or work anniversaries).
- **Link**: For links to websites, including company-internal pages.
- **External account**: For linking to an external account (e.g., GitHub,
GitLab, LinkedIn, etc.). You can
configure this field to
be used for @-mention suggestions. Some
integrations (Bitbucket,
GitHub, GitLab,
Jira) use silent
mentions to refer to
users if a matching external account is configured.
- **Dropdown**: A dropdown with a list of predefined options (e.g.,
office location).
- **Pronouns**: What pronouns should people use to refer to the user? Pronouns
are displayed in user mention autocomplete
suggestions.
- **Paragraph**: For multiline responses (e.g., a user’s intro message).
- **Short text**: For one-line responses up to 50 characters (e.g., team name or
role in your organization). You can
configure this field to
be used for @-mention suggestions.
- **Users**: For selecting one or more users (e.g., manager or direct reports).