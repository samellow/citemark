# Configure multi-language search

Zulip supports full-text search, which can be combined arbitrarily with Zulip’s full suite of search filters. By default, Zulip search only supports English text, using PostgreSQL’s built-in full-text search feature, with a custom set of English stop words to improve the quality of the search results.

Self-hosted Zulip organizations can instead set up an experimental PGroonga integration that provides full-text search for all languages simultaneously, including Japanese and Chinese. See here for setup instructions.