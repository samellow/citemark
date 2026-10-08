"""Chunking by headings (PRD 5.1): paths, anchors, blocks, labels, code fences and long sections."""

from citemark.evals.snapshot import normalize
from citemark.ingest.chunk import MAX_TOKENS, PATH_SEPARATOR, chunk_document

URL = "https://zulip.com/help/star-a-message"
ARTICLE = """# Star a message

Starring messages is a good way to keep track of important messages.

## Star a message

**Desktop/Web:**

1. Hover over a message to reveal three icons on the right.
2. Click the **star** icon.

 **Tip:** You can unstar a message using the same instructions.

**Mobile:**

1. Press and hold a message until the long-press menu appears.

## View your starred messages

### On mobile

Tap **Starred messages**.

### On mobile

Tap the **menu** tab first on older apps.

## Import the history

Run the following commands: ```
# stop the server first
./scripts/stop-server
```

````
```spoiler Not a heading either
# still code
```
````
"""
ANCHORS = (
    ("Star a message", "star-a-message"),
    ("View your starred messages", "view-your-starred-messages"),
    ("On mobile", "on-mobile"),
    ("On mobile", "on-mobile-1"),
    ("Import the history", "import-the-history"),
)


def path(*parts: str) -> str:
    return PATH_SEPARATOR.join(parts)


def test_each_section_is_a_passage_under_its_heading_path():
    passages = chunk_document("Star a message", ARTICLE, URL, ANCHORS)
    assert [p.heading_path for p in passages] == [
        path("Star a message"),  # the introduction
        path("Star a message"),  # the section named like the article reads once
        path("Star a message", "View your starred messages", "On mobile"),
        path("Star a message", "View your starred messages", "On mobile"),
        path("Star a message", "Import the history"),
    ]  # "View your starred messages" has no text of its own, so no passage
    assert [p.position for p in passages] == [0, 1, 2, 3, 4]
    assert all(p.text.startswith(p.heading_path + "\n\n") for p in passages)


def test_anchors_are_matched_in_page_order_even_when_headings_repeat():
    passages = chunk_document("Star a message", ARTICLE, URL, ANCHORS)
    assert [p.anchor_url for p in passages] == [
        None,
        f"{URL}#star-a-message",
        f"{URL}#on-mobile",
        f"{URL}#on-mobile-1",
        f"{URL}#import-the-history",
    ]


def test_a_label_stays_with_the_block_it_introduces():
    blocks = chunk_document("Star a message", ARTICLE, URL, ANCHORS)[1].blocks
    assert blocks == (
        "**Desktop/Web:**\n1. Hover over a message to reveal three icons on the right.\n2. Click the **star** icon.",
        "**Tip:** You can unstar a message using the same instructions.",
        "**Mobile:**\n1. Press and hold a message until the long-press menu appears.",
    )


def test_lines_inside_code_are_never_headings():
    passages = chunk_document("Star a message", ARTICLE, URL, ANCHORS)
    assert not any("stop the server" in p.heading_path or "Not a heading" in p.heading_path for p in passages)
    code = passages[-1].text
    assert "# stop the server first" in code and "# still code" in code


def test_no_text_is_lost():
    passages = chunk_document("Star a message", ARTICLE, URL, ANCHORS)
    kept = normalize(" ".join(block for p in passages for block in p.blocks))
    for line in ARTICLE.splitlines():
        if line.strip() and not line.startswith("#"):
            assert normalize(line) in kept, line


def test_a_long_section_splits_at_paragraphs_into_passages_of_about_the_same_size():
    paragraphs = [f"Paragraph {n}. " + "word " * 80 for n in range(20)]  # about 2,100 tokens in all
    passages = chunk_document("Guide", "# Guide\n\n## Setup\n\n" + "\n\n".join(paragraphs), URL)
    assert len(passages) == 5
    assert all(p.heading_path == path("Guide", "Setup") for p in passages)
    assert all(p.token_count <= MAX_TOKENS + 10 for p in passages)
    assert [block for p in passages for block in p.blocks] == [p.strip() for p in paragraphs]


def test_a_long_list_splits_between_its_items():
    steps = "\n".join(f"{n}. " + "step " * 60 for n in range(1, 16))
    passages = chunk_document("Guide", f"# Guide\n\n## Install\n\n**Linux:**\n{steps}", URL)
    blocks = [block for p in passages for block in p.blocks]
    assert len(blocks) > 1
    assert blocks[0].startswith("**Linux:**\n1. ")
    assert all(block.split("\n")[-1][0].isdigit() for block in blocks)  # each piece ends on a whole item
    assert "\n".join(blocks) == f"**Linux:**\n{steps}".rstrip()  # a block's edges are trimmed, nothing else
