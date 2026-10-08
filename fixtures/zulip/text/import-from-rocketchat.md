# Import from Rocket.Chat

You can import your current workspace into a Zulip organization. It’s a great way to preserve your workspace history when you migrate to Zulip, and to make the transition easy for the members of your organization.

The import will include your organization’s:

- **Name**
- **Message history**, including attachments and emoji reactions
- **Users**, including names, emails, roles, and teams
- **Channels**, including discussions and all user subscriptions
- **Custom emoji**

## Import process overview

To import your Rocket.Chat organization into Zulip, you will need to take the following steps, which are described in more detail below:

1. Export your Rocket.Chat data.
2. Import your Rocket.Chat data into Zulip.
3. Get your organization started with Zulip!

## Import your organization from Rocket.Chat into Zulip

### Export your Rocket.Chat data

Rocket.Chat does not provide an official data export feature, so the Zulip import tool works by importing data from a Rocket.Chat database dump.

If you’re self-hosting your Rocket.Chat instance, you can create a
database dump using the `mongodump` utility. Make sure your Rocket.Chat
server is **NOT** shut down while creating database dump using `mongodump`.

If your organization is hosted on Rocket.Chat Cloud or another hosting provider that doesn’t provide you with database access, you will need to request a database dump by contacting their support.

In either case, you should end up with a directory containing many
`.bson` files.

### Import your data into Zulip

To start using Zulip, you will need to choose between Zulip Cloud and self-hosting Zulip. For a simple managed solution, with no setup or maintenance overhead, you can sign up for Zulip Cloud with just a few clicks. Alternatively, you can self-host your Zulip organization. See here to learn more.

**Note:**

**You can only import a workspace as a new Zulip organization.** Your imported
message history cannot be added into an existing Zulip organization.

At this point, you should go to the directory containing all the `.bson` files
from your database dump and rename it to `rocketchat_data`. This directory will
be your **exported data** file in the instructions below.

**Zulip Cloud:**

If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information:

1. The subdomain you would like to use for your organization. Your Zulip chat will
be hosted at `<subdomain>.zulipchat.com`.
2. The **exported data** file containing your workspace message history export.

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
commands. **Note:**
The import could take several minutes to run, depending on how much data you’re importing.  **Tip:** The server stop/restart commands are only
necessary when importing on a server with minimal
RAM, where an OOM kill might otherwise occur.
```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_rocketchat_data /tmp/rocketchat_data --output /tmp/converted_rocketchat_data
./manage.py import '' /tmp/converted_rocketchat_data
./scripts/start-server
```
Alternatively, to import into a custom subdomain, run: ```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_rocketchat_data /tmp/rocketchat_data --output /tmp/converted_rocketchat_data
./manage.py import <subdomain> /tmp/converted_rocketchat_data
./scripts/start-server
```
5. Follow step 4 of the guide for installing a new Zulip server.

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are a few notes to keep in mind about the import process:

- Rocket.Chat does not export workspace settings, so you will need to configure the settings for your Zulip organization. This includes settings like email visibility, message editing permissions, and how users can join your organization.
- Rocket.Chat does not export user settings, so users in your organization may want to customize their account settings.
- Rocket.Chat user roles are mapped to Zulip’s user
roles in the following way:
Rocket.Chat role Zulip role Admin Owner User Member Guest Guest
- User avatars are not imported.
- Default channels for new users are not imported.
- Starred messages are not imported.
- Messages longer than Zulip’s limit of 10,000 characters are not imported.
- Livechat channels/messages are not imported.
- Messages from Rocket.Chat Discussions are imported as topics inside the Zulip channel corresponding to the parent channel of the Rocket.Chat Discussion.
- Messages from Rocket.Chat Discussions having direct channels (i.e. direct messages) as their parent are imported as normal direct messages in Zulip.
- While Rocket.Chat Threads are in general imported as separate topics, Rocket.Chat Threads within Rocket.Chat Discussions are imported as normal messages within the topic containing that Discussion, and Threads in Direct Messages are imported as normal Zulip direct messages.

Additionally, because Rocket.Chat does not provide a documented or stable data export API, the import tool may require small changes from time to time to account for changes in the Rocket.Chat database format. Please contact us if you encounter any problems using this tool.

## Get your organization started with Zulip

Once the import process is completed, you will need to:

1. Configure the settings for your organization, which are not exported. This includes settings like email visibility, message editing permissions, and how users can join your organization.
2. All users from your previous workspace will have accounts in your new Zulip organization. However, you will need to let users know about their new accounts, and decide how they will log in for the first time.
3. Share the URL for your new Zulip organization, and (recommended) the Getting started with Zulip guide.
4. Migrate any integrations.

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