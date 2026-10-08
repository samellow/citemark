# Tables

Zulip supports Markdown formatting for tables.

## Examples

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