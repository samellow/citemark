# LaTeX

Zulip supports math typesetting powered by KaTeX. Their support table is a helpful resource for checking what’s supported or how to express something.

## Insert LaTeX formatting

Zulip’s compose box has a smart **math (LaTeX)** () button,
which inserts contextually appropriate LaTeX formatting:

- If no text is selected, the button inserts displayed LaTeX (```` ```math ````) formatting.
- If selected text is on one line, the button inserts inline LaTeX (`$$`)
formatting.
- If selected text is on multiple lines, the button inserts displayed LaTeX
(```` ```math ````) formatting.

**Via compose box button:**

1. Open the compose box.
2. *(optional)* Select the text you want to format.
3. Click the **math (LaTeX)** () icon at the bottom of
the compose box to insert LaTeX formatting.

 **Tip:** You can also use the **math (LaTeX)** () icon to remove
existing LaTeX formatting from the selected text.

**Via Markdown:**

1. Open the compose box.
2. To use inline LaTeX, use double dollar signs (`$$`) around the text:
`$$O(n^2)$$` To use displayed LaTeX, use triple backticks and the word math
(```` ```math ````) followed by some text and triple backticks at the end:
````
```math
\int_a^b f(t)\, dt = F(b) - F(a)
```
````

## Examples

### What you type

````
Inline: $$O(n^2)$$
Displayed:
``` math
\int_a^b f(t)\, dt = F(b) - F(a)
```
````
### What it looks like

## Copy and paste formatted LaTeX

### Copy LateX from a message in Zulip

Zulip supports quoting, forwarding, or copying math expressions, and pasting them into the compose box.

 **Tip:** If you select part of a math expression to copy, Zulip will automatically
expand your selection to copy the full expression.

### Copy LaTeX from an external website

You can copy LaTeX from many third-party sites that use KaTeX, and paste it into Zulip.

 **Tip:** If copy-pasting math from a website isn’t working, consider contacting the
website’s administrators with the information below, as it may be an easy fix.

This feature is powered by KaTeX’s MathML annotations, which embed the original LaTeX source in the HTML for a math expression. For it to work, the website needs to:

- Generate math expressions using KaTeX in the default `htmlAndMathml` output
mode.
- Allow MathML annotations to be included in HTML copied by the browser (for Zulip, this was a couple lines of CSS).