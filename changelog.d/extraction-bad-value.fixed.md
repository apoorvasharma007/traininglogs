One exercise with an impossible value (an RPE of 11, a negative weight) no longer aborts the
whole extraction: that exercise becomes a flagged placeholder and the others keep their data.
A model-service outage (timeout, dropped connection, 5xx) does the same for its one exercise.
