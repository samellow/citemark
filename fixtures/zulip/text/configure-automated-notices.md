# Configure automated notices

The Zulip sends automated notices via Notification Bot to notify users about changes in their organization or account. Some types of notices can be configured, or disabled altogether.

Notices sent to channels are translated into the language that the organization has configured as the language for automated messages and invitation emails. The topic name is also translated. Notices sent directly to users will use their preferred language.

## Notices about channels

### New channel announcements

**Note:**

This feature is only available to organization owners and administrators.

When creating a new public or web-public channel, the channel creator can choose to advertise the new channel via an automated notice. You can configure what channel Zulip uses for these notices, or disable these notices entirely. The topic for these messages is “new channels”.

New private channels are never announced.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Automated messages and emails**, configure **New channel
announcements**.
5. Click **Save changes**.

### Channel events

You can configure whether Zulip will send an automated message when a channel’s settings are updated. If enabled, Notification Bot will send messages about updates to settings such as the channel name, description, privacy and posting policy. Messages will be sent to the “channel events” topic in the modified channel.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Automated messages and emails**, configure **Send automated
messages for channel events**.
5. Click **Save changes**.

## Notices about topics

A notice is sent when a topic is resolved or unresolved. Users can configure whether these notices are automatically marked as read.

Additionally, when moving messages to another channel or topic, users can decide whether to send automated notices to help others understand how content was moved.

## Notices about users

You will be notified if someone subscribes you to a channel, or changes your group membership.

### New user announcements

**Note:**

This feature is only available to organization owners and administrators.

You can configure where Notification Bot will post an announcement when new users join your organization, or disable new user announcement messages entirely. The topic for these messages is “signups”.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Automated messages and emails**, configure **New user
announcements**.
5. Click **Save changes**.

### Notices about changes to user profile

When an administrator modifies your account settings, you will receive a private message from Notification Bot listing the changes that were made. This includes updates to your full name, role, and custom profiles fields.

The notification will show both the old and new values for each field that was changed, making it easy to see exactly what was modified. Only administrators can change other users’ profiles, and these notifications ensure that users are always informed when such changes occur.

## Zulip update announcements

Zulip announces new features and other important product changes via automated messages. This is designed to help users discover new features they may find useful, including new configuration options.

These announcements are posted to the “Zulip updates” topic in the channel selected by organization administrators (usually 1-2x a month on Zulip Cloud). You can read update messages whenever it’s convenient, or mute the topic if you are not interested. If you organization does not want to receive these announcements, they can be disabled.

On self-hosted Zulip servers, announcement messages are shipped with the Zulip server version that includes the new feature or product change. You may thus receive several announcement messages when your server is upgraded.

Unlike other notices, Zulip update announcements are not translated.

### Configure Zulip update announcements

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Automated messages and emails**, configure **Zulip update
announcements**.
5. Click **Save changes**.