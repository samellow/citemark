# Review notes: zulip v1 (2026-10-07)

## Outcome (2026-10-08)

Every item below was decided, and all 50 questions were read and approved or edited.

- **The result:** `citemark test check` passes, with 18 of 50 questions changed from the draft. In total there are now 232 bullets (224 before) and 82 sources (77 before).
- **Where a bullet said more than the help center:** it was replaced with the help center's own sentences (Q003, Q008, Q009, Q011, Q030, Q032), had an unsupported word swapped (Q033, Q035), or was deleted (Q027). Q010 now gives the 15-subscriber size.
- **Bullets added from the left-out caveats:**
  - Q008: two (the deletion time limit; a file shared in several messages)
  - Q013, Q024 and Q028: one each
  - Q015 and Q031: two each
  - Q032: one (how to invite a guest)
  - New accepted sources were added where a bullet came from another article.
- **Recorded in notes instead:** Q007, Q014, Q016, Q025 and Q029.
- **Notes corrected:** Q032, Q037, Q038, Q039 and Q046.
- **Types and options:** Q035 stays a partial. "desktop" was removed from Q039's options and "a channel" from Q040's.
- **In pass 2,** Q001 lost its permission bullet, which repeated the admin caveat.
- **One correction to the audit:** the help center does mention a "status menu" (Q033's keyboard tip).

These are for your review pass (plan P0.7). Edit `zulip-v1.yaml`, not the draft. Then run:

    uv run citemark test check test-sets/zulip-v1.yaml --snapshot fixtures/zulip \
      --expect answerable=32,partial=5,ambiguous=3,decline=7,off_topic=3 --max-per-article 3 \
      --draft test-sets/zulip-v1.draft.yaml

## Where it stands

- **The mechanical checks pass,** against the corrected snapshot:
  - all 50 questions, in the composition the brief asked for
  - at most 3 questions per article
  - every quote found word for word in its section
  - every decline term with zero hits
- **The wording check** flagged none of the draft's questions.
- **The 11 fixed questions** carry `locked: true`, because the demo page shows their wording. That's the only difference from the draft.
- **A key-fact audit** compared all 224 key facts with the snapshot, using a fresh agent that saw only this file and the help center:
  - 215 are supported
  - 9 are partly supported
  - none are made up
- **The snapshot was corrected** after the audit. The drafting session saw a copy that was missing 125 paragraphs and list items, on 68 pages (plan G9, widened). The fix restored the "Select **Billing**" step behind Q030 and the call-provider list behind Q042's notes.

Each row below is something to decide; none is a required change. "Judgment call" means the audit wasn't sure it's a problem.

## Key facts that say more than the help center

| Q | The fact | What the help center says |
|---|---|---|
| Q003 | muted channels are "collapsed at the bottom of their folder" | mute-a-channel: they appear in a **collapsible** section at the bottom of their folder, in the desktop/web app |
| Q008 | deleted messages are "archived for 30 days first" | delete-a-message: 30 days, but server admins can change it (`ARCHIVED_DATA_VACUUMING_DELAY_DAYS`). Judgment call. |
| Q009 | "`:` opens the picker for any reaction" | emoji-reactions: "Use `:` to add any reaction". It never says that opens the picker. Judgment call. |
| Q011 | Free plan: 5 GB "in total for the organization" | share-and-upload-files: "a total of 5 GB of file storage". It never says "for the organization". Judgment call. |
| Q027 | "Owners can revoke or resend invitations" | invite-new-users: administrators can too, except invitations to the owner role |
| Q030 | "Gear icon, then at the bottom of the billing page click Cancel plan" | zulip-cloud-billing (corrected snapshot): gear icon, **Select Billing**, then Cancel plan at the bottom of the page, then Downgrade |
| Q032 | hiding other users from guests "requires the Zulip Cloud Plus plan" | guest-users: "**Zulip Cloud customers** who wish to use this feature must upgrade". The notes repeat the overstatement ("a Plus-only feature"). |
| Q033 | "open the status menu and click the x" | status-and-availability: open your user card or click your profile picture, then click the icon to the right of your status. The help center never names the icon or a "status menu". |
| Q035 | "click the play control" | desktop-notifications: "click the [icon] to the right of your selection". The icon has no name in the page. Judgment call. |

## Notes that are wrong or incomplete

| Q | The note | What the help center says |
|---|---|---|
| Q037 | the org-level DM setting is "not a per-person block" | restrict-direct-messages: it can name individual users, so an admin can stop one person starting DMs. That's with anyone, not just with you. Judgment call. |
| Q039 | notifications for one topic are in topic-notifications | That article covers topics you follow; silencing one topic is mute-a-topic |
| Q046 | uploaded sound files are "playable" | share-and-upload-files says they're "previewed"; "play" is only said of videos |
| Q038 | the list of other meanings of "reset it" | It also leaves out the API key (logging-out), plus font size and line spacing ("reset to the default"). No listed meaning is wrong. Judgment call. |

## Things the help center says that the expected answer leaves out

The strongest are first.

| Q | Left out | Where |
|---|---|---|
| Q015 | An import can only create a new organization, and settings, edit history and passwords don't come across | import-from-slack |
| Q028 | Only organization or channel administrators can archive | configure-who-can-administer-a-channel |
| Q031 | Retention policies only exist on paid Cloud plans. A third cause is private channels with protected history (judgment call). | message-retention-policy, channel-permissions |
| Q025 | Admins can turn the call buttons off (call provider "None") | configure-call-provider |
| Q013 | Muted users are left out of read receipts too | mute-a-user |
| Q007 | Read receipts can still show activity while you're invisible | status-and-availability |
| Q024 | The organization can allow move history only, hiding content edits | restrict-message-edit-history-access |
| Q008 | Deletion can have a time limit, and a file shared in several messages survives until all of them are deleted | delete-a-message |
| Q016 | A draft is only saved after at least 3 characters (judgment call) | view-and-edit-your-message-drafts |
| Q032 | How to add a guest: the role is set at invite, and default channels are preselected, which matters for "just one channel" (judgment call) | invite-new-users |
| Q014 | Web-app users get no alternative to Do Not Disturb (judgment call) | desktop-notifications |
| Q029 | Topic editing has its own time limit (minor) | restrict-moving-messages |
| Q010 | The wildcard restriction starts above 15 subscribers (minor) | restrict-wildcard-mentions |

## Type and grading

- **Q035 (partial):** the question has one part, the phone's alert sound, and the help center answers none of it. A decline with a near-miss may fit better. Judgment call.
- **Q039 `expected_option`:** the test runner picks the bot's clarifying option that matches one of these phrases (plan 5.3). "desktop" also matches "Do Not Disturb in the desktop app", one of the other meanings in the notes, so the runner could follow up with the wrong option.
- **Q040 `expected_option`:** "a channel" is loose, though no other listed meaning contains it.

## What wasn't a problem

- **Uncovered parts** (Q033, Q034, Q036, Q037): searched under other wordings, and none is covered.
- **Decline questions** (Q041–Q047): searched beyond their terms, and none is answered.
- **Icons:** they have no name in the page HTML itself, so a quote like Q006's "a filled in star () to their right" is what the help center's text really says.
