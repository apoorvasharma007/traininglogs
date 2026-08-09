# Ad-hoc sessions

Sessions that aren't part of a formal phase/week program go here — calisthenics,
gymnastics rings, juggling, reaction drills, shadow boxing, mobility, home or gym
kettlebell/dumbbell work, or any mix of these. `program`, `phase`, and `week` stay
unset for these sessions; `focus` carries whatever detail distinguishes the day
(e.g. "Skills + Core", "Rings + Muscle-Up Prep", "Gym Calisthenics + Mobility").

Structured programs with phase/week live at `inputs/programs/<slug>/phase_N/week_N/`
instead — see that directory. If a session mixes calisthenics into a real structured
program (e.g. rings work on a Push day), it belongs there too, not here — just add
it as another exercise in that day's file.

**To log a session:** copy `templates/adhoc-template.md` to a new file here
(e.g. `2026-07-19.md`), fill it in, then run
`traininglogs log inputs/sessions/2026-07-19.md`. Two worked examples:
`templates/adhoc-example-home-skills.md` and `templates/adhoc-example-gym-calisthenics.md`.
