# oldwebsites

Tools for recovering archived websites and refreshing their asset references.

## Download an archived site

Use `scripts/restore_site.py` to find a Wayback capture and download same-domain pages and referenced assets into a local directory:

```sh
python3 scripts/restore_site.py https://example.com --output recovered/example
```

To select a particular year, pass `--year`, for example `--year 2004`. The downloader is limited to the starting hostname and 500 files by default; adjust the limit with `--max-files`.

Wayback contains rendered public pages, not the original server-side PHP source. PHP modernization therefore needs a separate source checkout or backup.

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

The updater scans PHP, HTML, CSS, and JavaScript files and changes text references only. It does not download, generate, or replace the asset files themselves.

## Modernize source code

The modernization runner invokes existing project tools: Rector for PHP, ESLint for JavaScript, and Stylelint for CSS. Install and configure those tools in the source project first. It checks by default; pass `--write` to allow fixes:

```sh
python3 scripts/modernize_code.py path/to/source
python3 scripts/modernize_code.py path/to/source --write
```

Rector, ESLint, and Stylelint apply only the rules configured in that project. Review the resulting diff and run the site's tests before deployment.
