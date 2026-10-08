# Import from Microsoft Teams

You can import your current workspace into a Zulip organization. It’s a great way to preserve your workspace history when you migrate to Zulip, and to make the transition easy for the members of your organization.

The import will include your organization’s:

- **Name**
- **Users**, including names, emails, roles
- **Teams** as Zulip channels, including all user subscriptions
- **Message history**, excluding direct messages and messages in private channels

**Note:**

This feature is currently in beta. If you run into any problems, please report them.

## Import process overview

To import your Microsoft Teams data into Zulip, you will need to take the following steps, which are described in more detail below:

1. Export your Microsoft Teams data.
2. Authorize a Microsoft Graph API token.
3. Import your Microsoft Teams data into Zulip.
4. Clean up after the Microsoft Teams export.
5. Get your organization started with Zulip!

When planning to migrate from Microsoft Teams to Zulip, make sure your Microsoft tenant is active and still has access to Microsoft services for at least a couple of months. The process to gain access to the Teams data export tool can take around a month, and Zulip’s import tool for Microsoft Teams requires an active Microsoft Entra ID application. Additionally, since the imported users’ email addresses will be their Microsoft tenant emails, they will still need access to those accounts to update their Zulip email addresses.

## Import your organization from Microsoft Teams into Zulip

### Export your Microsoft Teams data

The Teams data export tool supports the export of data for tenants of up to 500 users. If your organization has more than 500 users, you can try the Teams export APIs.

#### Export message history using the Teams data export tool

1. Make sure that you are an admin of your Microsoft organization. Request
access to the data export tool
by contacting support through the **Teams admin center**.
2. File a ticket using the predefined title. In the description, provide an estimate of the size of your tenant, and confirmation that you are accessing the tool for the purpose of switching from Teams.
3. Once your request is approved, go to the Microsoft Teams admin
center as the **global administrator**.
4. In the **dashboard**, find the user interface for the **Teams data export**.
5. Select the date range and export your data. You should be able to download a
`zip` file with your data a few minutes after you start the export process.

### Authorize a Microsoft Graph API token

Some organization data is not exported by the Teams data export tool. The Zulip import tool will call several Microsoft Graph APIs to collect the following data:

- **Hosted contents**.
Teams content hosted in a chat message, such as images or code snippets.
- **User roles**. The user roles section explains how  Microsoft
Teams users roles and user types are mapped to Zulip user roles.

To access those APIs, create a Microsoft Entra ID application with the required permissions, and authorize an access token:

1. Log in to the Microsoft Entra ID portal as
the **global administrator**.
2. Navigate to the sidebar → **Entra ID** → **App registrations**, and click **New
registration**.
3. In the **Register an application** menu, enter the application’s name
(e.g., “Zulip export”).
4. In the **Supported accounts types** section, select **Accounts in this organizational
directory only**.
5. In the **Redirect URI** section, select **Web** as the platform type and enter `"https://chat.zulip.org/"`.
6. In the app’s menu, navigate to the **API permissions** menu.
7. Click **Add a permission** and select **Microsoft Graph**.
8. Select **Application permissions** as the permission type.
9. Search and add these permissions: 
  - `ChannelMessage.Read.All`
  - `User.Read.All`
  - `RoleManagement.Read.Directory`
See the required token permissions section for more details about these tokens and the endpoints that the import tool calls.
10. Click the **Grant admin consent for `your organization`** button in the **API
permissions** menu to grant admin consent to all scopes.
11. Take note of the application’s `tenant_id`, `client_id`, and `client_secret`.
12. To get the access token, make the following request: ```
curl --location --request POST 'https://login.microsoftonline.com/<tenant_id>/oauth2/v2.0/token' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'client_id=<client_id>' \
  --data-urlencode 'scope=https://graph.microsoft.com/.default' \
  --data-urlencode 'client_secret=<client_secret>' \
  --data-urlencode 'grant_type=client_credentials'
```
A successful response looks like this: ```
  {
    "token_type": "Bearer",
    "expires_in": 3599,
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Ik1uQ19WWmNBVGZNNXBP..."
  }
```
13. Take note of the `access_token`.

#### Required token permissions

The following Microsoft Graph API endpoints are used by the Zulip import tool:

