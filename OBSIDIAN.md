# Opening LLmWiki-KennisBank in Obsidian

This guide explains how to open the `$HOME/KennisBank` vault in [Obsidian](https://obsidian.md), which plugins are worth installing, and how to make the editor cooperate with the templates, frontmatter, and wikilinks that Claude Code already produces.

The instructions assume you have completed the setup in the main `README.md` and that `$HOME/KennisBank/` exists with the directory layout described in `vault-structure/README.md`.

---

## 1. Why Obsidian

Obsidian is a local-first markdown editor that reads and writes plain `.md` files in a directory you choose. It is free for personal use, runs offline, and renders the `[[wikilink]]` syntax that `scripts/auto-crosslink.py` already inserts into your wiki articles. You get a navigable graph view, a backlinks pane, fast search across YAML frontmatter, and a community plugin ecosystem that adds query, templating, and tag-management features that this vault benefits from. Obsidian itself is closed-source freeware, not FOSS. The file format is open: every note is a regular markdown file, so you can switch tools at any time without converting anything.

Fully open-source alternative: [Logseq](https://logseq.com) reads markdown vaults and supports `[[wikilinks]]` as well, with a different (block-based) editing model.

---

## 2. Install Obsidian

Download from [obsidian.md/download](https://obsidian.md/download).

On macOS with Homebrew:

```bash
brew install --cask obsidian
```

On Linux a `.AppImage` and `.deb` are provided on the download page. On Windows there is an installer and a portable build.

---

## 3. Open the vault

First-run flow:

1. Launch Obsidian.
2. If the welcome screen offers to create a "Help" vault, decline it.
3. Click "Open folder as vault".
4. Select `$HOME/KennisBank`.
5. Trust the vault when prompted (this enables community plugins later).

After the vault opens, Obsidian creates `$HOME/KennisBank/.obsidian/` to store its own configuration. This is expected. If you put the vault under git, exclude the noisy parts of `.obsidian/` (see section 10) and keep the rest so plugin settings stay portable.

You should now see the directory tree on the left: `00-inbox/`, `01-raw/`, `02-wiki/`, and so on. Markdown files will render with the existing YAML frontmatter at the top.

---

## 4. Recommended core settings

Open `Settings` (gear icon, bottom-left) and adjust:

**Files & Links**
- New link format: `Shortest path when possible`. This matches the bare `[[stem]]` format that `auto-crosslink.py` produces.
- Automatically update internal links: `on`. Renames will rewrite incoming links.
- Default location for new attachments: `In subfolder under current folder`.
- Subfolder name: `attachments`.
- Use `[[Wikilinks]]`: `on`.

**Editor**
- Strict line breaks: `off`. This keeps the file markdown-standard, which is what Claude Code writes.
- Show frontmatter: `on` if you want to edit YAML inline; `off` if you prefer it folded.
- Readable line length: personal preference.

**Appearance**
- Pick a community theme from `Manage` if the default is not your taste. `Minimal` and `Things` are widely used free themes that work well with this vault.

**Hotkeys**
- Optional. Worth a look once you know which actions you repeat (insert template, open quick switcher, toggle reading mode).

---

## 5. Recommended community plugins

Enable community plugins first: `Settings -> Community plugins -> Turn on community plugins`. Then click `Browse` and search by name. All plugins below are free and open-source.

Ordered by usefulness for this vault:

1. **Templater**
   Better template engine than the core Templates plugin. Supports JavaScript expressions, dynamic dates, and prompts. Use it with `tpl-sessie-log.md` and `tpl-wiki-artikel.md` in `04-templates/`.

2. **Dataview**
   Query frontmatter as if your vault were a database. The wiki articles already carry `type`, `tags`, `status`, `created`, and `updated`, which is everything Dataview needs.

3. **Various Complements**
   Autocomplete for `[[wikilinks]]`, `#tags`, and frontmatter values. Reduces typos in links so `auto-crosslink.py` and the graph stay accurate.

4. **Tag Wrangler**
   Rename, merge, and inspect tags from a side pane. Useful as the wiki grows past a few dozen articles.

5. **Advanced Tables**
   Friendly editing for the markdown tables that appear in some wiki articles. Adds tab navigation and column alignment.

6. **Excalidraw**
   Hand-drawn sketches stored inside notes. Useful for diagramming concepts before turning them into wiki articles.

7. **Obsidian Git**
   Auto-commit and (optionally) push the vault on a schedule. Recommended if you version-control `$HOME/KennisBank` and want a safety net independent of Claude Code.

8. **Linter**
   Enforces consistent frontmatter formatting (key order, quoting, date formats). Helps keep `created`/`updated` fields stable across notes that Claude wrote and notes you edited.

9. **Periodic Notes**
   Daily, weekly, monthly notes. The `/sessielog` command already covers session-level capture, but if you want a separate daily journal alongside the session logs, this is the standard plugin.

10. **Paste image rename**
    Renames pasted images to a sensible filename instead of `Pasted image 20260508120000.png`. Pairs well with the `attachments` subfolder setting from section 4.

Install only what you actually use. More plugins means more startup time and more surface area for bugs.

---

## 6. Configuring Templater for the existing templates

After enabling Templater:

1. Open `Settings -> Templater`.
2. Set `Template folder location` to `04-templates`.
3. Optional: under `Folder Templates`, map folders to default templates so a new file in that folder pre-fills the template:
   - `01-raw/sessies` -> `04-templates/tpl-sessie-log.md`
   - `02-wiki` -> `04-templates/tpl-wiki-artikel.md`
4. Optional but useful: `Settings -> Hotkeys`, search "Templater: Open Insert Template modal", and bind it to a key (for example `Cmd+Shift+T`).

The existing templates use `{{date}}` and `{{onderwerp}}` placeholders written for Claude's prompt-time substitution. Templater uses `<% %>` syntax. If you want Obsidian-driven insertion, copy a template and replace placeholders, for example:

```
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
```

Keep the originals untouched so Claude commands keep working. Put the Templater variants next to them, for example `tpl-wiki-artikel.templater.md`.

---

## 7. Configuring Dataview for this vault

After enabling Dataview, paste these queries inside any markdown file. They use the frontmatter that `tpl-wiki-artikel.md` already produces.

Wiki articles by status, newest first:

````
```dataview
TABLE status, updated
FROM "02-wiki"
SORT updated DESC
```
````

Session logs from the last 7 days:

````
```dataview
LIST
FROM "01-raw/sessies"
WHERE date(created) >= date(today) - dur(7 days)
SORT created DESC
```
````

Wiki articles still in `concept` status, oldest first (these are the ones to review):

````
```dataview
TABLE created, updated, tags
FROM "02-wiki"
WHERE status = "concept"
SORT updated ASC
```
````

A useful place to put these queries is `02-wiki/index.md`, which the `/sessielog` and `CLAUDE.md` flows already reference at the start of every session.

---

## 8. Graph view tips

Open the graph from the left sidebar (the connected-dots icon).

- Filters: limit the search to `path:02-wiki/ OR path:01-raw/sessies/` so the graph reflects compiled knowledge plus its raw sources.
- Exclude templates: add `-path:04-templates` to the filter so `tpl-*.md` does not pollute the layout.
- Groups: under `Groups`, add one for `tag:#claude-sessie` (different colour for raw sessions) and one for `path:02-wiki` (different colour for compiled articles).
- Forces: lower `Link force` slightly if the graph collapses on itself, raise `Repel force` if nodes overlap.

The graph stays nearly empty until your wiki accumulates `[[wikilinks]]`. Run a few `/sessielog` and `/wiki` cycles, then open it again.

---

## 9. Working alongside Claude Code

Claude Code writes directly into the same vault while Obsidian is open. Obsidian watches the filesystem and hot-reloads changed files. In normal use this works fine, because Claude usually writes to `01-raw/sessies/` or `02-wiki/` while you are reading or editing somewhere else.

Two rules avoid edit conflicts:

- Do not have the same file open in edit mode in Obsidian while a Claude command is writing to it. Switch to reading mode (`Cmd+E` / `Ctrl+E`) before running `/sessielog`, `/wiki`, `/intake`, or `/stale`.
- If you do edit a file just before running a Claude command, save first (Obsidian autosaves on focus change, but a manual `Cmd+S` is safer).

If you ever see two diverging versions of a note, check `08-archive/` and the git history (if Obsidian Git is enabled). Obsidian writes through to disk; there is no hidden state.

---

## 10. Optional: gitignore for Obsidian

If you keep the vault under git, add the following lines to your `.gitignore` so per-machine UI state is not tracked, but plugin configuration still is:

```
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
```

Keep the rest of `.obsidian/` (`app.json`, `appearance.json`, `hotkeys.json`, `community-plugins.json`, `plugins/`) under version control so the same plugin set and settings travel between machines.

---

## 11. Mobile (optional)

Obsidian Sync is paid. Free options:

- iCloud Drive: place `$HOME/KennisBank` inside `iCloud Drive/Obsidian/` on macOS; the iOS app reads it natively.
- [Syncthing](https://syncthing.net): FOSS peer-to-peer sync, works for Android and Linux desktops. Slightly more setup, no third-party server.
- Git: clone the vault on the mobile device with a git client, pull and push manually. Lowest convenience, full control.

Pick one. Do not run two sync mechanisms over the same vault.

---

## 12. Troubleshooting

**Templates do not insert.**
Templater is not enabled, or `Template folder location` does not point at `04-templates`. Re-check `Settings -> Community plugins` and `Settings -> Templater`.

**Wikilinks break after renaming a file.**
`Automatically update internal links` is off. Turn it on under `Settings -> Files & Links`. For files renamed before that setting was enabled, use the command palette: `Files: Update internal links`.

**Graph view is empty.**
The vault does not yet contain `[[wikilinks]]`. Run `/sessielog` and `/wiki` a few times so `auto-crosslink.py` can write backlinks based on the graphify output, then reopen the graph.

**Vault feels slow.**
Either too many plugins are loaded at startup, or `attachments` (or `07-media/`) holds many large binary files. Disable plugins you do not use, and consider moving large media out of the vault and linking to them by absolute path.

**`.obsidian/` shows up as untracked in git and you do not want it.**
Add the whole directory to `.gitignore` instead of the partial list in section 10. You will lose plugin-config portability across machines, which is acceptable for single-machine setups.
