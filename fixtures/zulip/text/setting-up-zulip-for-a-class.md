# Setting up Zulip for a class

Welcome to Zulip! This page will guide you through setting everything up for teaching with Zulip. If you are using Zulip for a different purpose, we recommend checking out the moving to Zulip guide instead.

If you are a student, or if your Zulip organization is already set up, you can proceed to the Using Zulip for a class guide.

If you encounter any problems as you’re getting started, please drop by our friendly development community and let us know!

## Trying out Zulip

You can start by reading about Zulip for Education, and how Zulip can become the communication hub for your class. Zulip is the only modern team chat app that is ideal for both live and asynchronous conversations. Post lecture notes and announcements, answer students’ questions, and coordinate with teaching staff all in one place.

We also highly recommend trying Zulip for yourself! You can:

- Create a Zulip Cloud organization for free with just a few clicks.
- Join the Zulip development community to see Zulip in action. Feel free to introduce yourself and ask questions!

## Choosing between Zulip Cloud and self-hosting

Follow the guide on choosing between Zulip Cloud and self-hosting to pick the best option for you. If your needs change, you can always move to a self-hosted installation or to Zulip Cloud.

Anyone can start with Zulip Cloud Free, which works well for a typical class. For large classes and departments, we offer special Zulip for Education pricing, with the same features as Zulip Cloud Standard. You can always get started with Zulip Cloud Free, and upgrade down the line if needed.

## Do I need a separate Zulip organization for each class?

There are a few ways to set up Zulip, and different ones may be convenient for your needs:

- If your **school or department already has a Zulip organization**,
you will probably find it easiest to just add your class to
it. Advantages:
  - Students and staff can use a single Zulip account for all classes.
  - You can create department-wide channels, e.g., for announcing talks or other events.
  - You don’t need to set up a separate server if you’re self-hosting Zulip.
- You can **set up a separate Zulip organization for each class** you’re teaching. Advantages:
  - This makes it simple to manage permissions, e.g., if you want to make sure TAs from one class cannot moderate discussion from a different class.
  - Students can’t see who is in channels for other classes.
  - You can easily switch between multiple Zulip organizations in the Zulip desktop apps.
- You can **use a single Zulip organization for several classes** you’re teaching, perhaps re-purposing a Zulip organization from a
prior term. Advantages:
  - Information from your classes is all in one place, e.g., if you want to re-post a response to a question that was also asked last time you taught the class.

If you change your mind down the line, you can rename your Zulip organization by sending a request to support@zulip.com.

## Create your organization profile

The information in your organization profile is displayed on the registration and login page for your organization, and in the Zulip app.

### Edit organization profile

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization profile**.
4. Edit your organization **name**, **type**, **description**, and **profile picture**.
5. *(optional)* Click **Preview organization profile** to see a preview of your
organization’s login page in a new browser tab.
6. Click **Save changes**.

### Add a wide logo

**Note:**

Zulip Cloud customers who wish to use this feature must upgrade to Zulip Cloud Standard or Zulip Cloud Plus.

You can customize the logo users see in the top left corner of the Zulip app. For best results:

- The logo should be a wide rectangle image with an up to 8:1 width to height ratio. It will be displayed at up to 200×25 pixels, or more on high-resolution displays.
- Make sure your logo has a transparent background, and trim any bordering whitespace.

To upload a logo:

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Organization profile**.
4. Under **Organization logo**, click the image under **Light theme logo** or **Dark theme logo**, and choose a replacement image to upload.
5. Crop the image as desired, and click **Save changes**.

Make sure to test the logo in both light theme and dark theme.

## Customize organization settings

Review the settings for your organization to set everything up how you want it to be.

User groups offer a flexible way to manage permissions in your organization. Most permissions in Zulip can be granted to any combination of roles, groups, and individual users.

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select **Organization settings**.
3. Click on the **Organization settings** and **Organization
permissions** tabs, as well as any others that are of interest.

A few settings to highlight:

