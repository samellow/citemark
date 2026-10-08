# Channel permissions

Channels organize conversations based on who needs to see them. For example, it’s common to have a channel for each team in an organization. Because Zulip further organizes messages into conversations labeled with topics, there is generally no need to create dedicated channels for specific projects.

There are three types of channels in Zulip:

- Private channels (indicated by ), where joining and viewing messages requires being invited. You can choose whether new subscribers can see messages sent before they were subscribed.
- Public channels (indicated by ), which are open to everyone in your organization other than guests.
- Web-public channels (indicated by ), where anyone on the Internet can see messages without creating an account.

## Configure channel permissions

You can configure the following permissions for each channel, regardless of its type.

Subscription permissions:

- Who can administer the channel
- Who can subscribe themselves
- Who can subscribe anyone
- Who can unsubscribe anyone

Messaging permissions:

- Who can send messages
- Who can start new topics
- Whether topics are required

Moderation permissions:

- Who can move messages
- Who can resolve topics
- Who can delete messages

For the organization as a whole, you can:

- Restrict channel creation
- Restrict who can subscribe others to channels

Any permission, including whether a channel is private, public, or web-public, can be modified after the channel is created.

## Private channels

Private channels (indicated by ) are for conversations that should be visible to users who are specifically granted access. There are two types of private channels in Zulip:

- In private channels with **shared history**, new subscribers can access the
channel’s full message history. For example, a newly added team member can get
ramped up on a secret project by seeing prior discussions.
- In private channels with **protected history**, new subscribers can only see
messages sent after they join. For example, a new manager would not be able to
see past discussions regarding their own hiring process or performance management.

Organization administrators and channel administrators can see and manage metadata for private channels. However, if they aren’t subscribed to a private channel, they cannot gain access to its content, or grant access to others, unless specifically permitted to do so.

This means organization administrators and channel administrators can:

- See and modify the channel’s name and description.
- See who is subscribed to the channel, and unsubscribe them.
- Move the channel to another folder.
- See the channel’s permissions settings, and modify settings that do not affect content access (e.g., who can post or message retention policy).
- See how much message traffic the channel gets (but not its contents).
- Archive the channel.

However, the following actions require specific permissions.

- **Seeing messages and topics**: Restricted to channel subscribers, and user
who are allowed to subscribe themselves or any user.
- Subscribing yourself or other users
- Modifying settings that affect content access (e.g., making a channel public, or changing who can add subscribers).
- Modifying settings that affect notifications (e.g., enabling mobile notifications for new subscribers): Restricted to organization administrators.

Administrators can export messages in private channels only if granted permission to do so by a subscriber.

Users who do not have special permissions (they are not organization administrators, and have not been granted access to channel metadata) cannot easily see which private channels exist. They can find out that a channel exists only by attempting to create a channel with the same name, if they have permission to create channels. They can’t get any other information about private channels they are not subscribed to.

**Note:**

If you create a bot that is allowed to read messages
in a private channel (e.g., a **generic bot**, *not* an **incoming webhook bot**,
which is more limited), an administrator can in theory gain access to messages
in the channel by making themselves the bot’s owner.

## Public channels

Public channels (indicated by ) are open to all members of your organization other than guests. Anyone who is not a guest can:

- See information about the channel, including its name, description, permission settings, and subscribers.
- Subscribe or unsubscribe themselves to the channel.
- See all messages and topics, whether or not they are subscribed.

You can configure other permissions for public channels, such as who is allowed to post.

Guest users can’t see public (or private) channels, unless they have been specifically subscribed to the channel.

## Web-public channels

The public access option lets administrators configure selected channels to be
**web-public**. Web-public channels (indicated by a ) can be viewed by anyone on the Internet without creating
an account in your organization.

For example, you can link to a Zulip topic in a web-public channel from a GitHub issue, a social media post, or a forum thread, and anyone will be able to click the link and view the discussion in the Zulip web application without needing to create an account.

To see this feature in action, you can view web-public channels in the Zulip development community without logging in.

Users who wish to post content will need to create an account in order to do so.

Web-public channels are indicated with a **globe** () icon.