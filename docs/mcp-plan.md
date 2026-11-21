# Drafting with Claude over MCP (plan for review, no code yet)

Kasi drafts real patterns from the basic blocks with Claude in claude.ai, through an MCP server on our
engine, and watches the pattern change live in the studio. ADR 0018 records the change of direction.

## Shape

- **Where:** the existing Railway `web` service. MCP at `https://<web domain>/mcp` (Streamable HTTP),
  next to the studio and its API. Built with the official MCP Python SDK (`mcp` 2.x).
- **A pattern** is a studio work item of a new kind, `pattern`: a block of the library at a size of its
  table or on a person's measurement file. Every change is a new version kept in Postgres (the actions,
  the note, who made it, and the pattern it produced). Undo and redo move between versions; restore
  makes a new version equal to an old one, so it can be undone too.
- **Active pattern:** each Claude connection works on one. A new connection (or one after a redeploy)
  starts on the person's most recently used pattern. Every result starts with the pattern's name and
  version, so it is always clear which one Claude is working on.
- **Live studio:** the pattern's page in the studio checks for a new version every second and redraws
  without losing zoom, showing the change's note ("Claude: lengthen the hem by 5 cm").
- **Few tools, schemas on demand:** 22 MCP tools. The drafting tools of `config/tools/` (about 40, plus
  an edit and a delete for each simple one) are not MCP tools themselves: Claude lists them, reads one
  tool's help, and passes `{tool, args}` lists to `preview` and `apply`.
- **Compact results:** text in pattern-making terms, at most 30 rows per list (with "and 12 more"),
  never the whole pattern. claude.ai accepts about 150,000 characters per result and 240 s per call.

## The tools

**Library and patterns**

| Tool | One line |
| --- | --- |
| `list_blocks` | The blocks you can start from (skirt, trousers, bodice, one-piece sleeve of the Aldrich women's basic set), their pieces, and the size table they are drafted for |
| `start_pattern(block, name, measurements)` | Start a new pattern from a block, at a size of its table (for example UK 12) or on a person's measurement file. It becomes the active pattern and appears in the studio |
| `open_pattern(pattern)` | Make another pattern the active one |
| `list_patterns` | The patterns you can open: name, block, measurements, version, last change |
| `list_measurements` | The sizes of the block's table and the people's measurement files you can draft with |
| `set_size(size)` | See the active pattern at another size or on another person. The pattern does not change |

**Looking**

| Tool | One line |
| --- | --- |
| `overview` | The pattern on one page: its pieces (closed or not, outline length), the proposed landmark names on each piece (marked unconfirmed), its variables with formula and value, the measurements it uses with their values |
| `find(...)` | Points, lines, curves and pieces by label, by proposed landmark name, by piece, by kind, or near a point |
| `inspect(object)` | How one object is made: its formulas and values, what it is built from, what is built from it; optionally its value at every size |
| `render(...)` | A picture: one size or every size nested, chosen pieces, labels and landmark names on or off, objects highlighted. Returned as an image |
| `measure(...)` | A distance, a curve length, or two seams compared (for example front and back side seam), at every size, with the difference |

**Changing**

| Tool | One line |
| --- | --- |
| `list_tools` | The drafting tools by group (points, lines, curves, arcs, moving and mirroring, pieces, variables, edits and deletes), one line each |
| `tool_help(tool)` | One drafting tool's arguments and one worked example |
| `preview(actions)` | Try a list of drafting actions without keeping them: what would be added, changed or deleted (and what is built on it), the new values at the smallest and largest size, and any problem it would cause |
| `apply(actions, note)` | Make the same list for real, all or nothing, with a one-line note. Returns the new version and the labels made |
| `undo` / `redo` | Take back the last change / put it back |
| `checkpoint(name)` | Name the current version, to come back to it |
| `restore(checkpoint or version)` | Go back to a checkpoint or any version (as a new change, so it can be undone) |
| `history` | Every change as a sentence, newest first: version, note, who made it (Claude or the studio), and each action in words ("Point C on line A to B, half its length from A") |

**Checking and output**

| Tool | One line |
| --- | --- |
| `validate` | The pattern at every size: formula errors and where, pieces whose outline is not closed, seam pairs that do not match, and typed numbers that will not follow the size |
| `export(format, size)` | A download link: `.sm2d`, SVG, PNG, PDF or DXF. Every file says it is net (stitch lines), because seam allowance is not computed yet |

"At every size" means every distinct size of the block's table (the basic set's 15 sizes are 5 sets of
numbers); for a person's file, the file and its two nudged copies (as decided for plan validation).
"Smallest and largest" are UK 6 and UK 14, or the two nudged copies.

