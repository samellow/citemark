# Import from Slack

You can import your current workspace into a Zulip organization. It’s a great way to preserve your workspace history when you migrate to Zulip, and to make the transition easy for the members of your organization.

The import will include your organization’s:

- **Name** and **Logo**
- **Message history**, including attachments and emoji reactions
- **Users**, including names, emails, roles, avatars, time zones, and custom profile fields
- **Channels**, including all user subscriptions
- **Custom emoji**

## Import process overview

To import your Slack organization into Zulip, you will need to take the following steps, which are described in more detail below:

1. Export your Slack data.
2. Import your Slack data into Zulip.
3. Clean up after the Slack export.
4. Decide how users will log in!

Be sure to check out the guide on moving from Slack for a walkthrough of the transition process.

## Import your organization from Slack into Zulip

### Export your Slack data

Slack’s data export
service allows you to
export all public channel messages, **including older messages that may no
longer be searchable** under your Slack plan.

Unfortunately, Slack only
allows
workspaces that are on the **Business+** or **Enterprise Grid** plans
to export private channels and direct messages. Slack’s support has
confirmed this policy as of August 2022.

Owners of **Business+** or **Enterprise Grid** workspaces can request
special
access
in order to export direct message data.

#### Export message history

1. Make sure that you are an owner or admin of your Slack workspace. If you are one, the Slack web application will display that in your profile, in a banner covering the bottom of your avatar.
2. Export your Slack message history.
You should be able to download a `zip` file with your data a few minutes
after you start the export process.

#### Export user data and custom emoji

1. Make sure that you are an owner or admin of your Slack workspace. If you are one, the Slack web application will display that in your profile, in a banner covering the bottom of your avatar.
2. Create a new Slack app. Choose the **From
scratch** creation option.
3. Create a
bot user,
following the instructions to add the following OAuth scopes to your bot:
  - `emoji:read`
  - `users:read`
  - `users:read.email`
  - `team:read`
4. In **OAuth & Permissions**, under **OAuth Tokens**, click **Install to
Workspace**. Grant the app permission to access your workspace by
clicking **Allow** when prompted.
5. You will immediately see a **Bot User OAuth Token**, which is a long
string of numbers and characters starting with `xoxb-`. Copy this token. It
grants access to download user and emoji data from your Slack workspace.

**Note:**

You may also come across a token starting with `xoxe-`. This token cannot
be used for the Slack export process.

### Import your data into Zulip

To start using Zulip, you will need to choose between Zulip Cloud and self-hosting Zulip. For a simple managed solution, with no setup or maintenance overhead, you can sign up for Zulip Cloud with just a few clicks. Alternatively, you can self-host your Zulip organization. See here to learn more.

**Note:**

**You can only import a workspace as a new Zulip organization.** Your imported
message history cannot be added into an existing Zulip organization.

**Zulip Cloud (self-serve):**

1. If you’ve already created an organization at the subdomain you plan to use, email support@zulip.com to get it deleted, so that you can start the import process.
2. Fill out the information to create a new Zulip Cloud
organization. Under **Import chat history?**,
select **Import from Slack**.
3. Click **Complete registration** in the confirmation email you received.
4. Enter your Slack **Bot User OAuth Token**, which will be a long
string of numbers and characters starting with `xoxb-`, and click **Submit**.
5. Click **Start upload** to upload the **exported data** `.zip` file
from your Slack workspace.
6. Configure **Who will be allowed to see other users’ email addresses?**,
and click **Start import**. The import may take some time to complete.
7. If you’re using a different registration email from your Slack account, select your Slack account from the dropdown. If you don’t have an account in the imported workspace, you can create a new Zulip account.
8. Set a password for your Zulip account, and click **Submit**.

**Zulip Cloud (via support):**

If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information:

1. The subdomain you would like to use for your organization. Your Zulip chat will
be hosted at `<subdomain>.zulipchat.com`.
2. The **exported data** file containing your workspace message history export.

1. Your Slack **Bot User OAuth Token**, which will be a long
string of numbers and characters starting with `xoxb-`.

**Note:**

If the organization already exists, the import process will overwrite all data that’s already there. If needed, we’re happy to preserve your data by moving an organization you’ve already created to a new subdomain prior to running the import process.

