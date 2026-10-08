# Community moderation toolkit

Zulip offers a comprehensive toolkit for moderating communities.

## Prevention

Zulip has many features designed to simplify moderation by preventing problematic behavior.

### Manage new users

- Decide whether to allow anyone to create an account, or require invitations to join.
- Link to a code of conduct in your organization description (displayed on the registration page) and custom welcome message.
- Disallow disposable email addresses or limit authentication methods to increase the effort for a bad actor to replace a banned account.
- Add a waiting period before new users can take disruptive actions.
- Monitor new users by enabling new user announcements.

### Restrict permissions for making changes

- Restrict who can create channels, or monitor new channels by enabling new channel announcements.
- Restrict who can add custom emoji.
- Restrict who can move messages to another channel, and set a time limit for editing topics.
- Restrict who can edit and delete messages, and set time limits on message editing and deletion.
- If you are concerned about impersonation, you can prevent users from changing their name, or require unique names.

### Minimize spam

- Configure email visibility to prevent off-platform spam.
- Restrict wildcard mentions so only moderators can mention everyone in your organization.
- Create a default channel for announcements where only admins can post.
- Configure who can authorize and start direct message conversations.

## Monitoring

- Enable moderation requests to make it easy to report problematic messages to community moderators.
- Configure alert words to get notified when a problematic word or phrase is included in a message.

## Response

The following features are an important part of an organization’s playbook when responding to abuse or spam that is not prevented by the organization’s policy choices.

- Individual users can mute abusive users to stop harassment that moderators have not yet addressed, or collapse individual messages that they don’t want to see.
- Ban (deactivate) users acting in bad faith. They will not be able to rejoin using the same email address, unless their account is reactivated by an administrator. You can choose whether to delete the user’s name, profile picture, and messages they’ve sent (e.g., their DMs or channel messages).
- Investigate behavior by viewing messages sent by a user.
- Delete messages, archive channels, and unsubscribe users from channels.
- Move topics, including between channels, when users start conversations in the wrong place.
- Change users’ names (e.g., to “Name (Spammer)”) for users who sent spam direct messages to many community members.
- Deactivate bots or deactivate custom emoji.

## Public access option

The public access option lets administrators configure selected channels to be
**web-public**. Web-public channels (indicated by a ) can be viewed by anyone on the Internet without creating
an account in your organization.

For example, you can link to a Zulip topic in a web-public channel from a GitHub issue, a social media post, or a forum thread, and anyone will be able to click the link and view the discussion in the Zulip web application without needing to create an account.

To see this feature in action, you can view web-public channels in the Zulip development community without logging in.

Users who wish to post content will need to create an account in order to do so.

## Zulip communities directory

The Zulip communities directory offers publicly accessible Zulip Cloud organizations an opportunity to be listed on the Zulip website. It’s a way for open-source projects, research communities, and others to advertise their Zulip community and support the Zulip project.

The directory will display your community’s name, logo, and a link to you Zulip chat. Other information from your organization profile and the size of your organization may be included as well.

For details on how to get your community listed, see Communities directory.