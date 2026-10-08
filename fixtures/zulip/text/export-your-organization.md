# Export your organization

**Note:**

If you’re self-hosting Zulip, you may want to check out the documentation on server export and import or server backups. You can also generate a static HTML archive of select channels.

Zulip has high quality export tools that can be used to migrate between the hosted Zulip Cloud service and your own servers. Zulip offers the following options for exporting data in an importable format:

- **Public data
only**:
Complete data for your organization *other than* private
channel messages and direct
messages. This export includes user settings and
channel subscriptions.
- **Public and private data (with
consent)**:
Everything in the export of public data, plus all the private
channel messages and direct
messages that members who have
allowed
administrators to export their private data can access.
- **All public and private data**.
This option is only available to **corporate** Zulip Cloud Standard
and Zulip Cloud Plus customers.

In addition, Zulip Cloud Standard and Zulip Cloud Plus customers can request a compliance export:

- **Compliance export**: A targeted, human-readable export
of messages matching some combination of criteria (e.g., sender, recipient,
message keyword, or timestamp).

## Export data in an importable format

**Note:**

This feature is only available to organization owners and administrators.

This export is formatted for importing into Zulip Cloud or a self-hosted installation of Zulip. It is not designed to be human-readable.

**Desktop/Web:**

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Organization settings**.
3. On the left, click **Data exports**.
4. Click **Start export**.
5. Select the desired **Export type**.
6. Click **Start export** to begin the export process. After a few minutes,
you’ll be able to download the exported data from the list of
data exports.
7. Use Zulip’s logical data import tool to import your data into a self-hosted server. For Zulip Cloud imports, contact support@zulip.com.

**Note:**

Generating the export can take up to an hour for organizations with a large number of messages or uploaded files.

### Export of all public and private data

**Note:**

This feature is only available to organization owners.

To perform this export, your organization must meet the following requirements:

- You are a paid Zulip Cloud Standard or Zulip Cloud Plus customer. In rare cases, exceptions may be made in case of due legal process.
- You have authority to read members’ direct messages. Typically, this will be because your Zulip organization is administered by a corporation, and you are an official representative of that corporation.

By requesting and executing this export, you will assume full legal responsibility that the appropriate employment agreements and corporate policy for this type of export are in place. Note that many countries have laws that require employers to notify employees of their use of such an export.

Contact support@zulip.com to request access to this export type, then follow the export instructions above.

If you self-host Zulip, an export of all public and private data can be performed by your server’s administrator.

## Compliance export

**Note:**

This feature is only available to organization owners.

This type of export is recommended if you plan to work with the exported data directly (e.g., reading messages or processing them with a script), rather than importing the export into a new Zulip organization.

To perform this export, your organization must meet the following requirements:

- You are a paid Zulip Cloud Standard or Zulip Cloud Plus customer. In rare cases, exceptions may be made in case of due legal process.
- You have authority to read members’ direct messages. Typically, this will be because your Zulip organization is administered by a corporation, and you are an official representative of that corporation.

By requesting and executing this export, you will assume full legal responsibility that the appropriate employment agreements and corporate policy for this type of export are in place. Note that many countries have laws that require employers to notify employees of their use of such an export.

1. Email support@zulip.com asking for a **compliance
export**. Please send the email from the same address that you use to sign in
to Zulip, so that Zulip Support can verify that you are an owner of the
organization. You will need to specify:
  1. The `zulipchat.com` URL for your organization
  2. What limits you would like on the export.  Currently, compliance
exports can apply any combination of the following filters:
    - Message sender
    - Message recipient
    - Message contents, by specific keywords
    - Sent timestamp before, after, or between dates If you need other limits, please ask.
  3. Your preferred format for the export: CSV or JSON.
  4. Whether or not you want to receive copies of all attachments referenced in the exported messages.
2. You will receive the requested information once your authority to request the export has been verified.

If you self-host Zulip, a compliance export can be performed by your server’s administrator.

## Configure whether administrators can export your private data

1. Click on the **gear** () icon in the upper right corner of the web or desktop app.
2. Select  **Personal settings**.
3. On the left, click **Account & privacy**.
4. Under **Privacy**, toggle **Let administrators export my private data**.