**Self-hosted:**

#### Import into a self-hosted Zulip server

Zulip’s import tools are robust, and have been used to import workspaces with 10,000 members and millions of messages. If you’re planning on doing an import much larger than that, or run into performance issues when importing, contact us for help.

1. Follow steps 1 and 2 of the guide for installing a new Zulip server.
2. Copy the **exported data** file containing your workspace message
history export onto your Zulip server, and put it in `/tmp/`.
3. Log in to a shell on your Zulip server as the `zulip` user.
4. To import into an organization hosted on the root domain
(`EXTERNAL_HOST`) of the Zulip installation, run the following
commands, replacing `<token>` with your Slack **Bot User OAuth Token**. **Note:**
The import could take several minutes to run, depending on how much data you’re importing.  **Tip:** The server stop/restart commands are only
necessary when importing on a server with minimal
RAM, where an OOM kill might otherwise occur.
```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_slack_data /tmp/slack_data.zip --token <token> --output /tmp/converted_slack_data
./manage.py import '' /tmp/converted_slack_data
./scripts/start-server
```
Alternatively, to import into a custom subdomain, run: ```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_slack_data /tmp/slack_data.zip --token <token> --output /tmp/converted_slack_data
./manage.py import <subdomain> /tmp/converted_slack_data
./scripts/start-server
```
5. Follow step 4 of the guide for installing a new Zulip server.

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are few notes to keep in mind about the import process:

- Slack does not export workspace settings, so you will need to configure the settings for your Zulip organization. This includes settings like email visibility, message editing permissions, and how users can join your organization.
- Slack does not export user settings, so users in your organization may want to customize their account settings.
- Slack’s user roles are mapped to Zulip’s user
roles in the following way:
Slack role Zulip role Workspace Primary Owner Owner Workspace Owner Owner Workspace Admin Administrator Member Member Single Channel Guest Guest Multi Channel Guest Guest Channel creator none
- Slack threads are imported as topics with names that include snippets of the original message, such as “2023-05-30 Hi, can anyone reply if you’re o…”.
- Message edit history and `@user joined #channel_name` messages are not imported.

## Clean up after the Slack export

Once your organization has been successfully imported in to Zulip, you should delete the Slack app that you created in order to export your Slack data. This will prevent the OAuth token from being used to access your Slack workspace in the future.

## Decide how users will log in

When user accounts are imported, users initially do not have passwords configured. There are a few options for how users can log in for the first time.

 **Tip:** For security reasons, passwords are never exported.

### Allow users to log in with non-password authentication

When you create your organization, users will immediately be able to log in with authentication methods that do not require a password. Zulip offers a variety of authentication methods, including Google, GitHub, GitLab, Apple, Discord, LDAP and SAML.

### Send password reset emails to all users

You can send password reset emails to all users in your organization, which will allow them to set an initial password.

If you imported your organization into Zulip Cloud, simply email support@zulip.com to request this.

**Note:**

To avoid confusion, first make sure that the users in your organization are aware that their account has been moved to Zulip, and are expecting to receive a password reset email.

#### Send password reset emails (self-hosted organization)

**Default subdomain:**

1. To test the process, start by sending yourself a password reset email by
using the following command:
`./manage.py send_password_reset_email -u username@example.com`
2. When ready, send password reset emails to all users by
using the following command:
`./manage.py send_password_reset_email -r '' --all-users`

**Custom subdomain:**

1. To test the process, start by sending yourself a password reset email by
using the following command:
`./manage.py send_password_reset_email -u username@example.com`
2. When ready, send password reset emails to all users by
using the following command:
`./manage.py send_password_reset_email -r <subdomain> --all-users` If you would like to only send emails to users who have not logged in yet,
you can use the following variant instead: `./manage.py send_password_reset_email -r <subdomain> --all-users --only-never-logged-in`

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions on your Zulip organization’s login page.

## View imported user accounts

You can see and manage a list of imported users who have not logged in yet to activate their Zulip account.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Users**.
4. Select the **Imported** tab.

## Onboarding

To prepare your organization for transitioning to Zulip, follow the guide on moving from Slack.