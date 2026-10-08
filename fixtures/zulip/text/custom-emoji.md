# Custom emoji

Custom emoji can be used by all users in an organization (including bots). They are supported everywhere that Zulip supports emoji, including emoji reactions, messages, channel descriptions and user statuses.

## Add custom emoji

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom emoji**.
4. Click **Add a new emoji**.
5. Click **Upload image or GIF**, and add a file in the PNG, JPG, or
GIF file format. Zulip will automatically scale the image down to
25x25 pixels.
6. Enter an **Emoji name**, and click **Confirm**.

**Emoji names** can only contain `a-z`, `0-9`, dashes (`-`), and spaces.
Upper and lower case letters are treated the same, and underscores (`_`)
are treated the same as spaces.

### Bulk add emoji

We expose a REST API endpoint for bulk uploading emoji. Using REST API endpoints requires some technical expertise; contact us if you get stuck.

## Replace a default emoji

You can replace a default emoji by adding a custom emoji of the same name. If an emoji has several names, you must use the emoji’s primary name to replace it. You can find the primary name of an emoji by hovering over it in the emoji picker, while the search box is empty (you may have to scroll down a bit to find it).

## Deactivate custom emoji

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Custom emoji**.
4. Click the **deactivate** () icon next to the
emoji that you would like to deactivate.

Deactivating an emoji will not affect any existing messages or emoji reactions. Anyone can deactivate custom emoji they added, and organization administrators can deactivate anyone’s custom emoji.

## Change who can add custom emoji

**Note:**

This feature is only available to organization owners and administrators.

You can configure who can add custom emoji. This permission can be granted to any combination of roles, groups, and individual users.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Other permissions**, configure **Who can add custom emoji**.
5. Click **Save changes**.