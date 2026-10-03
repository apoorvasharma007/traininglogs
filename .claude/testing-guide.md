# Testing

1. Run all the tests:

   ```bash
   docker compose up -d db_test
   .venv/bin/pytest tests/
   ```

   They need the test database in Docker, on port 5433. The tests clear its sessions as they run,
   so nothing you store there lasts. The suite has to finish with 0 failed and 0
   skipped before a step merges.

2. To check a change to the web page without paying for AI, run the app on the test database:

   ```bash
   DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/uvicorn traininglogs.api.app:app --reload
   ```

   Open `http://localhost:8000/`, pick a session under "Repeat a past session", and you get a
   real card to click around, at no cost. If the list is empty because the tests just cleared the
   database, extract one sample from `web/sample_inputs.md` once (a few cents), confirm it, and
   repeat that as often as you like.

3. After a deploy, open the live app and check that the page loads, then check that the app
   refuses a request without your API key:

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://traininglogs-875429444117.us-east1.run.app/sessions
   ```

   It should print `401`.

Tests that touch the database use the real test database, never mocks. A test that breaks
because of your change gets fixed or rewritten in the same step, never skipped.
