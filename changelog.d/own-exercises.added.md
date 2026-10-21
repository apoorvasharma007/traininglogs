`GET /exercises` sends the library and the person's own exercises. `POST /exercises` adds an
own exercise (a name and a primary muscle, or a link to a library exercise) and
`PUT /exercises/{user_exercise_id}` changes, renames, links or unlinks one. A name that is a
library exercise's name has to link to it; a clash with the library or your own names is 409.
