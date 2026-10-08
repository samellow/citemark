# Import from Mattermost

You can import your current workspace into a Zulip organization. It’s a great way to preserve your workspace history when you migrate to Zulip, and to make the transition easy for the members of your organization.

The import will include your organization’s:

- **Name** and **Logo**
- **Message history**, including attachments and emoji reactions
- **Users**, including names, emails, roles, avatars, time zones, and custom profile fields
- **Channels**, including all user subscriptions
- **Custom emoji**

## Import process overview

To import your Mattermost organization into Zulip, you will need to take the following steps, which are described in more detail below:

1. Export your Mattermost data.
2. Import your Mattermost data into Zulip.
3. Get your organization started with Zulip!

## Import your organization from Mattermost into Zulip

### Export your Mattermost data

Mattermost’s bulk export tool allows you to export all public and private channel messages.

The instructions below correspond to various common ways Mattermost is installed; if yours isn’t covered, contact us and we’ll help you out.

Replace `<username>` and `<server_ip>` with the appropriate values below.

**Default installation:**

1. SSH into your Mattermost production server.
`ssh <username>@<server_ip>`
2. Navigate to the `../server/bin/` directory in your Mattermost installation and
locate the `mmctl` executable. All subsequent `mmctl` commands are executed
using this executable.
3. Log in to a `mmctl` instance. `mmctl auth login <server_ip>` You’ll be prompted for a username (use your admin user), password, and for a
connection name. The connection name can be anything you want.
4. Create a full export of the server, including attached files.
`mmctl export create` **Note:**
If you’re on version \< `7.3.0`, you need to include the `--attachments` argument when calling the command above to export attachment files.
5. List all of the exports on the server, and copy the name of the
latest one to your clipboard.
`mmctl export list`
6. Download the export file to the server, replacing `latest_export` with the actual file name from the previous step and `/local/dir/` with the download destination. `mmctl export download latest_export.zip /local/dir/latest_export.zip`
7. Finally, copy the exported zip to your local computer.
`scp <username>@<server_ip>:latest_export.zip /local/dir`

**Cloud instance:**

1. Log in to your Mattermost cloud instance.
2. Navigate to the `../server/bin/` directory in your Mattermost installation and
locate the `mmctl` executable. All subsequent `mmctl` commands are executed
using this executable.
3. Log in to a `mmctl` instance. `mmctl auth login <server_ip>` You’ll be prompted for a username (use your admin user), password, and for a
connection name. The connection name can be anything you want.
4. Create a full export of the server, including attached files.
`mmctl export create` **Note:**
If you’re on version \< `7.3.0`, you need to include the `--attachments` argument when calling the command above to export attachment files.
5. List all of the exports on the server, and copy the name of the
latest one to your clipboard.
`mmctl export list`
6. Download the export file to the server, replacing `latest_export` with the actual file name from the previous step and `/local/dir/` with the download destination. `mmctl export download latest_export.zip /local/dir/latest_export.zip`
7. Finally, copy the exported zip file to your local computer.
`scp <username>@<server_ip>:latest_export.zip /local/dir`

**Docker:**

1. SSH into the server hosting your Mattermost docker container. `ssh <username>@<server_ip>`
2. Navigate to the `../server/bin/` directory in your Mattermost installation and
locate the `mmctl` executable. All subsequent `mmctl` commands are executed
using this executable.
3. Create a full export of the server, including attached files. `docker exec -it mattermost-docker_app_1 mmctl export create` **Note:**
If you’re on version \< `7.3.0`, you need to include the `--attachments` argument when calling the command above to export attachment files.
4. List all of the exports on the server, and copy the name of the latest one to your clipboard. `docker exec -it mattermost-docker_app_1 mmctl export list`
5. Download the export file to the server, replacing `latest_export` with the actual file name from the previous step and `/local/dir/` with the download destination.
`docker exec -it mattermost-docker_app_1 mmctl export download latest_export.zip /local/dir/latest_export.zip`
6. Finally, copy the exported zip file to your local computer. `scp <username>@<server_ip>:latest_export.zip /local/dir`

**GitLab Omnibus:**

1. SSH into your GitLab Omnibus server.
`ssh <username>@<server_ip>`
2. Create an export of all your Mattermost teams, as a tar file.
```
cd /opt/gitlab/embedded/service/mattermost
sudo -u \
    mattermost /opt/gitlab/embedded/bin/mattermost \
    --config=/var/opt/gitlab/mattermost/config.json \
    export bulk export.json --all-teams --attachments
mkdir -p exported_emoji
tar --transform 's|^|mattermost/|' -czf export.tar.gz \
    data/ exported_emoji/ export.json
```
3. Exit your shell on the GitLab Omnibus server.
`exit`
4. Finally, copy the exported tar file from GitLab Omnibus to your local computer.
`scp <username>@<server_ip>:/opt/gitlab/embedded/bin/mattermost/export.tar.gz .`

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

