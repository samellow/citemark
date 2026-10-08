# Animated GIFs

**Note:**

On self-hosted servers, the GIF picker needs to be configured by a server administrator. You can choose between GIPHY, Tenor and KLIPY as your GIF provider.

Zulip makes it easy to find animated GIFs and use them in your messages, if the GIF picker is enabled in your organization.

You can customize how animated images are played in messages you receive. Administrators can configure the size of GIFs and other images in the message feed.

## Insert a GIF

**Desktop/Web:**

1. Click the **add GIF** () icon at
the bottom of the compose box.
2. Find a GIF you’d like to use.
3. Click on an image to insert it in the compose box.

 **Tip:** You can preview your message
before sending.

If previews of linked images are disabled in your organization, the GIF will appear as a link, rather than an image.

## Configure maximum GIFs rating

**Note:**

This feature is only available to organization owners and administrators.

You can configure the maximum rating of GIFs shown in the GIF picker, which by
default is set to GIFs rated **G (General audience)**.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Compose settings**, select a rating for **GIF picker**.
5. Click **Save changes**.

## Disable the GIF picker

**Note:**

This feature is only available to organization owners and administrators.

Disabling the GIF picker removes it from the compose box.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Compose settings**, set **GIF picker** to **Disabled**.
5. Click **Save changes**.

## Privacy

Zulip’s GIF picker uses a third-party service to provide GIFs (Tenor for Zulip Cloud). Any text you enter into the GIF search box will be sent from your browser directly to the corresponding service’s API. Because these requests are made client-side, the service you are querying (Tenor, GIPHY or KLIPY) will be able to see your IP address and may use that data for tracking, similar to if you visited their website and performed the same search there.

Zulip proxies all external images in messages through the server, including GIFs. This prevents images from being used to track recipients.