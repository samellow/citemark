# Moving from Slack

Welcome to Zulip! This page will guide you through the process of transitioning your organization to Zulip. It assumes that you have completed your initial evaluation of Zulip, decided whether to use Zulip Cloud or self-host, and are ready to introduce Zulip to your organization.

If you’re moving from other communication tools, check out the general guide on moving to Zulip.

The following steps are described in more detail below:

1. Import or create your organization.
2. Sign up for a plan.
3. Configure your organization.
4. Review and update communication policies.
5. Prepare users for the transition.
6. Invite users to join.

Each organization is unique, but we hope these common practices will help you think through the transition process in your own context.

## Import or create your organization

You can import your organization’s Slack data, including message history, users, channels, and custom emoji. Data is imported into Zulip as a new organization, so the best time to import is when your team is about to start using Zulip for day-to-day work. This may be part of your evaluation process, or after you’ve made the decision to move to Zulip.

**Import from Slack:**

1. If you plan to self-host, set up your Zulip server. You can self-host Zulip directly on Ubuntu or Debian Linux, in Docker, or with prebuilt images for Digital Ocean and Render.
2. Follow the steps in the Slack import guide.

**Create a new organization:**

1. If you plan to self-host, set up your Zulip server. You can self-host Zulip directly on Ubuntu or Debian Linux, in Docker, or with prebuilt images for Digital Ocean and Render.
2. Create a Zulip organization on Zulip Cloud or on your self-hosted server. You can create a new Zulip Cloud organization in less than two minutes. Setting up a self-hosted server will take a bit longer, but is easy to do with Zulip’s robust installer.

## Sign up for a plan

If you require features that are not available on Zulip Cloud Free or the Zulip Free plan for self-hosted organizations, you will need to upgrade your plan.

**Zulip Cloud:**

1. Follow the instructions to upgrade to a Zulip Cloud Standard or Plus plan. If your organization may be eligible for a free or discounted plan, you can apply for sponsorship.

**Self hosting:**

1. Follow the instructions to upgrade to a Zulip Basic or Zulip Business plan. If your organization may be eligible for a free or discounted plan, you can apply for sponsorship. To inquire about Zulip Enterprise, please reach out to sales@zulip.com.

## Configure your organization

1. Create your organization profile, which is displayed on your organization’s registration and login pages.
2. Create user groups, which offer a flexible way to manage permissions.
3. Review organization permissions, such as who can invite users, create channels, etc.
4. If your organization uses an issue tracker (e.g., GitHub, Salesforce, Zendesk, Jira, etc.), configure linkifiers to automatically turn issue numbers (e.g., #2468) into links.
5. Set up custom profile fields, which make it easy for users to share information, such as their pronouns, job title, or team.
6. Review default user settings, including language, default visibility for email addresses, and notification preferences.
7. Create channels if you decided not to import your Slack workspace. Zulip’s topics give each conversation its own space, so one channel per team should be enough to get you started.
8. Move your integrations using Zulip’s Slack-compatible incoming webhook. You can transition to Zulip-native integrations over time.

## Review and update communication policies

Consider updating your organization’s communication policies and practices to take advantage of Zulip’s organized conversations:

- Many organizations find that with Zulip, there’s no longer a reason to use email for internal communications. You get the organization of an email inbox together with all the features of a modern chat app, like instant delivery of messages, emoji reactions, typing notifications, @-mentions, and more.
- Because Zulip further organizes messages into conversations labeled with topics, there is generally no need to create dedicated channels for specific projects.
- With conversations organized by topic, you can review prior discussions to understand past work, explanations, and decisions — your chat history becomes a knowledge base. Should it be standard practice to link to Zulip conversations from docs, issue trackers, etc. for additional context?
- Using Zulip, you can discuss complex topics and make decisions with input from all stakeholders, without the overhead of scheduling meeting. Are there standing meetings you might not need? For example, stand-ups can be replaced with dedicated check-in topics for each team member.
- Zulip makes it easy to find conversations and follow up. To avoid disrupting focus work, @-mentions in Zulip should generally be reserved for time-sensitive messages. Silent mentions make it easy to refer to someone without calling for their attention.

## Prepare users for the transition

Prepare an introduction to Zulip for your organization. It often works well to combine a written announcement with a live presentation. Recommended topics to cover include:

1. Brief introduction to Zulip.
2. Why you’re making this change. How do you expect it to improve communication in your organization?
3. Accompanying changes to your communication policies. Are there any changes to common workflows?
4. Pointers to additional resources, such as Zulip’s getting started guide, and the guide on how threading works in Zulip for folks who are used to Slack’s threads.
5. Transition timeline.
6. How users will be supported during the transition.

## Invite users to join

If you imported your organization from Slack, decide how users will log in for the first time. Otherwise:

**Imported organizations:**

1. Configure allowed authentication methods. Zulip offers a variety of authentication methods, including email/password, Google, GitHub, GitLab, Apple, Discord, LDAP and SAML. Users can immediately log in with any allowed authentication method that does not require a password.
2. Share a link to your Zulip organization, which is
`https://your-org.zulipchat.com` on Zulip Cloud.
3. *(optional)* To log in with an email/password, users will need to set their
initial password. You can:
  - Automatically send password reset emails to all users in your organization. If you imported your organization into Zulip Cloud, simply email support@zulip.com to request this. Server administrators for self-hosted organizations should follow these instructions.
  - Let users know that they can request a password reset on your organization’s login page.

**Require invitations:**

1. Configure allowed authentication methods. Zulip offers a variety of authentication methods, including email/password, Google, GitHub, GitLab, Apple, Discord, LDAP and SAML. Users can log in with any allowed authentication method, regardless of how they signed up.
2. Invite users by sending email invitations or sharing a reusable invitation link.

**Allow anyone to join:**

1. Allow users to join without an invitation.
2. Configure the appropriate email domain restrictions for your organization.
3. Share a link to your registration page, which is https://your-org.zulipchat.com for Zulip Cloud organizations.

 **Tip:** Remember to update links and login instructions to point to Zulip.

Congratulations on making the move! If you have any questions or feedback throughout this process, please reach out to the Zulip team.