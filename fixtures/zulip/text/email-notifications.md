# Email notifications

## Message notification emails

Zulip can be configured to send message notification emails for DMs, mentions, and alerts, as well as channel messages and followed topics.

You will receive email notifications only for messages sent when you were not active on Zulip. Messages sent to the same conversation within a configurable time period (e.g., a few minutes) will be combined into a single email.

You can reply to Zulip messages by replying to message notification emails.

**Note:**

To enable replies via email on a self-hosted server, the incoming email gateway must be configured by the system administrator.

### Configure triggers for message notification emails

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Toggle the checkboxes in the **Email** column of the **Notification
triggers** table.

### Include organization name in subject line

You can configure whether the name of your Zulip organization is included in the subject of message notification emails.

Zulip offers a convenient **Automatic** configuration option, which includes the
name of the organization in the subject only if you have accounts in multiple
Zulip Cloud organizations, or in multiple organizations on the same Zulip server.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Email message notifications**, configure **Include organization name in subject of message notification emails**.

### Configure delay for message notification emails

To reduce the number of emails you receive, Zulip delays sending message notification emails for a configurable period of time. The delay helps in a few ways:

- No email is sent if you return to Zulip and read the message before the email would go out.
- Edits made by the sender soon after sending a message will be reflected in the email.
- Multiple messages in the same Zulip conversation are combined into a single email. Different conversations will always be in separate emails, so that you can respond directly from your email.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Email message notifications**, select the desired time period from the **Delay before sending message notification emails** dropdown.

### Hide message content

For security or compliance reasons, you may want to hide the content of your Zulip messages from your email. Organization administrators can do this at an organization-wide level, but you can also do this just for the messages you receive.

This setting also blocks message topics, channel names, and user names from being sent through your email.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Email message notifications**, toggle **Include message content in message notification emails**.

## New login emails

By default, Zulip sends an email whenever you log in to Zulip. These emails help you protect your account; if you see a login email at a time or from a device you don’t recognize, you should change your password right away.

In typical usage, these emails are sent infrequently, since all Zulip apps (web, mobile, desktop, and terminal) keep you logged in to any organization you’ve interacted with in the last 1-2 weeks.

However, there are situations (usually due to corporate security policy) in which you may have to log in every day, and where getting login emails can feel excessive.

### Disable new login emails

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Other emails**, toggle **Send email notifications for new logins to my account**.

## Low-traffic newsletter

**Note:**

This feature is only available on Zulip Cloud.

Zulip sends out a low-traffic newsletter (expect 2-4 emails a year) to Zulip Cloud users announcing major changes in Zulip.

### Managing your newsletter subscription

**Zulip Cloud:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Other emails**, toggle **Send me Zulip’s low-traffic newsletter (a few emails a year)**.