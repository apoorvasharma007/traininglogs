# Sample inputs for manually testing the confirm UI

Paste one of these into the textarea at http://localhost:8000/ and hit Extract. Each is a
different shape/level of detail a real person might actually type — not the clean, structured
`.md` format the CLI's file-based path is used to. **Every Extract click is a real paid Haiku
call** (a few cents) — pick one or two, not all six back to back.

---

## 1. Terse, single line, 4 exercises

No line breaks at all — this is the shape that used to break exercise chunking (fixed in
Phase 5, see `CHANGELOG.md`).

```
Push day. Bench press 60kg for 8, 8, 6 at RPE 9. Incline DB press 22kg for 10, 10, 8. Cable flye 3 sets of 12. Shoulder press machine 40kg for 10, 10, 8.
```

---

## 2. Casual multi-line paragraph, 5 exercises, moderate detail

No headers, a little color commentary, one exercise has a warmup mentioned inline.

```
Pull day today, back felt a bit tired from Tuesday.

Deadlift: warmed up with the bar, then 60kg x5, 100kg x5, then worked sets 140kg x5, 140kg x5, 145kg x3 at RPE 9 — grip started going on the last one.

Lat pulldown 3 sets of 10 at 55kg, felt smooth.

Barbell row 70kg for 8, 8, 8, nothing crazy.

Face pulls, 3 sets of 15 light, just for shoulder health.

Bicep curls dumbbell 14kg for 12, 12, 10.
```

---

## 3. Detailed, 6 exercises — warmup, RPE, failure technique, a drop set

The kind of input with the most for the model to get right: a warmup block, a failure-technique
note, and a drop set described in prose rather than as its own row.

```
Legs, felt strong. Deload week is over.

Squat — warmup 40kg x8, 60kg x5, 80kg x3. Working sets: 100kg x8 RPE 7, 100kg x8 RPE 8, 100kg x6 RPE 9.5, that last one had two grinder reps at the end, form held up though.

Romanian deadlift 80kg for 10, 10, 10, RPE 8 across the board.

Leg press 200kg for 12, 12, 10.

Walking lunges bodyweight, 3 sets of 20 steps each leg.

Leg curl machine 45kg for 12, 12, 12, last set was a drop set down to 30kg for 8 more.

Calf raises 60kg for 15, 15, 15, 15.
```

---

## 4. Semi-structured numbered list, 4 exercises

Someone typing quickly in a notes app, numbered but not headered.

```
Upper body — 2026-08-10

1. Overhead press: 45kg x6, 45kg x6, 40kg x8 (RPE 9 on set 3)
2. Pull-ups: bodyweight, 10, 8, 6
3. Dips: bodyweight +10kg, 3 sets of 10
4. Hammer curls: 16kg dumbbells, 3 sets of 10
```

---

## 5. Structured with headers, 6 exercises, includes a superset

Closer to the CLI's usual `.md` shape, but written by hand rather than to spec — and a superset
written as one combined section, which is a real edge case for the splitter (it's told a
superset is two exercises, not one entry).

```
## Push Session

**Focus:** Chest and shoulders
**Duration:** ~55 min

### Exercise 1
**Name:** Flat Bench Press
Sets: 70kg x8, 70kg x8, 70kg x6 RPE 9

### Exercise 2
**Name:** Incline Bench Press
Sets: 55kg x10, 55kg x10, 55kg x8

### Exercise 3 & 4 (superset)
**Name:** Cable Lateral Raise / Cable Rear Delt Flye
3 rounds of 15 each side, light weight, superset back to back with almost no rest.

### Exercise 5
**Name:** Tricep Pushdown
3 sets of 12 at 35kg

### Exercise 6
**Name:** Overhead Tricep Extension
3 sets of 12 dumbbell, 18kg
```

---

## 6. Bare minimum, 5 exercises, no RPE or notes at all

The sparsest realistic input — just names, weights, and set x rep counts.

```
Chest and back. Bench 80kg 5x5. Rows 70kg 5x5. Pullups bodyweight 3x8. Dumbbell press 24kg 3x10. Lat raises 10kg 3x15.
```
