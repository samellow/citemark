# Global times

When collaborating with people in different time zones, you often need to express a specific time clearly. In Zulip, rather than typing out your time zone and having everyone translate the time in their heads, you can insert a time, and it will be displayed to each user in their own time zone (just like timestamps on Zulip messages).

## Insert a time

**Via compose box button:**

1. Open the compose box.
2. Click the **add global time** ()
icon at the bottom of the compose box to open the date picker.
3. Select the desired time by clicking with your mouse, or using the arrow
keys + `Enter`.
4. Click **Confirm** to insert the selected time.

**Via Markdown:**

1. Open the compose box.
2. Type `<time`, and click **Mention a time-zone-aware time**, or press `Enter` to open the date picker.
3. Select the desired time by clicking with your mouse, or using the arrow
keys + `Enter`.
4. Click **Confirm** to insert the selected time.

## Examples

### What you type

A date picker will appear once you type `<time`.

`Our next meeting is scheduled for <time:2024-08-06T17:00:00+01:00>.`
The selected time is inserted into your Markdown message along with your time zone (in ISO 8601 format).

### What it looks like

A person in San Francisco will see:

While someone in London will see: