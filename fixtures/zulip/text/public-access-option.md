# Public access option

The public access option lets administrators configure selected channels to be
**web-public**. Web-public channels (indicated by a ) can be viewed by anyone on the Internet without creating
an account in your organization.

For example, you can link to a Zulip topic in a web-public channel from a GitHub issue, a social media post, or a forum thread, and anyone will be able to click the link and view the discussion in the Zulip web application without needing to create an account.

To see this feature in action, you can view web-public channels in the Zulip development community without logging in.

Users who wish to post content will need to create an account in order to do so.

## Enabling web-public channels in your organization

Enabling web-public channels makes it possible to create web-public channels in your organization. It also makes certain information about your organization accessible to anyone on the Internet via the Zulip API (details below).

To help protect closed organizations, creating web-public channels is disabled by default for all organizations.

### Information that can be accessed via API when web-public channels are enabled

The following information about your organization can be accessed via the Zulip API if web-public channels are enabled and there is currently at least one web-public channel.

- The organization’s settings (linkifiers, custom emoji, permissions settings, etc.)
- Names of users
- Names of user groups and their membership
- Names and descriptions of channels

Enabling web-public channels is thus primarily recommended for open communities such as open-source projects and research communities.

### Enable or disable web-public channels

**Note:**

Self-hosted Zulip servers must enable support for web-public channels in their
server settings
by setting `WEB_PUBLIC_STREAMS_ENABLED = True` prior to proceeding.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Channel permissions**, toggle the checkbox labeled **Allow
creating web-public channels (visible to anyone on the Internet)**.

### Manage who can create web-public channels

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Channel permissions**, make sure the checkbox labeled **Allow
creating web-public channels (visible to anyone on the Internet)** is
checked.
5. Under **Who can create web-public channels?**, select the option you prefer.

 **Tip:** See Managing abuse to learn why only
trusted roles like moderators and administrators can create web-public channels.

## Creating a web-public channel

To create a new web-public channel, follow the instructions for creating a
channel, selecting the **Web-public** option for **Who
can access this channel**.

To make an existing channel web-public, follow the instructions to
change the privacy of a
channel, selecting the
**Web-public** option for **Who can access this channel**.

## What can logged out visitors do?

Logged out visitors can browse all content in web-public channels, including using Zulip’s built-in search to find conversations. Logged out visitors can only access the web-public channels in your organization, and the topics, messages (including uploaded files) and emoji reactions in those channels.

They **cannot**:

- View channels that are not configured as web-public channels (or see whether any such channels exist) without creating an account.
- Send messages.
- React with emoji.
- Participate in polls, or do anything else that might be visible to other users.

Logged out visitors have access to a subset of the metadata information available to any new account in the Zulip organization, detailed below.

### Information about the organization

- The **Organization settings** and **Channel settings** menus are not
available to logged out visitors. However, organization settings data is
required for Zulip to load, and may thus be accessed via the Zulip API.
- Logged out visitors cannot view usage statistics.

### Information about users

Logged out visitors can see the following information about users who participate in web-public channels. They do not see this information about users who do not participate in web-public channels in the Zulip UI, though they may access it via the Zulip API.

- Name
- Avatar
- Role (e.g., Administrator)
- Join date

The following additional information is not available in the UI for logged out visitors, but may be accessed without an account via the Zulip API:

- Configured time zone
- Which user groups a user belongs to

The following information is available to all users with an account, but not to logged out visitors:

- Presence information, i.e. whether the user is currently online, their status, and whether they have set themselves as unavailable.
- Detailed profile information, such as custom profile fields.
- Which users are subscribed to which web-public channels.

## Managing abuse

The unfortunate reality is that any service that allows hosting files visible to the Internet is a potential target for bad actors looking for places to distribute illegal or malicious content.

In order to protect Zulip organizations from bad actors, web-public channels have a few limitations designed to make Zulip an inconvenient target:

- Only users in trusted roles (moderators and administrators) can be given permission to create web-public channels. This is intended to make it hard for an attacker to host malicious content in an unadvertised web-public channel in a legitimate organization.
- There are rate limits for unauthenticated access to uploaded files, including viewing avatars and custom emoji.

Our aim is to tune anti-abuse protections so that they don’t interfere with legitimate use. Please contact us if your organization encounters any problems with legitimate activity caused these anti-abuse features.

As a reminder, Zulip Cloud organizations are expected to moderate content to ensure compliance with Zulip’s Rules of Use.

## Caveats

- Web-public channels do not yet support search engine indexing. You can use zulip-archive to create an archive of a Zulip organization that can be indexed by search engines.
- The web-public view is not yet integrated with Zulip’s live-update system. As a result, a visitor will not see new messages that are sent to a topic they are currently viewing without reloading the browser window.