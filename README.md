# oldwebsites

Tools for recovering archived websites and refreshing their asset references.

**Status: Beta, ongoing work.** This toolkit is experimental and incomplete. It can automate configured checks and fixes, but it does not guarantee a complete conversion of an old site to modern code. Review all changes and test the recovered site before using it in production.

## Download an archived site

Use `scripts/restore_site.py` to find a Wayback capture, enumerate archived URLs for that hostname in the snapshot year, and download those pages and assets into a local directory. It also follows same-host references in HTML and CSS:

```sh
python3 scripts/restore_site.py https://example.com --output recovered/example
```

To select a particular year, pass `--year`, for example `--year 2004`. Without `--year`, it uses the year of the latest available starting-page capture. The downloader has no file limit by default; use `--max-files 1000` to set one.

This aims to copy every URL Wayback exposes for that hostname and year, but cannot recover content Wayback never captured. Failed downloads and reaching an optional file limit are reported and return a nonzero exit status, indicating the copy is incomplete.

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

The modernization runner invokes existing project tools: Rector for PHP, ESLint for JavaScript, Stylelint for CSS, and Prettier to format HTML. These tools only apply the rules configured in the source project; HTML is formatted but not structurally upgraded. Install and configure the tools first. The runner checks by default; pass `--write` to allow fixes:

```sh
python3 scripts/modernize_code.py path/to/source
python3 scripts/modernize_code.py path/to/source --write
```

Wayback provides rendered pages, not PHP source, so PHP modernization requires a separate source checkout or backup. Review the resulting diff and run the site's tests before deployment.
