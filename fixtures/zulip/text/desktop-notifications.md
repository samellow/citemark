# Desktop notifications

Zulip can be configured to send visual and audible desktop notifications for DMs, mentions, and alerts, as well as channel messages and followed topics.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Toggle the checkboxes in the **Desktop** column of the **Notification
triggers** table.

## Notification sound

You can select the sound Zulip uses for audible desktop notifications. Choosing
**None** disables all audible desktop notifications.

### Change notification sound

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Desktop message notifications**, configure **Notification sound**.

 **Tip:** To hear the selected sound, click the  to the right of your selection.

## Unread count badge

By default, Zulip displays a count of your unmuted unread messages on the desktop app sidebar and on the browser tab icon. You can configure the badge to only count direct messages and mentions, or to include messages in followed topics but not other channel messages.

### Configure unread count badge

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Desktop message notifications**, configure **Unread count badge**.

### Disable unread count badge

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Desktop message notifications**, select **None** from the **Unread count badge** dropdown.

## Testing desktop notifications

**Note:**

This does not make an unread count badge appear.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Desktop message notifications**, click **Send a test notification**.
If notifications are working, you will receive a test notification.

## Troubleshooting desktop notifications

Desktop notifications are triggered when a message arrives, and Zulip is not in focus or the message is offscreen. You must have Zulip open in a browser tab or in the Zulip desktop app to receive desktop notifications.

**Visual desktop notifications** appear in the corner of your main monitor.
**Audible desktop notifications** make a sound.

To receive notifications in the desktop app, make sure that Do Not Disturb mode is turned off.

### Check notification settings for DMs or channels

If you have successfully received a test notification, but you aren’t seeing desktop notifications for new messages, check your Zulip notification settings. Make sure you have enabled desktop notifications for DMs or for the channel you are testing. Messages in muted topics will not trigger notifications.

### Check platform settings

The most common issue is that your browser or system settings are blocking
notifications from Zulip. Before checking Zulip-specific settings, make sure
that **Do Not Disturb mode** is not enabled on your computer.

**Chrome:**

1. Click on the site information menu to the left of the URL for your Zulip organization.
2. Toggle **Notifications** and **Sound**. If you don’t see those options,
click on **Site settings**, and set **Notifications** and **Sound** to **Allow**.

Alternate instructions:

1. Select the Chrome menu at the top right of the browser, and select
**Settings**.
2. Select **Privacy and security**, **Site Settings**, and then **Notifications**.
3. Next to **Allowed to send notifications**, select **Add**.
4. Paste the Zulip URL for your organization into the site field, and
click **Add**.

**Firefox:**

1. Select the Firefox menu at the top right of the browser, and select
**Settings**.
2. On the left, select **Privacy & Security**. Scroll to the **Permissions** section and select the **Settings** button next to **Notifications**.
3. Find the URL for your Zulip organization, and adjust the **Status** selector to **Allow**.

**Desktop app:**

**Windows**

1. Click the **Start** button and select **Settings**. Select **System**,
and then **Notifications & actions**.
2. Select **Zulip** from the list of apps.
3. Configure the notification style that you would like Zulip to use.

**macOS**

1. Open your Mac **System Preferences** and select **Notifications**.
2. Select **Zulip** from the list of apps.
3. Configure the notification style that you would like Zulip to use.