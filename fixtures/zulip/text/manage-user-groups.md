# Manage user groups

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to Zulip Cloud Standard or Zulip Cloud Plus.

User groups offer a flexible way to manage permissions in your organization. Most permissions in Zulip can be granted to any combination of roles, groups, and individual users.

Groups provide an easy way to refer to multiple users at once. You can:

- Mention a group of users, notifying everyone in the group as if they were personally mentioned.
- Compose a direct message to a user group. This automatically puts all the users in the group into the addressee field.
- Subscribe a user group to a channel. This individually subscribes all the users in the group.

## Create a user group

 **Tip:** You can modify the group’s name, description, and other settings after it
has been created.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select **Group settings**.
3. Click **Create user group** on the right, or click the **create new user group** ()
icon in the upper right.
4. Fill out the requested information, and click **Continue to add
members**.
5. Under **Add members**, enter groups and users you want to add. You can enter
a `#channel` to add all subscribers to the group. Click **Add**.
6. Click **Create** to create the group.

**Note**: You will only see the **Create user group** button if you have
permission to create user groups.

## Change a user group’s name or description

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **General** tab on the right.
6. Click the **change group info** ()
icon to the right of the user group, and enter a new name or description.
7. Click **Save changes**.

## Configure group permissions

**Note:**

Guests can never administer user groups, add anyone else to a group, or remove anyone else from a group, even if they belong to a group that has permissions to do so.

 **Tip:** Users who can add members to a group can always join the group.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **General** tab on the right.
6. Under **Group permissions**, configure **Who can administer this group**, **Who
can mention this group**, **Who can add members to this group**, **Who can remove
members from this group**, **Who can join this group**, and **Who can leave this group**.
7. Click **Save changes**.

## Add users to a group

**Note:**

You will see the options described only if you have permission to take this action.

**Via group settings:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **Members** tab on the right.
6. Under **Add members**, enter users you want to add. You can enter a `#channel` to add all subscribers to the group.
7. Click **Add**. Zulip will notify everyone who is added to the group.

**Via user profile:**

1. Hover over a user’s name in the right sidebar.
2. Click on their avatar or the **ellipsis** () to the right of their name to open their **user card**.
3. Click **View profile**.
4. Select the **User groups** tab.
5. Under **Add user to groups**, enter the groups you want to add the
user to. You can start typing to filter suggestions.
6. Click the **Add** button. Zulip will notify the user about the groups
they’ve been added to.

## Add user groups to a group

You can add a group to another user group, making it easy to express your organization’s structure in Zulip’s permissions system. A user who belongs to a subgroup of a group is treated as a member of that group. For example:

- The “engineering” group could be made up of “engineering-managers” and “engineering-staff”.
- The “managers” group could be made up of “engineering-managers”, “design-managers”, etc.

Updating the members of a group automatically updates the members of all the groups that contain it. In the above example, adding a new team member to “engineering-managers” automatically adds them to “engineering” and “managers” as well. Removing a team member who transferred automatically removes them.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **Members** tab on the right.
6. Under **Add members**, enter groups you want to add.
7. Click **Add**.

 **Tip:** Click the  icon
on a user group pill to add all the members of the group, rather than the
group itself.

## Remove user or group from a group

**Note:**

You will see the options described only if you have permission to take this action.

**Via group settings:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **Members** tab on the right.
6. Under **Members**, find the user or group you would like to remove.
7. Click the **remove** () icon in that row. Zulip will notify
everyone who is removed from the group.

**Via user profile:**

1. Hover over a user’s name in the right sidebar.
2. Click on their avatar or the **ellipsis** () to the right of their name to open their **user card**.
3. Click **View profile**.
4. Select the **User groups** tab.
5. Find the group you would like to remove the user from.
6. Click the **remove** () icon in that row. Zulip will notify
the user about the groups they’ve been removed from.

## Review and remove permissions assigned to a group

You can review which permissions are assigned to a group, and remove permissions as needed. To add permissions, use the dedicated permissions management panel for your organization, or the channel or group you’re adding permissions for.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Group settings**.
3. Click **All groups** in the upper left.
4. Select a user group.
5. Select the **Permissions** tab on the right.
6. Toggle the checkboxes next to any permissions you’d like to remove.
7. Click **Save changes**.

## Configure who can create user groups

**Note:**

This feature is only available to organization owners and administrators.

You can configure who can create groups in your organization. Guests can never create user groups, even if they belong to a group that has permissions to do so.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Group permissions**, configure **Who can create user groups**.
5. Click **Save changes**.

## Configure who can administer all user groups

**Note:**

This feature is only available to organization owners and administrators.

You can configure who can administer all user groups in your organization. Guests can never administer user groups, even if they belong to a group that has permissions to do so.

In addition, you can give users permission to administer a specific group.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Group permissions**, configure **Who can administer all user groups**.
5. Click **Save changes**.