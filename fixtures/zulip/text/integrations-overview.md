# Integrations overview

Integrations let you connect Zulip with other products. For example, you can get notification messages in Zulip when an issue in your tracker is updated, or for alerts from your monitoring tool.

Zulip offers over 120 native integrations, which take advantage of Zulip’s topics to organize notification messages. Additionally, thousands of integrations are available through Zapier and IFTTT. You can also connect any webhook designed to work with Slack to Zulip.

If you don’t find an integration you need, you can:

- Write your own integration. You can submit a pull request to get your integration merged into the main Zulip repository.
- File an issue to request an integration (if it’s a nice-to-have).
- Contact Zulip Sales to inquire about a custom development contract.

## Set up an integration

### Native integrations

1. Search Zulip’s integrations for the product you’d like to connect to Zulip.
2. Click on the card for the product, and follow the instructions on the page.

### Integrate via Zapier or IFTTT

If you don’t see a native Zulip integration, you can access thousands of additional integrations through Zapier and IFTTT.

1. Search Zapier or IFTTT for the product you’d like to connect to Zulip.
2. Follow the integration instructions for Zapier or IFTTT.

### Integrate via Slack-compatible webhook API

Zulip can process incoming webhook messages written to work with Slack’s webhook API. This makes it easy to quickly move your integrations when migrating your organization from Slack to Zulip, or integrate any product that has a Slack webhook integration with Zulip .

**Note:** In the long term, the recommended approach is to use
Zulip’s native integrations, which take advantage of Zulip’s topics.
There may also be some quirks when Slack’s formatting system is
translated into Zulip’s.

1. Create a bot for the Slack-compatible
webhook. Make sure that you select **Incoming webhook** as the **Bot type**.
2. Decide where to send Slack-compatible webhook notifications, and generate the integration URL.
3. Use the generated URL anywhere you would use a Slack webhook.

### Integrate via email

If the product you’d like to integrate can send email notifications, you can send those emails to a Zulip channel. The email subject will become the Zulip topic, and the email body will become the Zulip message.

For example, you can configure your personal GitHub notifications to go to a Zulip channel rather than your email inbox. Notifications for each issue or pull request will be grouped into a single topic.

## Write your own integration

You can write your own Zulip integrations using the well-documented APIs below. For example, if your company develops software, you can create a custom integration to connect your product to Zulip.

If you need help, best-effort community support is available in the Zulip development community. To inquire about options for custom development, contact Zulip Sales.

### Sending content into Zulip

- If the third-party service supports outgoing webhooks, you likely want to build an incoming webhook integration.
- If it doesn’t, you may want to write a script or plugin integration.
- The `zulip-send` tool makes it easy to send Zulip
messages from shell scripts.
- Finally, you can send messages using Zulip’s API, with bindings for Python, JavaScript and other languages.

### Sending and receiving content

- To react to activity inside Zulip, look at Zulip’s Python framework for interactive bots or Zulip’s real-time events API.
- If what you want isn’t covered by the above, check out the full REST API. The web, mobile, desktop, and terminal apps are built on top of this API, so it can do anything a human user can do. Most but not all of the endpoints are documented on this site; if you need something that isn’t there check out Zulip’s REST endpoints.