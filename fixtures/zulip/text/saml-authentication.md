# SAML authentication

**Note:**

This feature is only available to organization owners and administrators.

Zulip supports using SAML authentication for single sign-on, both for Zulip Cloud and self-hosted Zulip servers. SAML Single Logout is also supported.

This page describes how to configure SAML authentication with several common providers:

- Okta
- OneLogin
- Entra ID (AzureAD)
- Keycloak
- Auth0

Other SAML providers are supported as well.

If you are self-hosting Zulip, please follow the detailed setup instructions in the SAML configuration for self-hosting. The documentation on this page may be a useful reference for how to set up specific SAML providers.

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to the Zulip Cloud Plus plan.

## Configure SAML

**Okta:**

1. Make sure your Zulip Cloud organization is on the Zulip Cloud Plus plan.
2. Set up SAML authentication by following
Okta’s documentation.
Specify the following fields, skipping **Default RelayState** and **Name ID format**:
  - **Single sign on URL**: `https://auth.zulipchat.com/complete/saml/`
  - **Audience URI (SP Entity ID)**: `https://zulipchat.com`
  - **Application username format**: `Email`
  - **Attribute statements**:
    - `email` to `user.email`
    - `first_name` to `user.firstName`
    - `last_name` to `user.lastName`
3. Assign the appropriate accounts in the **Assignments** tab. These are the users
that will be able to log in to your Zulip organization.
4. If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information: 
  - Your organization’s URL
  - The **Identity Provider metadata** provided by Okta for the application.
To get the data, click the **View SAML setup instructions button** in
the right sidebar in the **Sign on** tab.
Copy the IdP metadata shown at the bottom of the page.
  - How you would like the Zulip log in button to be labeled: “Log in with…”
  - *(optional)* An icon to use on the log in button

**OneLogin:**

1. Make sure your Zulip Cloud organization is on the Zulip Cloud Plus plan.
2. Navigate to the OneLogin **Applications** page, and click **Add App**.
3. Search for the **SAML Custom Connector (Advanced)** app and select it.
4. Set a name and logo and click **Save**. This doesn’t affect anything in Zulip,
but will be shown on your OneLogin **Applications** page.
5. In the **Configuration** section, specify the following fields. Leave the
remaining fields as they are, including blank fields.
  - **Audience**: `https://zulipchat.com`
  - **Recipient**: `https://auth.zulipchat.com/complete/saml/`
  - **ACS URL**: `https://auth.zulipchat.com/complete/saml/`
  - **ACS URL Validator**: `https://auth.zulipchat.com/complete/saml/`
6. In the **Parameters** section, add the following custom parameters. Set the **Include in SAML assertion** flag on each parameter.
Field name Value email Email first\_name First Name last\_name Last Name username Email
7. If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information: 
  - Your organization’s URL
  - The **issuer URL** from the **SSO** section. It contains required **Identity Provider** metadata.
  - How you would like the Zulip log in button to be labeled: “Log in with…”
  - *(optional)* An icon to use on the log in button

**Entra ID (AzureAD):**

1. Make sure your Zulip Cloud organization is on the Zulip Cloud Plus plan.
2. From your Entra ID Dashboard, navigate to **Enterprise applications**,
click **New application**, followed by **Create your own application**.
3. Enter a name (e.g., `Zulip Cloud`) for the new Entra ID application,
choose **Integrate any other application you don’t find in the
gallery (Non-gallery)**, and click **Create**.
4. From your new Entra ID application’s **Overview** page that opens, go to **Single sign-on**, and select **SAML**.
5. In the **Basic SAML Configuration** section, specify the following fields:
  - **Identifier (Entity ID)**: `https://zulipchat.com`
  - **Default**: *checked* (This is required for enabling IdP-initiated sign on.)
  - **Reply URL (Assertion Consumer Service URL)**: `https://auth.zulipchat.com/complete/saml/`
6. If you want to set up IdP-initiated sign on, in the **Basic SAML
Configuration** section, also specify:
  - **RelayState**: `{"subdomain": "<your organization's zulipchat.com subdomain>"}`
7. Check the **User Attributes & Claims** configuration, which should already be
set to the following. If the configuration is different, please
indicate this when contacting support@zulip.com
(see next step).
  - **givenname**: `user.givenname`
  - **surname**: `user.surname`
  - **emailaddress**: `user.mail`
  - **name**: `user.principalname`
  - **Unique User Identifier**: `user.principalname`
