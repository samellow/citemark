# Restrict account creation

**Note:**

This feature is only available to organization owners.

Each Zulip account is associated with an email address. If your organization allows multiple authentication methods, it doesn’t matter which one is used to create an account. All authentication methods will work for all users in your organization, provided that they are associated with the account email. To log in with email, users are required to verify their email account by clicking on a validation link.

Zulip provides a number of configuration options to control who can create a new account and how users access their accounts:

- You can require an invitation to sign up (default), or you can allow anyone to join without an invitation.
- You can restrict the ability to invite new users to any combination of roles, groups, and individual users.

Regardless of whether invitations are required, you can:

- Configure allowed authentication methods.
- Restrict sign-ups to a fixed list of allowed domains (including subdomains). For example, you can require users to sign up with the email domain for your business or university.
- Disallow signups with known disposable email address. This is recommended for open organizations to help protect against abuse.

## Set whether invitations are required to join

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Joining the organization**, toggle **Invitations are required for
joining this organization**.
5. Click **Save changes**.

## Change who can send invitations

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Joining the organization**, configure **Who can send email invitations to new users** and **Who can create reusable invitation links**.
5. Click **Save changes**.

## Configuring email domain restrictions

Email domain restrictions apply to both new user accounts and email changes.

### Restrict sign-ups to a list of domains

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Set **Restrict email domains of new users** to **Restrict to a list of domains**.
5. Click **Configure** to add any number of domains. For each domain, you can
toggle **Allow subdomains**.
6. When you are done adding domains, click **Close**.
7. Click **Save changes**.

### Don’t allow disposable domains

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Set **Restrict email domains of new users** to **Don’t allow disposable emails**.
5. Click **Save changes**.

### Allow all email domains

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Set **Restrict email domains of new users** to **No restrictions**.
5. Click **Save changes**.