**Self-hosted:**

#### Import into a self-hosted Zulip server

Zulip’s import tools are robust, and have been used to import workspaces with 10,000 members and millions of messages. If you’re planning on doing an import much larger than that, or run into performance issues when importing, contact us for help.

1. Follow steps 1 and 2 of the guide for installing a new Zulip server.
2. Copy the **exported data** file containing your workspace message
history export onto your Zulip server, and put it in `/tmp/`.
3. Log in to a shell on your Zulip server as the `zulip` user.
4. To import into an organization hosted on the root domain
(`EXTERNAL_HOST`) of the Zulip installation, run the following commands,
replacing `<team-name>` with the name of the Mattermost team you want to import. **Note:**
The import could take several minutes to run, depending on how much data you’re importing.  **Tip:** The server stop/restart commands are only
necessary when importing on a server with minimal
RAM, where an OOM kill might otherwise occur.
```
cd /tmp
tar -xf mattermost_data.tar.gz
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_mattermost_data /tmp/mattermost_data --output /tmp/converted_mattermost_data
./manage.py import '' /tmp/converted_mattermost_data/<team-name>
./scripts/start-server
```
By default Mattermost teams will be converted into their own Zulip organizations,
to convert all Mattermost teams into one Zulip organization, run: `./manage.py convert_mattermost_data /tmp/mattermost_data --output /tmp/converted_mattermost_data --combine-teams-into-one-org` **Note**: With the `--combine-teams-into-one-org` option, admins in individual Mattermost
teams will be converted into admin users in the combined Zulip organization.
Alternatively, to import into a custom subdomain, run: ```
cd /tmp
tar -xf mattermost_data.tar.gz
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_mattermost_data /tmp/mattermost_data --output /tmp/converted_mattermost_data
./manage.py import <subdomain> /tmp/converted_mattermost_data/<team-name>
./scripts/start-server
```
5. Follow step 4 of the guide for installing a new Zulip server.

**Self-hosted (cloud export):**

#### Import into a self-hosted Zulip server

Zulip’s import tools are robust, and have been used to import workspaces with 10,000 members and millions of messages. If you’re planning on doing an import much larger than that, or run into performance issues when importing, contact us for help.

1. Follow steps 1 and 2 of the guide for installing a new Zulip server.
2. Copy the **exported data** file containing your workspace message
history export onto your Zulip server, and put it in `/tmp/`.
3. Log in to a shell on your Zulip server as the `zulip` user.
4. To import into an organization hosted on the root domain
(`EXTERNAL_HOST`) of the Zulip installation, run the following commands,
replacing `<team-name>` with the name of the Mattermost team you want to import. **Note:**
The import could take several minutes to run, depending on how much data you’re importing.  **Tip:** The server stop/restart commands are only
necessary when importing on a server with minimal
RAM, where an OOM kill might otherwise occur.
```
unzip latest_export.zip -d /tmp/my_mattermost_export
mv /tmp/my_mattermost_export/import.jsonl /tmp/my_mattermost_export/export.json
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_mattermost_data /tmp/my_mattermost_export --output /tmp/converted_mattermost_data
./manage.py import '' /tmp/converted_mattermost_data/<team-name>
./scripts/start-server
```
Alternatively, to import into a custom subdomain, run: ```
unzip latest_export.zip -d /tmp/my_mattermost_export
mv /tmp/my_mattermost_export/import.jsonl /tmp/my_mattermost_export/export.json
cd /home/zulip/deployments/current
./scripts/stop-server
./manage.py convert_mattermost_data /tmp/my_mattermost_export --output /tmp/converted_mattermost_data
./manage.py import <subdomain> /tmp/converted_mattermost_data/<team-name>
./scripts/start-server
```
5. Follow step 4 of the guide for installing a new Zulip server.

#### Import details

Whether you are using Zulip Cloud or self-hosting Zulip, here are a few notes to keep in mind about the import process:

- Mattermost does not export workspace settings, so you will need to configure the settings for your Zulip organization. This includes settings like email visibility, message editing permissions, and how users can join your organization.
- Mattermost’s user roles are mapped to Zulip’s user
roles in the following way:
Mattermost role Zulip role Team administrator Owner Member Member
- Mattermost’s export tool does not support exporting user avatars or message edit history.
- Direct messages will only be imported from Mattermost workspaces containing a single team. This is because Mattermost’s data exports do not associate direct messages with a specific Mattermost team.
- Messages in threads are imported, but they are not explicitly marked as being in a thread.

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