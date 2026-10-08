# Move from self-hosting to Zulip Cloud

With Zulip’s high quality import and export tools, you can always move from self-hosting your own Zulip server to using the Zulip Cloud service (and back).

## Process overview

To move your Zulip organization from a self-hosted server to Zulip Cloud, you will need to take the following steps, which are described in more detail below:

1. Plan the process and coordinate with Zulip support.
2. Upgrade your self-hosted server.
3. Export organization data.
4. Decide how users will log in.

## Plan the process and coordinate with Zulip support

To import your self-hosted organization into Zulip Cloud, your server will need to have the same database format as Zulip Cloud. Zulip Cloud is updated every couple of weeks, so it’s important to coordinate the timing with Zulip’s support team.

1. Review the process described on this page, and decide when you will be ready to make the transition.
2. Email support@zulip.com with the following information:
  - URL of the organization you plan to migrate
  - Your estimated timeline for generating a data export
  - Any other timing considerations for the transition (e.g., time of day)
  - If you’re planning to purchase the Zulip Cloud Plus plan, details on the Plus plan features (e.g., authentication methods) you intend to use. These features will be configured for your organization as part of the import process.

Zulip’s support team will coordinate with you to make the transition with minimal disruption for your team.

## Upgrade your self-hosted server

You will need to upgrade your server to use the same database format
as Zulip Cloud, using the published `zulip-cloud-current` branch.

1. Check your Zulip server version.
2. Upgrade to the latest maintenance release if you are running an older version of the Zulip server.
3. Upgrade
to the `zulip-cloud-current` branch.

For additional support with upgrading from an older version of Zulip, contact sales@zulip.com for paid support options.

## Export organization data

1. Make sure you have a plan for when the import into Zulip Cloud will take place.
2. Announce the migration and schedule Zulip downtime for your team.
3. Follow these instructions to export your Zulip data.
4. Send an email to support@zulip.com with:
  - Your data export file (`.tar.gz` format).
  - The subdomain you would like to use for your organization. Your Zulip
Cloud organization will be hosted at `<subdomain>.zulipchat.com`.

Zulip’s support team will let you know when the data import process is complete.

## Decide how users will log in

When user accounts are imported, users initially do not have passwords configured. There are a few options for how users can log in for the first time.

 **Tip:** For security reasons, passwords are never exported.

### Allow users to log in with non-password authentication

Users will immediately be able to log in with authentication methods that do not require a password, if these authentication methods are enabled.

### Send password reset emails to all users

You can ask support@zulip.com to send password reset emails to all users in your organization, which will allow them to set an initial password.

**Note:**

To avoid confusion, first make sure that the users in your organization are aware that their account has been moved, and are expecting to receive a password reset email.

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions on your Zulip organization’s login page.

## Advantages of Zulip Cloud

- **No setup or maintenance overhead:** Zulip Cloud is a simple SaaS solution,
so you don’t need to set up your own server. It only take a minute to sign
up.
- **Always up to date:** Zulip Cloud is updated every couple of weeks with the
latest version of Zulip. In contrast, new features are
released for self-hosted
installations twice a year (with maintenance
releases in between).
- **Operated by experts:** Zulip Cloud is operated by the core team developing
Zulip, with deep expertise in running your mission-critical chat software with
minimal downtime.
- **Free to get started:** Zulip Cloud Free
makes it easy to get started, and has all the features you need for casual
use.