# Self-hosted Zulip billing

This page describes how to manage your self-hosted plan, and answers some common questions about plans and billing for self-hosted organizations. Please refer to Self-hosted Zulip plans and pricing for plan details.

The topics covered include:

- Self-hosted plans overview
- Logging in to manage billing
- Upgrading to a paid plan
- Managing billing
- Canceling a paid plan
- Applying for a free Community plan
- Applying for a paid plan discount
- Payment methods
- License management options

If you have any questions not answered here, please don’t hesitate to reach out at sales@zulip.com.

## Self-hosted plans overview

Organizations that self-host Zulip can take advantage of the following plan options:

- **Free**: Includes free access to Zulip’s Mobile Push Notification
Service for up to 10 users.
- **Basic**: Includes unlimited access to Zulip’s Mobile Push Notification
Service for organizations with more than 10 users.
- **Business**: Includes commercial support, in addition to push notifications
access. Zulip’s support team can answer questions about installation and
upgrades, provide guidance in tricky situations, and help avoid painful
complications before they happen. You can also get guidance on how best to use
dozens of Zulip features and configuration options.
- **Enterprise**: If your organization requires hands-on support, such as
real-time assistance during installation and upgrades, help with advanced
deployment options, development of custom features or integrations, etc.,
please contact sales@zulip.com to discuss pricing.
- **Community**: This free plan includes unlimited push notifications access,
and is available for many non-commercial organizations with more than 10 users
(details below).

For full plan details, please take a look at self-hosted Zulip plans and pricing.

There is no option to combine multiple plans (e.g., Free and Basic) within a single organization. Pricing is based on the number of non-deactivated users, not on which features each user is taking advantage of. However, paid plan discounts are available in a variety of situations; see below for details.

### Organization plan or server plan?

You can purchase self-hosted plans for a Zulip organization, or for your entire server.

If your server hosts a single Zulip organization, follow the instructions for organization-level billing (available on Zulip Server 8.0+). This will provide a more convenient plan management experience.

If your server hosts multiple organizations, you can manage plans individually for each organization, or purchase a single plan to cover your entire server. Commercial support for any server-wide configurations requires upgrading the organization with the largest number of users.

## Log in to billing management

Once you are logged in, you can upgrade to a paid plan, manage billing, cancel a paid plan, or apply for a free Community plan or a paid plan discount.

**Organization-level billing:**

**Note:**

This feature is only available to users who can manage plans and billing.

1. *(first-time log in)* Your Zulip server administrator should register
the server with Zulip’s Mobile Push Notification Service, following
these instructions.
The Zulip Server 10.0+ installer includes a `--push-notifications` flag that automates this registration process.
2. Click on the **gear** () icon in the upper right corner
of the web or desktop app.
3. Select  **Plan management**.
4. *(first-time log in)* Enter the email address you want to use for
plan management, and click **Continue**.
5. *(first-time log in)* In your email account, open the email you
received (Subject: Confirm email for Zulip plan management), and
click **Confirm and log in**.
6. *(first-time log in)* Enter your name, configure your email preferences,
and accept the Terms of Service.
7. Verify your information, and click **Continue**.

**Server-level billing:**

 **Tip:** A **server administrator** is anyone who sets up and manages your Zulip
installation. A **billing administrator** is anyone responsible for
managing your Zulip plan.

**Server administrator steps:**

1. *(first-time log in)* Register the server with Zulip’s Mobile Push
Notification Service, following these
instructions.
The Zulip Server 10.0+ installer includes a `--push-notifications` flag that automates this registration process.
2. Go to https://selfhosting.zulip.com/serverlogin/.
3. Fill out the requested server information, and click **Continue**.
4. Enter the email address of the billing contact for your organization,
and click **Confirm email**.

**Billing administrator steps:**

1. In your email account, open the email you received
(Subject: Log in to Zulip plan management), and click **Log in**.
2. *(first-time log in)* Enter your name, configure your email preferences,
and accept the Terms of Service.
3. Verify your information, and click **Continue**.

## Upgrade to a paid plan

### Start a free trial

**New customers** are eligible for a free 30-day trial of the **Basic** plan.
An organization is considered to be a new customer if:

- It was not registered for Zulip’s Mobile Push Notification Service prior to December 12, 2023, and
- It has never previously signed up for a self-hosted Zulip plan (Basic, Business, Community or Enterprise).

**Pay by credit card:**

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, click the **Start
30-day trial** button at the bottom of the **Basic** plan.
3. Click **Add card** to enter your payment details.
4. *(optional)* Update the billing details included on receipts so that
they are different from the information entered for the payment method,
e.g., in case you would prefer that the company’s name be on receipts
instead of the card holder’s name.
5. Click **Start 30-day trial** to start your free trial.

 **Tip:** Once you start the trial, you can switch between monthly and annual
billing on your organization’s billing page. You can
cancel any time during your trial to avoid any charges.

