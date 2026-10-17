# oldwebsites

Tools for recovering archived websites and refreshing their asset references.

## Recover an archived page

Use `scripts/restore_site.py` to find the latest Wayback Machine capture from 2000 onward and save its replay HTML:

```sh
python3 scripts/restore_site.py https://example.com --output recovered/example.html
```

To select a particular year, pass `--year`, for example `--year 2004`. The saved replay HTML may still load images, stylesheets, and scripts from the Wayback Machine; this first version does not mirror an entire site for offline use.

## Refresh asset references

Create a JSON mapping from old references to replacement references:

```json
{
	"assets": {
		"images/logo.gif": "assets/logo.svg",
		"http://example.com/site.css": "assets/site.css"
	}
}
```

Preview matching changes first, then apply them with `--write`:

```sh
python3 scripts/update_assets.py recovered --mapping assets.json
python3 scripts/update_assets.py recovered --mapping assets.json --write
```

The updater scans HTML, CSS, and JavaScript files and changes text references only. It does not download, generate, or replace the asset files themselves.
