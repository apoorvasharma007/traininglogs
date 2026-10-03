# Sample inputs

Sessions to paste into the app's text box when testing Extract. Each one is written the way a
person types after a workout, at a different level of detail. Every Extract is a paid call to
Claude Haiku, a few cents each, so try one or two at a time.

Samples 1 to 6 are lifting sessions. Samples 7 and 8 test what the app is for beyond lifting: a
run and a skills session.

---

## 1. One line, four exercises

No line breaks at all. The model has to find where each exercise starts inside a single line,
which it used to get wrong.

```
Push day. Bench press 60kg for 8, 8, 6 at RPE 9. Incline DB press 22kg for 10, 10, 8. Cable flye 3 sets of 12. Shoulder press machine 40kg for 10, 10, 8.
```

---

## 2. A casual paragraph, five exercises

No headings, a bit of commentary, and one warmup mentioned in passing.

```
Pull day today, back felt a bit tired from Tuesday.

Deadlift: warmed up with the bar, then 60kg x5, 100kg x5, then worked sets 140kg x5, 140kg x5, 145kg x3 at RPE 9 — grip started going on the last one.

Lat pulldown 3 sets of 10 at 55kg, felt smooth.

Barbell row 70kg for 8, 8, 8, nothing crazy.

Face pulls, 3 sets of 15 light, just for shoulder health.

Bicep curls dumbbell 14kg for 12, 12, 10.
```

---

## 3. Detailed, six exercises, with warmups, RPE, a failure note and a drop set

The most for the model to get right: a warmup block, grinder reps described in words, and a drop
set written as part of a sentence instead of its own row.

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

## 4. A numbered list, four exercises

Typed quickly in a notes app, numbered but without headings. Has a date in the first line.

```
Upper body — 2026-08-10

1. Overhead press: 45kg x6, 45kg x6, 40kg x8 (RPE 9 on set 3)
2. Pull-ups: bodyweight, 10, 8, 6
3. Dips: bodyweight +10kg, 3 sets of 10
4. Hammer curls: 16kg dumbbells, 3 sets of 10
```

---

## 5. Headings and fields, six exercises, with a superset

Written with headings by hand. Two exercises share one heading as a superset, and the model should
still split them into two exercises.

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

## 6. The bare minimum, five exercises

Names, weights and set counts. No RPE, no notes.

```
Chest and back. Bench 80kg 5x5. Rows 70kg 5x5. Pullups bodyweight 3x8. Dumbbell press 24kg 3x10. Lat raises 10kg 3x15.
```

---

## 7. A run

Distance, time, heart rate and splits, with strides at the end. Nothing here is a weight.

```
Easy run + strides
5.2 km in 31:40, avg HR 148. legs heavy from yesterday's squats
splits 6:12, 6:05, 6:01, 6:08, 5:58
4 strides at the end, ~100m each, felt snappy
```

---

## 8. A skills session

Reflex drills and handstand practice, measured in rounds, hits and hold times instead of weight
and reps.

```
Skills - reflex + handstand
Reaction ball drills 3 rounds of 2 min, dropped maybe 6 catches in round 1, 2 in round 3
Light board reaction test 3 x 30s, best 41 hits
Wall handstand holds 30s, 35s, 28s - wrist ok today
Freestanding attempts for 10 min, longest kick-up hold ~6s
```