8. If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information: 
  - Your organization’s URL
  - From the **SAML Signing Certificate** section:
    - **App Federation Metadata Url**
    - Certificate downloaded from **Certificate (Base64)**
  - From the **Set up** section
    - **Login URL**
    - **Microsoft Entra Identifier**
  - How you would like the Zulip log in button to be labeled: “Log in with…”
  - *(optional)* An icon to use on the log in button

**Keycloak:**

1. Make sure your Zulip Cloud organization is on the Zulip Cloud Plus plan.
2. Make sure your Keycloak server is up and running.
3. In Keycloak, register a new Client for your Zulip organization: 
  - **Client-ID**: `https://zulipchat.com`
  - **Client Protocol**: `saml`
  - **Client SAML Endpoint**: *(empty)*
4. In the **Settings** tab for your new Keycloak client, set the following properties:
  - **Valid Redirect URIs**: `https://auth.zulipchat.com/*`
  - **Base URL**: `https://auth.zulipchat.com/complete/saml/`
  - **Client Signature Required**: `Disable`
5. In the **Mappers** tab for your new Keycloak client:
  - Create a Mapper for the first name:
    - **Property**: `firstName`
    - **Friendly Name**: `first_name`
    - **SAML Attribute Name**: `first_name`
    - **SAML Attribute Name Format**: `Basic`
  - Create a Mapper for the last name:
    - **Property**: `lastName`
    - **Friendly Name**: `last_name`
    - **SAML Attribute Name**: `last_name`
    - **SAML Attribute Name Format**: `Basic`
  - Create a Mapper for the email address:
    - **Property**: `email`
    - **Friendly Name**: `email`
    - **SAML Attribute Name**: `email`
    - **SAML Attribute Name Format**: `Basic`
6. If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information: 
  - Your organization’s URL
  - The URL of your Keycloak realm.
  - How you would like the Zulip log in button to be labeled: “Log in with…”
  - *(optional)* An icon to use on the log in button

 **Tip:** Your Keycloak realm URL will look something like this: `https://keycloak.example.com/auth/realms/yourrealm`.

**Auth0:**

1. Make sure your Zulip Cloud organization is on the Zulip Cloud Plus plan.
2. Set up SAML authentication by following Auth0’s documentation
to create a new application. You don’t need to save the certificates or other information detailed.
All you will need is the **SAML Metadata URL**.
3. In the **Addon: SAML2 Web App Settings** tab, set the **Application Callback URL** to `https://auth.zulipchat.com/complete/saml/`.
4. Edit the **Settings** section to match:
```
{
  "audience": "https://zulipchat.com",
  "mappings": {
    "email": "email",
    "given_name": "first_name",
    "family_name": "last_name"
  },
  "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
}
```
5. If you are using Zulip Cloud, we’ll take it from here! Please email support@zulip.com with the following information: 
  - Your organization’s URL
  - The **SAML Metadata URL** value mentioned above. It contains required **Identity Provider** metadata.
  - How you would like the Zulip log in button to be labeled: “Log in with…”
  - *(optional)* An icon to use on the log in button

 **Tip:** Once SAML has been configured, consider also configuring SCIM.

## Synchronizing group membership with SAML

You can configure each Zulip user’s groups to be updated based on their groups in your Identity Provider’s (IdP’s) directory every time they log in.

Your IdP directory’s group names don’t have to match the associated Zulip group
names (e.g., membership in your IdP’s group **finance** can be synced to
membership in the Zulip group **finance-department**). See the technical
documentation on how your IdP’s groups are mapped
to Zulip groups for details.

 **Tip:** It should be possible to set this up with any provider. If you’re interested
in using this functionality with a provider other than Okta, reach out to
support@zulip.com.

**Okta:**

1. Follow the instructions above to configure SAML, and go to
the application you created for using SAML with Zulip in your
**Applications** menu.
2. Select the **General** tab, and **Edit** the **SAML Settings** section.
3. Proceed through the prompts until the main **Configure SAML** prompt.
4. Scroll down below the **Attribute Statements** section (which you configured
when creating the app) to **Group Attribute Statements**.
5. Add the following attribute:
  - **Name**: `zulip_groups`
  - **Name format**: `Unspecified`
  - **Filter**: `Matches regex: .*` When a user signs in to Zulip via SAML, Okta will now include a list of the
user’s groups in its response to the Zulip server.
6. To enable this feature, please email
support@zulip.com with the following information:
  - Your Zulip organization URL.
  - Which groups should be synced from your IdP’s directory.
  - Which groups should have a different name in Zulip (if any).