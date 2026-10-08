# Message formatting

Zulip uses Markdown to allow you to easily format your messages. Even if you’ve
never heard of Markdown, you are probably familiar with basic Markdown
formatting, such as using `*` at the start of a line in a bulleted list, or
around text to indicate emphasis.

Formatting buttons in the compose box make it easy to format your message. For those who prefer to type the formatting they need, this page provides an overview of all the formatting available in Zulip. There is a convenient message formatting reference in the Zulip app that you can use whenever you need a reminder of the formatting syntax below.

- Text emphasis
- Bulleted lists
- Numbered lists
- Indenting list items
- Links
- Code blocks
- LaTeX
- Quotes
- Spoilers
- Emoji and emoticons
- Mention a user or group
- /me action messages
- Global times
- Tables
- Polls
- Collaborative to-do lists
- Paragraph and section formatting

## Text emphasis

In Zulip, you can make text bold or italic, or cross it out with strikethrough.

### What you type

```
**bold**, *italic*, and ~~strikethrough~~ text
***~~All three at once~~***
```
### What it looks like

 **Tip:** You can also use buttons or keyboard shortcuts (`Ctrl` +
`B` or `Ctrl` + `I`) to make text bold or italic.
Learn more.

## Bulleted lists

Zulip supports Markdown formatting for bulleted lists.
You can create bulleted lists using `*`, `-`, or `+` at the start of each line.
Add two spaces before the bullet to create a nested list.

### What you type

```
* bulleted lists
  * with sub-bullets too
  * sub-bullets start with 2 spaces
    * start sub-sub-bullets with 4 spaces
* multi
line
bullet
- dashes and
+ pluses are ok too
```
### What it looks like

 **Tip:** You can also use the **bulleted list** ()
button in the compose box to insert bulleted list formatting.
Learn more.

## Numbered lists

Zulip supports Markdown formatting for numbered lists.
You can create numbered lists by putting a number followed by a `.` at the start
of each line. Lists are numbered automatically, so you can reorder list items
while editing your message without having to update the numbers. Add two spaces
before the number to create a nested list.

### What you type

```
1. numbered lists
1. increment automatically
   1. use nested lists if you like
   3. delete or reorder lines without fixing the numbering
1. one more
   17. lists can start at any number
   18. so you can continue a list after some other text
```
### What it looks like

 **Tip:** You can also use the **numbered list** ()
button in the compose box to insert numbered list formatting.
Learn more.

## Indenting list items

In Zulip, you can increase or reduce the indentation of a list item using keyboard shortcuts in the compose box.

- Press `Ctrl` + `]` to increase the
indentation of the current list item.
- Press `Ctrl` + `[` to reduce the
indentation of the current list item.

 **Tip:** You can indent bulleted and numbered list items using keyboard
shortcuts. Learn more.

## Links

In Zulip, you can insert a named link using Markdown formatting. In addition, Zulip automatically creates links for you when you enter:

- A URL
- A reference to a channel, topic, or specific message (see also Link to a message or conversation)
- Text that matches a custom linkifier set up by your organization

### What you type

```
Named link: [Zulip homepage](zulip.com)
A URL (links automatically): zulip.com
Channel link: #**channel name**
Topic link: #**channel name>topic name**
Message link: #**channel name>topic name@123**
Custom linkifier: For example, #2468 can automatically link to an issue in your tracker.
```
### What it looks like

 **Tip:** You can also use the **link** ()
button or a keyboard shortcut (`Ctrl` + `Shift` +
`L`) to insert a link. Learn more.

## Code blocks

You can write snippets of code, code blocks, and other text in a fixed-width font using standard Markdown formatting. Zulip also has syntax highlighting and supports configuring custom code playgrounds.

### What you type

````
Inline code span: `let x = 5`
Code block:
```
def f(x):
   return x+1
```
Syntax highlighting:
```python
def fib(n):
    # TODO: base case
    return fib(n-1) + fib(n-2)
```
````
 **Tip:** You can also use `~~~` to start code blocks, or just indent the code 4 or more
spaces.

### What it looks like

A widget in the top right corner of code blocks allows you to easily copy code to your clipboard.

 **Tip:** You can also use the **code** ()
button in the compose box to insert code formatting.
Learn more.

 **Keyboard tip:** You can also use `Ctrl` + `Shift` + `C`
to insert code formatting.

## LaTeX

Zulip supports math typesetting powered by KaTeX. Their support table is a helpful resource for checking what’s supported or how to express something.

### What you type

````
Inline: $$O(n^2)$$
Displayed:
``` math
\int_a^b f(t)\, dt = F(b) - F(a)
```
````
### What it looks like

 **Tip:** You can also use the **math (LaTeX)** ()
button in the compose box to insert LaTeX formatting.
Learn more.

## Quotes

You can format quotes one line at a time, or create a block of text that will be formatted as a quote.

### What you type

````
> a multi-line
quote on two lines
normal text
```quote
A multi-paragraph
quote in two paragraphs
```
````
### What it looks like

 **Tip:** There is a handy option to quote message to a
