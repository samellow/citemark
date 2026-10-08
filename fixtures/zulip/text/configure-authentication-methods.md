# Configure authentication methods

**Note:**

This feature is only available to organization owners.

You can choose which authentication methods to enable for users to log in to your organization. The following options are available on all plans:

- Email and password
- Social authentication: Google, GitHub, GitLab, Apple, Discord

The following options are available for organizations on Zulip Cloud Standard, Zulip Cloud Plus, and all self-hosted Zulip servers:

- Oauth2 with Microsoft Entra ID (AzureAD)

The following options are available for organizations on Zulip Cloud Plus, and all self-hosted Zulip servers:

- SAML authentication, including Okta, OneLogin, Entra ID (AzureAD), Keycloak, Auth0
- OpenID Connect
- SCIM provisioning

The following authentication and identity management options are available for all self-hosted servers. If you are interested in one of these options for a Zulip Cloud organization, contact support@zulip.com to inquire.

- AD/LDAP user sync
- AD/LDAP group sync
- Custom authentication options with python-social-auth

### Configure authentication methods

**Note:**

For self-hosted organizations, some authentication options require that you first configure your server to support the option.

 **Tip:** Before disabling an authentication method, test that you can
successfully log in with one of the remaining authentication methods.
The `change_auth_backends` management
command
can help if you accidentally lock out all administrators.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Authentication methods**.
4. To use SAML authentication or SCIM provisioning, Zulip Cloud organizations must upgrade to Zulip Cloud Plus, and contact support@zulip.com to enable these methods.
5. Toggle the checkboxes next to the available login options.
6. Click **Save changes**.