# Delete a topic

**Note:**

This feature is only available to organization owners and administrators.

We generally recommend against deleting topics, but there are a few situations in which it can be useful:

- Clearing out test messages after setting up an organization.
- Clearing out messages from an overly enthusiastic bot.
- Managing abuse.

In most other cases, renaming a topic is often a better idea, or just leaving the topic as is. Deleting a topic can confuse users who come to the topic later via an email notification.

Note that deleting a topic also deletes every message with that topic, whereas archiving a channel does not.

### Delete a topic

**Desktop/Web:**

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Click **Delete topic**.
4. Approve by clicking **Confirm**.

**Mobile:**

Access this feature by following the web app instructions in your mobile device browser.

Implementation of this feature in the mobile app is tracked on GitHub. If you’re interested in this feature, please react to the issue’s description with 👍.

Note that deleting all of the individual messages within a particular topic also deletes that topic. Structurally, topics are simply an attribute of messages in Zulip.