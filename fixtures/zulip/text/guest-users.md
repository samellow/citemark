# Guest users

You can add users who should have restricted access to your organization as
**guests**. For example, this may be a good choice for contractors or customers
invited to a company’s Zulip chat.

Guest users **can**:

- View and send messages in channels they have been subscribed to, including viewing message history in the same way as other channel subscribers.

Guest users **cannot**:

- See private or public channels, unless they have been specifically subscribed to the channel.
- Create new channels or user groups.
- Add or manage bots.
- Add custom emoji.
- Invite users to join the organization.

You can also **configure** other permissions for guest users, such as whether they
can:

- Move or edit messages.
- Notify a large number of users with a wildcard mention.

Zulip Cloud plans have special discounted pricing for guest users.

## Configure guest indicator

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Guests**, toggle **Display “(guest)” after names of guest users**.
5. Click **Save changes**.

## Configure warning when composing a DM to a guest

Zulip can display a warning to let users know when recipients for a direct message they are composing are guests in your organization. The warning will be shown as a banner in the compose box on the web and desktop apps.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Guests**, toggle **Warn when composing a DM to a guest**.
5. Click **Save changes**.

## Configure whether guests can see all other users

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to the Zulip Cloud Plus plan.

You can restrict guests’ ability to see other users in the organization. If you do so, guests will be able to see information about other users only in the following cases:

- The user belongs to a direct message thread with the guest.
- The user is subscribed to one or more channels with the guest.

When a guest cannot see information about a user, the guest’s experience will be that:

- The user does not appear in the right sidebar.
- The user does not appear in typeahead suggestions, e.g., in the compose box and search.
- Otherwise, such a user will be displayed as an **Unknown user** in the Zulip
app. For example, messages and reactions from a former subscriber of a channel
will be shown as from an **Unknown user**.
- An **Unknown user**’s user card will not display
information about that user. However, the guest can still search from all
messages send by a particular **Unknown user** from that user’s card.

In practice, guests should rarely encounter content from an **Unknown user**,
unless users in your organization frequently change their channel subscriptions
or are deactivated.

The only information guests can access about unknown users via the API is which user IDs exist, and availability updates for each user ID.

 **Tip:** Self-hosted organizations can disable API access to availability updates
by configuring
`CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE = True`. For performance reasons,
this is recommended only for organizations with up to \~100 users.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Guests**, configure **Who can view all other users in the
organization**.
5. Click **Save changes**.