- If your class uses a programming language, set the default language for code blocks. Also consider setting up code playgrounds.
- If your class uses code repositories, set up linkifiers to make it easy to link to issues (e.g., just by typing #1234 for issue 1234).
- Add custom emoji that your class will enjoy.

### Roles and permissions

Zulip offers several levels of permissions based on user roles. Here are some recommendations for how to assign roles and permissions for a class.

#### Recommended roles and permissions for a single-class Zulip organization

| Who | Role | 
|---|---|
| Lead instructor, IT | Owner (also has all Administrator permissions) | 
| Other instructors, head TA | Administrator | 
| Teaching assistants, lab assistants | Moderator | 
| Students | Member | 

##### Settings

**Note:**

These are the default permissions for new **Education
(non-profit)** and **Education (for-profit)** organizations.

- Set who can invite new users. (Recommended: Admins)
- Set who can access user email addresses. (Recommended: Admins only)
- Set who can create channels. (Recommended: Admins for public channels; Admins, moderators and members for private channels)
- Set who can subscribe other users to channels. (Recommended: Admins and moderators)
- Set who can edit the topic of any message. (Recommended: (default) Members for small classes; Admins and moderators for large classes)
- Set who can move messages between channels. (Recommended: Admins and moderators)
- Set who can create and manage user groups. (Recommended: Admins and moderators)

#### Recommended roles and permissions for a department

| Who | Role | 
|---|---|
| IT | Owner (also has all Administrator permissions) | 
| IT, department leadership | Administrator | 
| Professors, Lecturers, head TAs | Moderator | 
| Teaching assistants, lab assistants, students | Member | 

##### Settings

- Set who can invite new users. (Recommended: Admins and moderators)
- Set who can access user email addresses. (Recommended: Admins only)
- Set who can create channels. (Recommended: Admins and moderators for public channels; Admins, moderators and members for private channels)
- Set who can subscribe other users to channels. (Recommended: Admins and moderators)
- Set who can edit the topic of any message. (Recommended: Admins and moderators)
- Set who can move messages between channels. (Recommended: Admins and moderators)
- Set who can create and manage user groups. (Recommended: Admins and moderators)

## Create channels

Channels organize conversations based on who needs to see them. For example, it’s common to have a channel for each team in an organization. Because Zulip further organizes messages into conversations labeled with topics, there is generally no need to create dedicated channels for specific projects.

We recommend setting up some channels before inviting other users to join Zulip, so that you can automatically subscribe everyone to the right set of channels.

If you later create additional channels, no worries! You can always subscribe a group of users, or all the subscribers of another channel, to a new channel.

 **Tip:** Add clear descriptions to your channels, especially public channels.

### How to create a channel

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Channel settings**.
3. Click **All** in the upper left.
4. Click **Create channel** on the right.
5. Fill out the requested info, and click **Create**.

### Tips for creating channels

For most classes, the following channels are recommended:

- **#announcements**: For general announcements about the class. When
creating this channel, restrict posting
permissions so that only course staff
(administrators and moderators) are
allowed to post.
- **#staff (private)**: For discussions among course staff.
- **#general**: For random topics, e.g., students forming study groups.
- A channel for each **lecture** or **unit**, e.g., “Lecture 1: Course
intro” or “Unit 3: Sorting algorithms”.
- A channel for each **section**/**tutorial group** (e.g., “Section 1”)

 **Tip:** You can start by creating channels for just the first few
lectures/units at this point. When you create a new channel,
you will be able to copy channel membership from existing channels.

A few notes:

- Small classes may need just one discussion channel for all lectures.
- If you are using a single Zulip organization for more than one class, all channel names should be prefixed with the name of the class, e.g., “CS101 > Lecture 1: Course intro”.

## Customize settings for new users

Customize settings for new users to get them off to a great start.

- Add custom profile fields, such as pronouns or job title.
- Configure default new user settings.
- Set default channels for new users.
- Set organization language for automated messages and invitation emails, if it should be something other than American English.

 **Tip:** If using your Zulip organization for a single class, set default
channels for new users to include **#announcements**, **#general**,
and all lecture/unit channels.

## Invite users to join

 **Tip:** Before inviting users, you may want to delete any test
messages or topics.

### How to invite users to join

To simplify subscription management, be sure to set the channels students and staff should be subscribed to when you create the invitations. You may choose to send invitations to course staff separately, so that they can immediately be subscribed to private channels for your class.

**Require invitations:**

1. Configure allowed authentication methods. Zulip offers a variety of authentication methods, including email/password, Google, GitHub, GitLab, Apple, Discord, LDAP and SAML. Users can log in with any allowed authentication method, regardless of how they signed up.
2. Invite users by sending email invitations or sharing a reusable invitation link.

**Allow anyone to join:**

1. Allow users to join without an invitation.
2. Configure the appropriate email domain restrictions for your organization.
3. Share a link to your registration page, which is https://your-org.zulipchat.com for Zulip Cloud organizations.

To get everyone off to a good start, you may wish to share the guide to Getting started with Zulip and the guide to Using Zulip for a class.

 **Tip:** If you create new channels later on, you can subscribe users
by group or copy membership from another
channel (e.g., from Lecture 5 to Lecture 6).

## Create user groups

User groups allow you to mention multiple users at once, notifying them about a message. For example, you may find it useful to set up the following user groups:

- @staff
- @TAs
- @graders
- @students
- @section1, @section2, etc.

### How to create a user group

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select **Group settings**.
3. Click **Create user group** on the right, or click the **create new user group** ()
icon in the upper right.
4. Fill out the requested information, and click **Continue to add
members**.
5. Under **Add members**, enter groups and users you want to add. You can enter
a `#channel` to add all subscribers to the group. Click **Add**.
6. Click **Create** to create the group.

**Note**: You will only see the **Create user group** button if you have
permission to create user groups.

## Set up integrations

Zulip integrates directly with dozens of products, and with hundreds more through Zapier and IFTTT. Popular Zulip integrations include GitHub and GitLab. The integrations page has instructions for integrating with each product.

## Cleaning up at the end of a class

If you plan to use the same Zulip organization in future terms (either for your own classes or for your department), you will likely want to:

- Rename all channels to indicate the class and term in which they were used, for
example:
  - **#announcements** → **#FA21 - CS101 - announcements**
  - **#CS101 > Lecture 1: Course intro** → **#FA21 - CS101 > Lecture 1: Course
intro**
- If you do *not* want students from future classes to see messages
from the prior term (e.g., because you posted homework solutions),
make all the channels from the class private. You’ll
be able to find and reuse content yourself, and invite course
staff to these private channels as needed.
- You may choose to deactivate students’ Zulip accounts when the class is over.
- Unpin channels from the class from your personal view.

If you do not plan to reuse the Zulip organization, you can instead:

- Export the organization or generate a static HTML archive to archive the information.
- Deactivate the organization.

## Further reading

- Using Zulip for a class
- Getting started with Zulip
- Introduction to topics
- Moderating open organizations