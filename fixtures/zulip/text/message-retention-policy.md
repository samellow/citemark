# Message retention policy

**Note:**

This feature is only available to organization owners.

By default, Zulip stores messages indefinitely, allowing full-text search of your complete history.

Zulip supports configuring both a global organization-level message retention policy, as well as retention policies for individual channels. These policies control how many days a message is stored before being automatically deleted (the default being forever). Zulip’s system supports:

- Setting an organization-level retention policy, which applies to all direct messages and all channels without a specific policy.
- Setting a retention policy for individual channels, which overrides the organization-level policy for that channel. This can be used to just delete messages on specific channels, to only retain messages forever on specific channels, or just to have a different retention period.

In Zulip Cloud, message retention policies are available on the Zulip Cloud Standard and Zulip Cloud Plus plans, as well as for the hundreds of communities with sponsored Cloud Standard hosting.

### Configure message retention policy for organization

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Message retention period**, configure **Message retention
period**.
5. Click **Save changes**.

### Configure message retention policy for individual channels

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Select a channel.
5. Select the **Permissions** tab on the right.
6. Under **Administrative permissions**, configure the **Message retention period**.
7. Click **Save changes**.

 **Tip:** You can also click on a channel name in the navigation bar at the top of the
app to access its settings, or use the **ellipsis** ()
next to the channel name in the left sidebar.

## Important details

- Retention policies are processed in a daily job; so changes in the policy won’t have any effect until the next time the daily job runs.
- Deleted messages are preserved temporarily in a special archive. So if you discover a misconfiguration accidentally deleted content you meant to preserve, contact Zulip support promptly for assistance with restoration. See the deletion documentation for more details on precisely how message deletion works in Zulip.