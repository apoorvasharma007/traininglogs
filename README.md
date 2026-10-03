# traininglogs

traininglogs turns workout notes written however you like into structured training data.

You paste in a session the way you'd jot it down in Apple Notes: half sentences, `100 x 3 atg`,
"left knee felt off on set 2". The app reads it and lays out a confirmation card showing what it understood from your note, like exercises and sets, with weights, reps and effort. You fix whatever it got wrong by tapping it, confirm, and the session lands in Postgres DB.

The goal is an app that can log any kind of training. Someone who runs, cycles, lifts and practises
skills like reflex drills shouldn't need a different app, or a different format, for each. So the
input stays open: no form, no template. The app's job is to make sense of what you wrote and
store it reliably enough that progress can be tracked from it later. The insights part comes
next: a user dashboard that turns the stored sessions into a picture of your progress.

Right now it's a personal app with a single user, running at
https://traininglogs-875429444117.us-east1.run.app (it asks for an API key). Accounts for other
people come later.

How it works inside: [docs/design.html](docs/design.html).
