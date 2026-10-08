# Image, video and website previews

Zulip displays previews of images, videos, audio files and websites in your message feed. You can configure how animated images are previewed, or hide link previews on individual messages.

Organization administrators can:

- Configure the size of image and video previews.
- Configure whether website previews are shown.
- Configure whether previews of linked images and videos are shown.

## Configure how animated images are played

In the desktop and web apps, you can configure previews of animated images to always show the animation, show it when you hover over the image with your mouse, or not show it at all. For large animated images, only the first part of the animation will be shown in the preview.

You can always see the full animated image by opening it in the image viewer.

**Note:**

This configuration applies only to images uploaded since July 21, 2024 on Zulip Cloud, or on Zulip Server 9.0+ in self-hosted organizations. Previews of images uploaded earlier are always animated.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Preferences**.
4. Under **Information**, select the desired option from the **Play animated
images** dropdown.

## Hide or show link previews on a message

If a message shows a website preview or a video preview from a site like YouTube or Vimeo that you’d rather not see, you can hide it just for yourself, without changing how the message looks for anyone else.

1. Hover over a message to reveal three icons on the right.
2. Click on the **ellipsis** ().
3. Click **Hide link previews**.

 **Tip:** To bring the previews back, follow the same steps and click **Show link
previews**.

 **Keyboard tip:** You can use `Shift` + `L` to hide or show link previews on
the selected message.

## Configure image and video thumbnail size

**Note:**

This feature is only available to organization owners and administrators.

You can configure the size of image and video previews for users in your organization. Smaller previews avoid disrupting the flow of conversation, while larger ones reduce the need to open the image viewer.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Message feed settings**, select the desired option from the **Size
of images and videos in messages** dropdown.
5. Click **Save changes**.

## Configure whether website previews are shown

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Message feed settings**, toggle **Show previews of linked websites**.
5. Click **Save changes**.

## Configure whether previews of linked images and videos are shown

**Note:**

This feature is only available to organization owners and administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization settings**.
4. Under **Message feed settings**, toggle **Show previews of linked images
and videos**.
5. Click **Save changes**.

## Security

To prevent images from being used to track Zulip users, Zulip proxies all external images in messages through the server.