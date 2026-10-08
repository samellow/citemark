# Resolve a topic

Zulip’s topics are very helpful for customer support, answering questions, investigating issues and production errors, as well as other workflows. Resolving topics makes it easy to track the status of each question, investigation, or notification.

Marking a topic as resolved:

- Puts a ✔ at the beginning of the topic name, e.g., `example topic` becomes `✔ example topic`.
- Triggers an automated notice from Notification Bot indicating that you resolved the topic. Users can configure whether these notices are automatically marked as read.
- Changes whether the topic appears when using the `is:resolved` and `-is:resolved` search filters.

Marking a topic as unresolved removes the ✔ and also triggers an automated notice from Notification Bot.

It’s often helpful to define a policy for when to resolve topics that fits how topics are used in a given channel. Here are some common approaches for deciding when to mark a topic as resolved:

- **Support**: When the support interaction is complete. Resolving
topics is particularly useful for internal support teams that might
not need a dedicated support ticket tracker.
- **Issues, errors and production incidents**: When investigation or
incident response is complete, and any follow-up work has been
transferred to the appropriate tracker.
- **Workflow management**: When the work described in the topic is
complete and any follow-ups have been transcribed.
- **Answering questions**: When the question has been fully answered,
and follow-ups would be best discussed in a new topic.

Users can resolve or unresolve a topic if they have permission to do so.

## Mark a topic as resolved

**Desktop/Web:**

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Select **Mark as resolved**.

 **Tip:** You can also click on the **mark as resolved** ()
icon in the message recipient bar to mark an unresolved topic as resolved.

**Mobile:**

1. Press and hold a topic until the long-press menu appears.
2. Tap **Mark as resolved**.

 **Tip:** If you are viewing a single topic, you can access the long-press
menu from the bar at the top of the app.

## Mark a topic as unresolved

Marking a topic as unresolved normally triggers an automated notice from Notification Bot. However, unresolving a topic right after you resolved it removes the original notice instead. This is helpful if you resolved a topic by accident.

**Desktop/Web:**

1. Hover over a topic in the left sidebar.
2. Click on the **ellipsis** ().
3. Select **Mark as unresolved**.

 **Tip:** You can also click on the **ellipsis** ()
in the message recipient bar, and select the **Mark as unresolved** option.

**Mobile:**

1. Press and hold a topic until the long-press menu appears.
2. Tap **Mark as unresolved**.

 **Tip:** If you are viewing a single topic, you can access the long-press
menu from the bar at the top of the app.

## Search for messages in unresolved topics

**Desktop/Web:**

1. Click the **search** () icon in the top bar to open the search box.
2. Type `-is:resolved`, or start typing and select **Exclude topics marked as
resolved** from the typeahead.
3. *(optional)* Enter additional search terms or
filters.
4. Press `Enter`.

 **Keyboard tip:** You can also use the `/` or `Ctrl` + `K`
keyboard shortcut to start searching messages.

 **Tip:** To get a feed of unread messages in all unresolved topics, search for
`is:unresolved is:unread`.

## Search for messages in resolved topics

**Desktop/Web:**

1. Click the **search** () icon in the top bar to open the search box.
2. Type `is:resolved`, or start typing and select **Topics marked as resolved** from the typeahead.
3. *(optional)* Enter additional search terms or
filters.
4. Press `Enter`.

 **Keyboard tip:** You can also use the `/` or `Ctrl` + `K`
keyboard shortcut to start searching messages.

## Filter by whether topics are resolved

**Desktop/Web:**

1. Click on a channel in the left sidebar.
2. Click **show all topics** at the bottom of the list of recent topics in the
selected channel.
3. In the search box at the top of the list of topics, type `is:`.
4. Choose **unresolved** or **resolved** from the typeahead suggestions.

## Configure whether resolved topic notices are marked as read

Zulip lets you automatically mark as read Notification Bot notices indicating that someone resolved or unresolved a topic, or do so just for topics you don’t follow.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Notifications**.
4. Under **Topic notifications**, configure **Automatically mark resolved topic
notices as read**.

## Sending messages to resolved topics

You can send messages to a resolved topic, which is handy for *“thank you”*
messages, or to discuss whether a topic was incorrectly marked as resolved.

When a topic is resolved or unresolved, users’ compose boxes and message views automatically update to show the topic’s current state. This helps make sure everyone sends messages to the correct place.

Integrations will still send messages to the original topic after a topic is resolved. This is useful for alerting integrations, where a repeating alert might have a different cause. As usual, you can mark the topic resolved once you’ve investigated the situation.