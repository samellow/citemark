# Create user groups

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to Zulip Cloud Standard or Zulip Cloud Plus.

User groups offer a flexible way to manage permissions in your organization. Most permissions in Zulip can be granted to any combination of roles, groups, and individual users.

Many organizations find it helpful to create groups for:

- Each team, e.g., “mobile”, “design”, or “IT”.
- Leadership roles, e.g., “managers”, “engineering-managers”.

You can add a group to another user group, making it easy to express your organization’s structure in Zulip’s permissions system. A user who belongs to a subgroup of a group is treated as a member of that group. For example:

- The “engineering” group could be made up of “engineering-managers” and “engineering-staff”.
- The “managers” group could be made up of “engineering-managers”, “design-managers”, etc.

Updating the members of a group automatically updates the members of all the groups that contain it. In the above example, adding a new team member to “engineering-managers” automatically adds them to “engineering” and “managers” as well. Removing a team member who transferred automatically removes them.

Groups provide an easy way to refer to multiple users at once. You can:

- Mention a group of users, notifying everyone in the group as if they were personally mentioned.
- Compose a direct message to a user group. This automatically puts all the users in the group into the addressee field.
- Subscribe a user group to a channel. This individually subscribes all the users in the group.

## How to create a user group

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