**Pay by invoice:**

**Note:**

Only manual license management is available when paying by invoice. If you are using a non-US bank, please see details on making sure your payment covers the full amount of the invoice.

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, click the **Start
30-day trial** button at the bottom of the **Basic** plan.
3. Select **pay by invoice**.
4. Select your preferred option from the **Payment schedule** dropdown.
5. Select the **Number of licenses** you would like to purchase for your
organization. You can adjust this number to update your initial invoice any
time during your trial.
6. Click **Update billing information** to enter your billing details, which
will be included on invoices and receipts.
7. Click **Start 30-day trial** to start your free trial.

### Upgrade directly to a paid plan

**Pay by credit card:**

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, click the button at the bottom of the plan you would like to purchase.
3. Select your preferred option from the **Payment schedule** dropdown.
4. Click **Add card** to enter your payment details.
5. *(optional)* **View and update** billing information included on
receipts so that they are different from the information entered for
the payment method, e.g., in case you would prefer that the company’s
name be on receipts instead of the card holder’s name.
6. Click the **Purchase** button to complete your purchase.

**Pay by invoice:**

**Note:**

Only manual license management is available when paying by invoice. If you are using a non-US bank, please see details on making sure your payment covers the full amount of the invoice.

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, click the button at the bottom of the plan you would like to purchase.
3. Select **pay by invoice**.
4. Select your preferred option from the **Payment schedule** dropdown.
5. Select the **Number of licenses** you would like to purchase for your
organization; see details about manual license
management.
6. Click **Update billing information** to enter your billing details,
which will be included on invoices and receipts.
7. Click the **Send invoice** button, and an email with an initial
invoice will be sent to the email address you used to sign in.
8. Your plan will be upgraded when the initial invoice is paid.

 **Tip:** Until the initial invoice is paid, logging in to manage your billing
will show a page with a link to the outstanding invoice. You’ll be able
to manage your plan once your first invoice is paid.

## Manage billing

On the billing page for an active paid plan you can:

- View your past invoices.
- View and update the billing details displayed on invoices and receipts for future payments.
- If you pay for your plan by credit card, update your card’s payment details.
- Change your billing frequency to be monthly or annual.
- If you opted for manual license management, you can update the number of licenses for the current billing period or the next billing period.

### Manage billing

1. Log in to billing management.

### Configure who can manage plans and billing

**Note:**

For a self-hosted Zulip server running a version older than Zulip 10.0+, follow the instructions for older versions here.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization permissions**.
4. Under **Other permissions**, configure **Who can manage plans and billing**.
5. Click **Save changes**.

## Cancel paid plan

If you cancel your plan, your organization will be downgraded to the
**Free** plan at the end of the current billing period.

1. Log in to billing management.
2. At the bottom of the page, click **Cancel plan**.
3. Click **Downgrade** to confirm.

## Free Community plan

Zulip sponsors free plans for over 1000 worthy organizations. The following
types of organizations are generally eligible for the **Community** plan.

- Open-source projects, including projects with a small paid team.
- Research in an academic setting, such as research groups, cross-institutional collaborations, etc.
- Organizations operated by individual educators, such as a professor teaching one or more classes.
- Non-profits with no paid staff.
- Communities and personal organizations (clubs, groups of friends, volunteer groups, etc.).

Organizations that have up to 10 users, or do not require mobile push
notifications, will likely find the **Free** plan to be the most convenient
option. Larger organizations are encouraged to apply for the **Community**
plan, which includes unlimited push notifications and support for many Zulip
features.

If you aren’t sure whether your organization qualifies, submitting a sponsorship
form describing your situation is a great starting point. Many organizations
that don’t qualify for the **Community** plan can still receive discounted paid
plan pricing.

### Apply for Community plan

These instructions describe the **Community** plan application process for an
existing Zulip server. If you would like to inquire about eligibility prior to
setting up a self-hosted server, contact sales@zulip.com.

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, scroll down to the
**Sponsorship and discounts** area, and click **Apply here**.
3. Fill out the requested information, and click **Submit**. Your application
will be reviewed for **Community** plan eligibility.

 **Tip:** Organizations that do not qualify for a **Community** plan may be offered a
discount for the **Basic** plan.

## Paid plan discounts

The following types of organizations are generally eligible for significant discounts on paid plans. You can also contact sales@zulip.com to discuss bulk discount pricing for a large organization.

- Education organizations and non-profit organizations.
- Discounts are available for organizations based in the **developing world**.
- Any organization where many users are **not paid staff** is likely eligible
for a discount.

If there are any circumstances that make regular pricing unaffordable for your organization, contact sales@zulip.com to discuss your situation.

### Education pricing

Organizations operated by individual educators (for example, a professor teaching one or more classes) are generally eligible for the Community plan.

Departments and other institutions using Zulip with students are eligible for discounted education pricing. Other educational uses (e.g., by teaching staff or university IT) may qualify for non-profit pricing.

