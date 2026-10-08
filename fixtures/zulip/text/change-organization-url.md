# Change organization URL

**Note:**

This feature is only available to organization owners.

Zulip supports changing the URL for an organization. Users who navigate to the old URL in the browser will see a notice about the organization being moved, prior to being redirected to the new URL. Links to channels, topics and messages will thus continue to work.

When you change the URL:

- All users will be logged out of the web, mobile and desktop apps.
- Any API clients or integrations will need to be updated to point to the new organization URL.

 **Tip:** Consider using a wildcard
mention
in an announcement channel to let users know about an upcoming change.

## Change your Zulip Cloud subdomain

Zulip Cloud organizations are generally hosted at `<subdomain>.zulipchat.com`,
with the subdomain chosen when the organization was created. Organization
owners can request to change the subdomain.

Please email support@zulip.com with the following information:

1. Your organization’s current subdomain.
2. The subdomain you would like to move your organization to.
3. Whether you want links to the old subdomain to redirect to the new one for an extended period of time. By default, the old subdomain may be freed up for reuse after 3 months.

## Move to a custom URL on Zulip Cloud

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to the Zulip Cloud Plus plan.

Because maintaining custom URLs requires effort from our operational team, this feature is available only for organizations with 25+ Zulip Cloud Plus licenses.

Please email support@zulip.com with the following information:

1. Your organization’s current URL.
2. The URL you would like to move your organization to.

## Change the URL for your self-hosted server

If you’re self-hosting, you can change the root domain of your Zulip
server by changing the `EXTERNAL_HOST` setting.  If
you’re hosting multiple organizations
and want to change the subdomain for one of them, you can do this
using the `change_realm_subdomain` management command.

In addition to configuring Zulip as detailed here, you also need to generate SSL certificates for your new domain.