message in Zulip.
You can also use the **quote** ()
button in the compose box to insert quote formatting.
Learn more.

## Spoilers

Zulip lets you temporarily hide content in a collapsible **spoiler** section,
with only the header initially shown. Clicking on the header reveals the hidden
content.

### What you type

````
```spoiler The spoiler heading might summarize what's inside
This content is initially hidden.
> You can combine spoilers with other formatting.
```
A message can contain both spoilers and other content.
```spoiler
Leave the heading blank if you like.
```
````
### What it looks like

Collapsed spoilers:

Expanded spoilers:

 **Tip:** You can also use the **spoiler** () button in the compose
box to insert spoiler formatting. Learn more.

## Emoji and emoticons

You can use emoji in Zulip messages and topics. There are several ways to use an emoji in your message:

- Enter an emoji name
surrounded by `:`, with help from autocomplete suggestions.
- Select an emoji from the emoji picker
- Use an emoticon
- Paste an emoji

You can add custom emoji for your organization. Like default emoji, custom emoji can be entered into the compose box by name, or selected from the emoji picker.

### What you type

`:octopus: :heart: :zulip: :)`
### What it looks like

## Mention a user or group

You can mention a team member or user group to call their attention to a message. Mentions follow the same notification settings as direct messages and alert words. A silent mention allows you to refer to a user without triggering a notification. A wildcard mention allows you to mention everyone on a channel, or mention all topic participants.

### What you type

```
Users: @**Bo Lin** or @**Ariella Drake|26** (two `*`)
User group: @*support team* (one `*`)
Silent mention: @_**Bo Lin** or @_**Ariella Drake|26** (`@_` instead of `@`)
Wildcard mentions: @**all**, @**everyone**, @**channel**, @**topic** (two `*`)
```
 **Tip:** A `|` followed by a user ID is inserted automatically when you select a
user from the typeahead suggestions, if there are two users with the same
name in the organization.

### What it looks like

## /me action messages

You can send messages that display your profile picture and name as the
beginning of the message content by beginning a message with `/me`. You can
use this feature in conversations when you want to describe actions you’ve
taken or things that are happening around you using a third-person voice.

For example, if you are **Ada Starr**:

### What you type

`/me is away`
### What it looks like

## Global times

When collaborating with people in different time zones, you often need to express a specific time clearly. In Zulip, rather than typing out your time zone and having everyone translate the time in their heads, you can insert a time, and it will be displayed to each user in their own time zone (just like timestamps on Zulip messages).

### What you type

A date picker will appear once you type `<time`.

`Our next meeting is scheduled for <time:2024-08-06T17:00:00+01:00>.`
The selected time is inserted into your Markdown message along with your time zone (in ISO 8601 format).

### What it looks like

A person in San Francisco will see:

While someone in London will see:

 **Tip:** You can also use the **add global time** () button in the compose
box to select a time from the date picker. Learn more.

## Tables

Zulip supports Markdown formatting for tables.

### What you type

```
|| yes | no | maybe
|---|---|:---:|------:
| A | left-aligned | centered | right-aligned
| B |     extra      spaces      |  are |  ok
| C | **bold** *italic* ~~strikethrough~~  :smile:  ||
```
 **Tip:** The initial pipes (`|`) are optional if every entry in the first column is
non-empty.
The header separators (`---`) must be at least three dashes long.

### What it looks like

## Polls

Zulip makes it easy to create a poll. Polls in Zulip are collaborative, so anyone can add new options to a poll. However, only the creator of the poll can edit the question.

### What you type

```
/poll What did you drink this morning?
Milk
Tea
Coffee
```
### What it looks like

 **Tip:** You can also use the **add poll** () button in the compose box to create a
poll. Learn more.

## Collaborative to-do lists

Zulip supports creating shared to-do lists where any user who can access the
message can add tasks by entering the task’s title and description, and clicking
**Add task**. Once created, task titles and descriptions cannot be edited. The task
list title can be edited any time by the to-do list’s creator.

### What you type

```
/todo Today's tasks
Task 1: This is the first task.
Task 2: This is the second task.
Last task
```
### What it looks like

Tasks are marked (and unmarked) as completed by clicking the checkboxes on the left.

 **Tip:** You can also use the **add to-do list** () button in the compose box to create a
shared to-do list. Learn more.

## Paragraph and section formatting

Zulip supports Markdown formatting for paragraphs and visual section breaks, which you can use to control the layout of your text and to visually separate different sections of content.

### What you type

```
One blank space for a new paragraph
New line, same paragraph
New paragraph
---, ***, or ___ for a horizontal line
Over the line
---
Under the line
```
### What it looks like

## Message formatting reference

A summary of the formatting syntax above is available in the Zulip app.

**Desktop/Web:**

1. Click on the **help menu** () icon in the upper right corner of the app.
2. Select **Message formatting**.

 **Tip:** You can also open the compose box, and click
the **question mark** () icon
at the bottom of the compose box.