| Endpoint | Uses | Least-privileged permission | 
|---|---|---|
| directory role list member | Used to find users who are global administrators. | `User.Read.All` | 
| list directory role | Used to find the ID for the global administrator role. | `RoleManagement.Read.Directory` | 
| list user | Used to find guest accounts. | `User.Read.All` | 
| get hosted content | Used to download hosted content attachments. | `ChannelMessage.Read.All` | 

### Import your data into Zulip

To start using Zulip, you will need to choose between Zulip Cloud and self-hosting Zulip. For a simple managed solution, with no setup or maintenance overhead, you can sign up for Zulip Cloud with just a few clicks. Alternatively, you can self-host your Zulip organization. See here to learn more.

**Note:**

**You can only import a workspace as a new Zulip organization.** Your imported
message history cannot be added into an existing Zulip organization.

**Zulip Cloud:**

If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information:

1. The subdomain you would like to use for your organization. Your Zulip chat will
be hosted at `<subdomain>.zulipchat.com`.
2. The **exported data** file containing your workspace message history export.

**Note:**

If the organization already exists, the import process will overwrite all data that’s already there. If needed, we’re happy to preserve your data by moving an organization you’ve already created to a new subdomain prior to running the import process.

**Self hosting:**

#### Import into a self-hosted Zulip server

Zulip’s import tools are robust, and have been used to import workspaces with 10,000 members and millions of messages. If you’re planning on doing an import much larger than that, or run into performance issues when importing, contact us for help.

1. Follow steps 1 and 2 of the guide for installing a new Zulip server.
2. Copy the **exported data** file containing your workspace message
history export onto your Zulip server, and put it in `/tmp/`.
3. Log in to a shell on your Zulip server as the `zulip` user.
4. To import into an organization hosted on the root domain
(`EXTERNAL_HOST`) of the Zulip installation, run the following
commands, replacing `<token>` with your Microsoft Graph API access token. **Note:**
The import could take several minutes to run, depending on how much data you’re importing.  **Tip:** The server stop/restart commands are only
necessary when importing on a server with minimal
RAM, where an OOM kill might otherwise occur.
```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_microsoft_teams_data /tmp/TeamsData/ --token <token> --output /tmp/converted_microsoft_teams_data
./manage.py import '' /tmp/converted_microsoft_teams_data
./scripts/start-server
```
Alternatively, to import into a custom subdomain, run: ```
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_microsoft_teams_data /tmp/TeamsData/ --token <token> --output /tmp/converted_microsoft_teams_data
./manage.py import <subdomain> /tmp/converted_microsoft_teams_data
./scripts/start-server
```
5. Follow step 4 of the guide for installing a new Zulip server.

### Import details

Because the import tool is currently in beta, the following data is not imported into Zulip. If importing any of this data is important for your organization, contact support@zulip.com to see if the import tool can be extended to include it.

- Direct messages and messages in private channels
- Meeting chats and recordings
- Message attachments stored in Microsoft SharePoint are not imported.
- Message reactions
- Message edit history, and system messages such as `@user_a added @user_b to the chat`
- Custom emoji
- User avatars

A couple of additional caveats to keep in mind:

- Mentions in messages are not converted to Zulip mentions.
- Message thread replies will be combined to the main topic.

#### User roles

Microsoft tenant’s user roles are mapped to Zulip’s user roles in the following way:

| Microsoft Teams role | Zulip role | 
|---|---|
| Global Administrator | Owner | 
| Member | Member | 
| Guest | Guest | 

#### Settings

The Teams export tool does not export organization settings, or full user settings. Configure organization settings as described below, and encourage users to customize their account settings.

## Clean up after the Microsoft Teams export

Once your organization has been successfully imported in to Zulip, you should delete the Microsoft Entra ID application that you created in order to export your Microsoft Teams data.

## Get your organization started with Zulip

Once the import process is completed, you will need to:

1. Configure the settings for your organization, which are not exported. This includes settings like email visibility, message editing permissions, and how users can join your organization.
2. All users from your previous workspace will have accounts in your new Zulip organization. However, you will need to let users know about their new accounts, and decide how they will log in for the first time.
3. Share the URL for your new Zulip organization, and (recommended) the Getting started with Zulip guide.
4. **Make sure all users change their Zulip email
addresses from their Microsoft tenant
emails** to ones they can continue to access, before your organization’s
Microsoft subscription expires. Zulip’s management
tools
also allow self-hosted server administrators to change user emails directly;
Zulip Cloud users can contact support for
assistance.
5. Migrate any integrations.

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