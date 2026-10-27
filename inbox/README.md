# Inbox: paste job ads here

For ads from JobStreet, LinkedIn, Hiredly, Maukerja or anywhere else.

1. Open [`dump.txt`](dump.txt) on GitHub and tap the pencil (Edit).
2. Paste as many ads as you like below the line, old or new. Put a line with `---` between ads, or start each ad with its link.
3. Tap **Commit changes**.

A run starts within a few minutes. It splits the ads, skips ones it has seen before, saves them to `data/pasted.jsonl`, scores them and empties `dump.txt` again. Pasted ads stay on the shortlist for 30 days.

Tip: the first lines of an ad are read as title, company and location, which is how JobStreet and LinkedIn copy-pastes usually start. You can also write `Title:`, `Company:`, `Location:` or `URL:` lines to be exact.