Proposed landmark names appear in `overview`, `find` and `render` labels, always marked unconfirmed.

## Auth

**OAuth**, against the studio accounts, from the start (no secret-URL step): with the SDK's authorization
server support it is under a day's work.

- claude.ai registers itself (Dynamic Client Registration), signs in with PKCE (S256) and refreshes its
  token. Only the redirects `https://claude.ai/api/mcp/auth_callback` and
  `https://claude.com/api/mcp/auth_callback` are accepted.
- The sign-in page is the studio's (email and password), then one consent page: "Allow Claude
  (claude.ai) to draft patterns as Kasi?".
- Tokens are stored hashed in Postgres; access tokens last an hour, refresh tokens rotate. Disabling a
  person or resetting their password ends their connections.
- Fallback if something blocks OAuth: a long secret in the URL path from a Railway variable, as Kasi
  allowed. Not planned.

## Exports: easy and hard

The basic set draws its pieces on top of each other, so every export except `.sm2d` lays the pieces out
side by side, in simple rows, as drafted (no nesting, no grainline yet). One size per file by default.

| Format | How hard | Why |
| --- | --- | --- |
| `.sm2d` | Easy | Our writer already round-trips losslessly. Seamly2D also needs the measurement file, so both come together |
| PNG | Easy | The renderer exists (Pillow) |
| SVG | Easy | The renderer exists; add true 1:1 size in mm and the piece layout |
| DXF | Easy to medium | With `ezdxf` (MIT): each piece a closed polyline on its own layer, in cm, curves flattened finely (0.1 mm). **Hard** only if a cutting program needs AAMA/ASTM DXF (blocks per piece, grade rules) |
| PDF | Medium, the most work | 1:1 on A4 tiles with overlap, alignment marks, row and column labels, a 10 cm test square, a page map, plus a one-page overview. `reportlab` (BSD) |

Download links are signed (with `SESSION_SECRET`) and expire; the file is made from the stored
version when the link is opened, so nothing is kept on Railway's disk.

## The log

Every MCP call is stored: time, person, tool, arguments, a short result, pattern and version, how long it
took. The studio shows the log on the pattern's page and downloads it as JSONL.

## Tests

- **CI (every push):** an MCP client (the SDK's) against the app in the test process: the OAuth flow,
  then start from the skirt block, lengthen the hem by a formula, validate at every size, export every
  format, and read each file back (the `.sm2d` with our reader, which must compute the same).
- **Oracle workflow:** the same test with the pinned Seamly2D: it opens the exported `.sm2d` and must
  compute the same points and curves as the engine, bit for bit (as for the basic set today).

## Order

| Step | What | Stop |
| --- | --- | --- |
| a | This plan | **Kasi's OK** |
| b | Patterns, looking, changing, `validate`, OAuth, the log, the live studio, `docs/mcp-setup.md` | **Kasi connects claude.ai and tries it** |
| c | Exports | Report |
| d | Only if easy: manual drafting in the studio (forms generated from `config/tools/`, click the canvas to pick objects) | Report |

Not now: seam allowance, notches, grainline.

## Railway

No new variable: the server uses `DATABASE_URL`, `SESSION_SECRET` and `STUDIO_TOKEN` (already set) and
finds its own address from Railway's `RAILWAY_PUBLIC_DOMAIN`. `PUBLIC_URL` is only needed with a custom
domain. `docs/mcp-setup.md` (step b) lists them with the connector URL.
