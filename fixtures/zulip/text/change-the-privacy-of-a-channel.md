# Change the privacy of a channel

There are three types of channels in Zulip:

- Private channels (indicated by ), where joining and viewing messages requires being invited. You can choose whether new subscribers can see messages sent before they were subscribed.
- Public channels (indicated by ), which are open to everyone in your organization other than guests.
- Web-public channels (indicated by ), where anyone on the Internet can see messages without creating an account.

Organization administrators and channel administrators can always make a channel private. However, they can only make a private channel public or web-public if they have content access to it:

- They are subscribed to the channel, or
- They have the permission to add subscribers (themselves or others) to the channel.

**Note:**

**Warning**: Be careful making a private channel public. All past messages
will become accessible, even if the channel previously had protected history.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Select a channel.
5. Select the **Permissions** tab on the right.
6. Under **Subscription permissions**, configure **Who can access this channel**.
7. Click **Save changes**.

 **Tip:** You can also click on a channel name in the navigation bar at the top of the
app to access its settings, or use the **ellipsis** ()
next to the channel name in the left sidebar.

**Mobile:**

Access this feature by following the web app instructions in your mobile device browser.

Implementation of this feature in the mobile app is tracked on GitHub. If you’re interested in this feature, please react to the issue’s description with 👍.