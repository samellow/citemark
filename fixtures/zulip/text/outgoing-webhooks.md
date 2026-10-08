# Outgoing webhooks

Outgoing webhooks allow you to build or set up Zulip integrations which are notified when certain types of messages are sent in Zulip. When one of those events is triggered, the Zulip server will send an HTTP POST payload to the webhook’s configured URL.

Outgoing webhooks can be used to power a wide range of Zulip integrations. For example, the Zulip Botserver is built on top of this API.

## Create an outgoing webhook bot user

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Bots**.
4. Click **Add a new bot**.
5. Set **Bot type** to **Outgoing webhook**.
6. Fill out the fields, with **Endpoint URL** set to the URL you’d like
Zulip to post to, and the outgoing webhook format
you plan on using.
7. Click **Add**.

## Triggering

There are currently two ways to trigger an outgoing webhook:

- **@-mention** the bot user in a channel.  If the bot
replies, its reply will be sent to that
channel and topic.
- **Send a direct message** with the bot user as one of the recipients.
If the bot replies, its reply will be
sent to that direct message conversation.

## Timeouts

The remote server must respond to a `POST` request in a timely manner.
The default timeout for outgoing webhooks is 10 seconds, though this
can be configured by the administrator of the Zulip server by setting
`OUTGOING_WEBHOOKS_TIMEOUT_SECONDS` in the server’s
settings.

## Replying with a message

Many bots implemented using this outgoing webhook API will want to send a reply message into Zulip. Zulip’s outgoing webhook API provides a convenient way to do that by simply returning an appropriate HTTP response to the Zulip server.

A correctly implemented bot will return a JSON object containing one of two possible formats, described below.

### Example response payloads

If the bot code wants to opt out of responding, it can explicitly
encode a JSON object that contains `response_not_required` set
to `True`, so that no response message is sent to the user.  (This
is helpful to distinguish deliberate non-responses from bugs.)

Here’s an example of the JSON your server should respond with if you would not like to send a response message:

```
{
    "response_not_required": true
}
```
Here’s an example of the JSON your server should respond with if you would like to send a response message:

```
{
    "content": "Hey, we just received **something** from Zulip!"
}
```
The `content` field should contain Zulip-flavored Markdown.

Note that an outgoing webhook bot can use the Zulip REST API with its API key in case your bot needs to do something else, like add an emoji reaction or upload a file.