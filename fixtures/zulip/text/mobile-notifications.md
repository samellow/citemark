# Mobile notifications

Zulip can be configured to send mobile notifications for DMs, mentions, and alerts, as well as channel messages and followed topics.

Organization administrators can enable mobile notifications, per channel, as a default for new subscribers.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Toggle the checkboxes in the **Mobile** column of the **Notification
triggers** table.

## End-to-end encryption (E2EE) for mobile push notifications

Zulip Server 12.0+ and Zulip Cloud support end-to-end encrypted (E2EE) mobile
push notifications. All push notifications sent from an up-to-date version of
the server to an updated version of the app (30.0.271+ on Android, 30.0.272+ on iOS)
will be end-to-end encrypted. E2EE ensures that message **content** and **metadata**
(including the sender’s and recipient’s names, or channel and topic where the
message was sent) are not visible to Apple, Google, or Zulip’s
Mobile Push Notification
Service.

Organization administrators can require end-to-end encryption for mobile push notifications. When this setting is enabled, push notifications will only be sent to updated version of the apps that support end-to-end encryption. Older apps that don’t support E2EE will not receive any push notifications.

See technical documentation for encryption protocol details.

### Require end-to-end encryption for mobile push notifications

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Notifications security**, toggle **Require end-to-end encryption for push notifications**.

## Mobile notifications while online

You can customize whether or not Zulip will send mobile push notifications while you are actively using one of the Zulip apps.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Mobile message notifications**, toggle **Send mobile notifications even if I’m online**, as desired.

## Testing mobile notifications

Start by configuring your notifications settings to make it easy to trigger a notification.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. In the **Mobile** column of the **Notification triggers** table, make sure
the **DMs, mentions, and alerts** checkbox is checked.
5. Under **Mobile message notifications**, make sure the **Send mobile
notifications even if I’m online** checkbox is checked.

Next, test Zulip push notifications on your mobile device.

**Mobile:**

1. Download and install the Zulip mobile app if you have not done so already.
2. If your Zulip organization is self-hosted (not at `*.zulipchat.com`),
check
whether push notifications have been set up. If they were set up recently,
you will need to log out of your account.
3. Log in to the account you want to test.
4. Ask *another* user (not yourself) to send you a direct
message. You should see a Zulip message
notification in the **notifications area** on your device.

## Troubleshooting mobile notifications

### Checking your device settings

Some Android vendors have added extra device-level settings that can impact the delivery of mobile notifications to apps like Zulip. If you’re having issues with Zulip notifications on your Android phone, we recommend Signal’s excellent troubleshooting guide, which explains the notification settings for many popular Android vendors.

Android users using microG: we have heard reports of notifications working if microG’s “Cloud Messaging” setting is enabled.

### Enabling push notifications for self-hosted servers

**Note:**

These instructions do not apply to Zulip Cloud organizations (`*.zulipchat.com`).

To enable push notifications for your organization:

1. Your server administrator needs to register your Zulip server with the Zulip Mobile Push Notification Service.
2. For organizations with more than 10 users, a user who can manage plans and billing needs to sign up for a plan for your organization.