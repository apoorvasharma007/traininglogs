The server's database connections are safe to share between requests running at the same time.
When all ten are in use, a request waits up to ten seconds for one to come free, then answers "The
server is busy" (503) instead of failing with an error (500).
