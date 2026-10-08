# Spoilers

Zulip lets you temporarily hide content in a collapsible **spoiler** section,
with only the header initially shown. Clicking on the header reveals the hidden
content.

## Insert spoiler formatting

**Via compose box button:**

1. Open the compose box.
2. *(optional)* Select the text you want to hide inside the spoiler.
3. Click the **spoiler** () icon at the bottom of the
compose box to insert spoiler formatting.
4. Replace `Header` with the desired heading text.

 **Tip:** You can also use the **spoiler** () icon to remove
existing spoiler formatting from the selected text.

**Via Markdown:**

1. Open the compose box.
2. To create a spoiler section, use triple backticks and the word spoiler
(```` ```spoiler ````) followed by an optional spoiler heading, some text, and triple
backticks at the end:
````
```spoiler The spoiler heading
This content is initially hidden.
```
````

 **Tip:** A message can contain both spoilers and other content, and you can combine
spoilers with other formatting.

## Examples

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