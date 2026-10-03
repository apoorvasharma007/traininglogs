# web/

The confirm UI: plain HTML and JavaScript, no build step. The API serves it at `/`, so there is
no separate web server.

Run the app locally and open `http://localhost:8000/`:

```bash
.venv/bin/uvicorn traininglogs.api.app:app --reload
```

Paste your API key into the X-Api-Key field once; the page remembers it. The API base URL
defaults to the page's own address.

`sample_inputs.md` has ready-to-paste sessions for trying the extract flow. Each Extract is a
paid model call.
