# Browser tests

These tests use Playwright with Django's existing test runner. The server and
database are created by `StaticLiveServerTestCase`; no running demo or admin
account is required. Uploaded files use a temporary media directory.

From the repository root, install the Python dependencies and Chromium:

```bash
uv sync --group test --group e2e
uv run --group e2e playwright install chromium
```

On Linux, use `uv run --group e2e playwright install --with-deps chromium` to install the browser's
system dependencies as well.

Build the frontend dependencies so the browser can load the application's CSS
and JavaScript. Node.js and Corepack are required; Corepack selects the Yarn
version declared in `package.json`.

```bash
corepack enable
yarn install --immutable
make static-vendor
```

Run all public ticket creation scenarios:

```bash
uv run --group e2e quicktest.py tests.e2e.test_public_ticket_creation -v 2
```

To watch the browser with a one-second delay between actions:

```bash
HEADED=1 SLOW_MO=1000 uv run --group e2e quicktest.py tests.e2e.test_public_ticket_creation -v 2
```

`HEADED=1` opens the browser window. `SLOW_MO` is a delay in milliseconds;
the defaults are headless execution with no delay.

Browser tests are excluded from the default `make test` discovery by the
package's `load_tests` hook. Run each browser module explicitly, as above.
The `e2e` CI job installs Chromium and runs these tests separately from the
backend matrix.

The image scenario uses `tests/e2e/fixtures/ticket-attachment.png`. Include this small PNG
alongside the test code when submitting changes.