- **For-profit education pricing**:
  - **Basic plan**: $0.50 per user per month
  - **Business plan**: $1 per user per month with annual billing
($1.20/month billed monthly) with a minimum purchase of 100 licenses.
- **Non-profit education pricing**: The non-profit discount applies to
online purchases only (no additional legal agreements) for use at registered
non-profit institutions (e.g., colleges and universities).
  - **Basic plan**: $0.35 per user per month
  - **Business plan**: $0.67 per user per month with annual billing
($0.80/month billed monthly) with a minimum purchase of 100 licenses.

### Non-profit pricing

Non-profits with no paid staff are eligible for the Community plan.

For non-profits with paid staff, volunteers and other unpaid participants in your community are eligible for free Zulip accounts. Additionally, discounts are available for paid staff accounts. Contact sales@zulip.com to arrange discounted pricing for your organization.

### Guest user discounts

There is no automatic discount for guest users. However, organizations with a large number of guest users are very likely to be eligible for a discount. If this is your situation, please apply for a discount or email sales@zulip.com.

### Duplicate accounts

Some servers host multiple organizations, with some individuals having accounts in several of these organizations. If you have this setup, the ability to configure whether guests can see other users (introduced in Zulip 8.0) may allow you to consolidate into a single Zulip organization.

If you want to maintain a multi-organization setup with duplicate accounts, you may contact sales@zulip.com to arrange a discounted rate.

### Apply for a paid plan discount

These instructions describe the paid plan discount application process for an existing Zulip server. If you would like to inquire about paid plan discount eligibility prior to setting up a self-hosted server, contact sales@zulip.com.

1. Log in to billing management.
2. On the page listing Zulip’s self-hosted plans, scroll down to the
**Sponsorship and discounts** area, and click **Apply here**.
3. Select your preferred option from the **Plan** dropdown.
4. Fill out the requested information, and click **Submit**. Your application
will be reviewed for discount eligibility.

## Payment methods

### What are my payment options?

You can pay by credit card or by invoice. If you choose to pay by invoice, your organization will be upgraded to the plan you selected once the initial invoice is paid.

Note that automatic license management is only available if you pay by credit card. Paying by invoice requires manual license management.

### International SWIFT transfers

If you choose to pay via a bank transfer from a bank outside of the United
States, your payment will likely incur a transfer charge. When asked which side
will pay the transfer charge, please be sure to **select “OUR”** from the menu
of options. Otherwise, third party banking fees will be deducted from the amount
you transfer, and the resulting total will be insufficient to pay the full
amount of your invoice.

## License management options

### How does automatic license management work?

 **Tip:** Automatic license management is recommended unless you have a
specific reason to choose manual license management.

With automatic license management, you automatically purchase a Zulip license for each user in your organization at the start of each billing period (month or year), and whenever you need additional licenses.

- Deactivating a user frees up their license for reuse. No refunds are given for unused licenses you have purchased for the current billing period. For example if you start an annual billing period with 10 users, and deactivate 4 users halfway through the year, then you will receive no refund, even if those licenses are not used in the remaining 6 months of the year.
- If you have no free licenses when a new user joins or an existing user is reactivated, you will be automatically billed for an additional license. You will be charged only for the remaining part of the billing period. For example, if you are on a $8/user/month monthly plan, you will be billed $4 for a user added halfway through the month.
- If you have an annual billing period, each month, you will see a single charge for all licenses added the previous month. If you have a monthly billing period, the charge for licenses added during the previous month will be combined with your monthly renewal charge.

### How does manual license management work?

With manual license management, you choose and pay for a fixed number of licenses for your organization or server. Deactivating a user frees up their license for reuse.

If the number of active users exceeds the number of licenses you’ve purchased, any paid services included in your plan will be paused until this is addressed. For example, you will lose access to the Mobile Push Notification Service until you have purchased more licenses or deactivated enough users.

#### Manually update number of licenses

1. Log in to billing management.
2. Modify **Number of licenses for current billing period** or **Number of
licenses for next billing period**, and click **Update**.

 **Tip:** Modifying the number of licenses for the current billing period also
automatically updates the number of licenses for the next
billing period.

## How paid plans support the Zulip project

Zulip is proudly independent, with no venture capital funding, which means that revenue strongly impacts the pace of Zulip’s development. Paid plans for self-hosted customers help fund improvements in Zulip’s self-hosting experience, and overall product development. Zulip needs the support of businesses that self-host Zulip in order to thrive as an independent, 100% open-source project.

You can also learn about other ways to support the Zulip project.

## Self-hosting Zulip for free

Zulip is 100% open-source. Organizations that do not require support with their installation can always use Zulip for free with no limitations. Additionally, the Mobile Push Notification Service is provided free of charge for organizations with up to 10 users.

You can self-manage your Zulip installation without signing up for a plan. Get started with the installation guide.