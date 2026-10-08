# The pipeline

## Assets

One JSON object per line in `data/assets.jsonl`:

| field | values |
|---|---|
| `id` | `a0001` … |
| `name` | `<subject>-<style>-<size>`, not unique |
| `subject` | what it depicts: `search`, `cart`, `user`, `home`, `settings`, `back`, `bell`, `trash`, `heart`, `star`, `calendar`, `camera`, `lock`, `mail`, `download`, `upload`, `play`, `pause`, `edit`, `share`, `filter`, `clock`, `map`, `wifi` |
| `style` | `line`, `filled`, `duotone`, `3d`, `flat` |
| `color` | `red`, `blue`, `green`, `gray`, `black`, `white`, `yellow`, `purple`, `orange` |
| `size` | 16, 24, 32, 48, 64 |
| `platform` | `ios`, `android`, `web`, `all` |
| `kind` | `icon`, `illustration`, `component`, `photo` |
| `format` | `svg`, `png`, `lottie` |
| `version`, `downloads` | integers |
| `tags`, `desc` | free text, incomplete on purpose |

## Queries

A query names a subject and one to five of the attributes above, in English, Chinese or a mix,
using whatever words a person might use for them. It may also state a preference. A query in
`data/train.jsonl` carries `gt` (the asset it means) and `relevant` (every asset with the same
subject).

## Which asset a query means

1. Candidates are the assets whose subject and every mentioned attribute match the query.
2. If the query prefers a format (`svg`, `png`, `lottie`), keep only candidates in that format,
   unless none has it.
3. If the query asks for the latest, keep only the highest `version`.
4. Of what remains, the asset with the most `downloads` is the one; ties go to the lower `id`.

Rule 4 applies whether or not the query said "most popular". A query with no preference and a
single candidate means that candidate.

## Interfaces

```python
# recall.py
def recall(query: str, assets: list[dict]) -> list[str]:
    """Up to 20 asset ids, best first. Scored on whether gt is among them and on how many of
    them share gt's subject."""

# select.py
def select(query: str, candidates: list[str], assets: list[dict]) -> str | None:
    """One id from candidates (or None). Scored on whether it is gt."""
```

Both are plain modules at the repository root, standard library only, no file or network
access; `assets` is passed in on every call. Each stage must finish a 400-query split within
90 seconds.

## Scores

- `recall`: `100 × (0.7 × recall@20 + 0.3 × mean precision)` on the held-out split.
- `select`: `100 × hit rate` on the held-out split, with candidates from the current `recall.py`.
