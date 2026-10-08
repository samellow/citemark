# Share and upload files

You can attach multiple files to messages, including images, documents, videos, and sound files.

Zulip shows previews of attached images, videos, and audio files, and lets you click on a preview to view an image in more detail or play a video. You can browse all images and videos attached to messages in your current view in the image viewer.

## Uploading files

Images, videos and sound files you upload will be previewed directly in your message. Other files will appear as named links for downloading. You can rename files after uploading.

**Via drag-and-drop:**

1. Drag and drop one or more files anywhere in the Zulip app, whether or not the compose box is open.
2. *(optional)* Modify the name of the uploaded file as desired.

 **Tip:** You can preview the message
before sending to see what your uploaded files will look like.

**Via paste:**

1. Open the compose box.
2. Copy and paste one or more files into the compose box.
3. *(optional)* Modify the name of the uploaded file as desired.

 **Tip:** You can preview the message
before sending to see what your uploaded files will look like.

**Via compose box button:**

1. Open the compose box.
2. Click the **paperclip** ()
icon at the bottom of the compose box to select one or more files.
3. *(optional)* Modify the name of the uploaded file as desired.

 **Tip:** You can preview the message
before sending to see what your uploaded files will look like.

**Mobile:**

1. Navigate to a channel, topic, or direct message view.
2. Tap the
**paperclip** (), **image** (),
or **camera** ()
button at the bottom of the app to select one or more files.
3. *(optional)* Modify the name of the uploaded file as desired.

## Sharing files from other mobile apps

**Android:**

1. In another mobile app, select text or one or more files, and tap the
**share** button.
2. Tap the **Zulip** () logo to share to Zulip.
3. *(optional)* Tap the organization profile picture in the top right
corner of the app to switch to another account.
4. To send a channel message, select a channel and type a topic name.
To send a direct message, tap the **Direct message** tab, and choose
an existing direct message conversation or tap the **New DM** button
at the bottom of the screen and select message recipients.
5. *(optional)* Write a message.
6. Tap the **Send** button.

**iOS:**

Implementation of this feature for the IOS version of the mobile app is tracked on GitHub. If you’re interested in this feature, please react to the issue’s description with 👍.

## Convert pasted to text to a file

When pasting a large amount of text, you can convert it to a text file upload.

**Desktop/Web:**

1. Paste a large amount of text into the compose box (2,000+ characters).
2. In the banner above the compose box, click **Convert** to convert the
pasted text to a file.

## File upload limits

The Zulip Cloud Standard and Zulip Cloud Plus plans include 5 GB of file storage per user. Each uploaded file can be up to 1 GB.

The Zulip Cloud Free plan includes a total of 5 GB of file storage. Each uploaded file can be up to 10 MB.

In organizations on a self-hosted server, server administrators can configure
the maximum size for uploaded files via the `MAX_FILE_UPLOAD_SIZE`
server setting. Setting it to 0 disables file uploads, and
hides the UI for uploading files from the web and desktop apps.