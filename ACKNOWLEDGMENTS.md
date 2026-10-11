# Acknowledgments

The exercise library (`src/traininglogs/db/exercise_library.yaml`) and its fixed lists of muscles,
joint actions and movement patterns (`exercise-library-plan.md`) are built on the work below. Each
entry says what it decided in the library.

## Research

- Pelland JC, Remmert JF, Robinson ZP, Hinson S, Zourdos MC. *The resistance training dose
  response: meta-regressions exploring the effects of weekly volume and frequency on muscle
  hypertrophy and strength gain.* SportRxiv preprint.
  [sportrxiv.org](https://sportrxiv.org/index.php/server/preprint/view/460)
  Counting sets per muscle: a set counts 1 for each primary muscle and 0.5 for each secondary
  muscle.
- Maeo S, et al. *Triceps brachii
  hypertrophy is substantially greater after elbow extension training performed in the overhead
  versus neutral arm position.* European Journal of Sport Science, 2023.
  [PubMed](https://pubmed.ncbi.nlm.nih.gov/35819335/)
  Every triceps exercise has both triceps muscles as primary; overhead extensions grow the long
  head more.
- Kholinne E, et al. *The different role of each head of the triceps brachii muscle in elbow
  extension.* Acta Orthopaedica et Traumatologica Turcica, 2018.
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6136322)
  Presses list the triceps lateral and medial heads, not the long head.
- Rodríguez-Ridao D, Antequera-Vique JA, Martín-Fuentes I, Muyor JM. *Effect of five bench
  inclinations on the electromyographic activity of the pectoralis major, anterior deltoid, and
  triceps brachii during the bench press exercise.* International Journal of Environmental
  Research and Public Health, 2020. [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7579505/)
  The chest split into Upper Chest and Mid/Lower Chest; a 45 degree incline press has the front
  delts as primary alongside the upper chest.
- Kubo K, Ikebukuro T, Yata H. *Effects of squat training with different depths on lower limb
  muscle volumes.* European Journal of Applied Physiology 119(9):1933-1942, 2019.
  [Summary](https://www.strongerbyscience.com/squats-adductors/)
  Squats and leg presses list the vastus muscles, glute max and adductors, not the rectus femoris
  or hamstrings.
- Maeo S, et al. *Greater hamstrings muscle hypertrophy but similar damage protection after
  training at long versus short muscle lengths.* Medicine & Science in Sports & Exercise, 2021.
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7969179/)
  Seated and lying leg curls are separate exercises; seated grew the hamstrings more.
- *Electromyographic (EMG) study of the elbow flexors during supination and pronation of the
  forearm.* [PubMed](https://pubmed.ncbi.nlm.nih.gov/7570586/) and *Brachialis muscle activity
  can be assessed with surface electromyography*, Frontiers in Physiology, 2021.
  [Frontiers](https://www.frontiersin.org/articles/10.3389/fphys.2021.809422/full)
  Brachialis is its own muscle; hammer and reverse curls lead with the brachialis and
  brachioradialis.
- *A review of the anatomy of the hip abductor muscles, gluteus medius, gluteus minimus, and
  tensor fascia lata.* Clinical Anatomy, 2012. [PubMed](https://pubmed.ncbi.nlm.nih.gov/22109658/)
  Abductors are glute med, glute min and TFL, under Hips; Glutes is glute max only.
- *Assessment of tibial rotation and meniscal movement using kinematic magnetic resonance
  imaging.* [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4237875/)
  Knee internal and external rotation are joint actions.

## Anatomy references

Used to check every muscle, what it does, and every joint action.

- StatPearls (NCBI Bookshelf): [serratus anterior](https://www.ncbi.nlm.nih.gov/books/NBK531457/),
  [rotator cuff](https://www.ncbi.nlm.nih.gov/books/NBK513324/),
  [deltoid](https://www.statpearls.com/point-of-care/20331),
  [brachioradialis](https://ncbi.nlm.nih.gov/books/NBK526110),
  [lower back muscles](https://www.statpearls.com/point-of-care/28131),
  [teres major](https://www.ncbi.nlm.nih.gov/books/NBK580487/)
- Kenhub: [brachioradialis](https://www.kenhub.com/en/library/anatomy/brachioradialis-muscle)
- TeachMeAnatomy: [anterior compartment of the leg](https://teachmeanatomy.info/lower-limb/muscles/leg/anterior-compartment)
- WikiMSK: [adductor muscles of the hip](https://wikimsk.org/wiki/Adductor_muscles_of_the_hip)
- Wikipedia: [trapezius](https://en.wikipedia.org/wiki/Trapezius),
  [calf raises](https://en.wikipedia.org/wiki/Calf_raises)
- Iliopsoas and rectus femoris as hip flexors:
  [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11250012/)
- Subtalar joint motion, University of Oklahoma Health Sciences Center:
  [OUHSC](https://ouhsc.edu/bserdac/dthompso/web/gait/knmatics/STJOPEN.HTM)
- Neck muscles: [antranik.org](https://antranik.org/muscles-of-the-neck-and-vertebral-column/)

## Movement patterns

The patterns have no single scientific standard; the list follows coaching consensus.

- Dan John's five fundamental movements and John Rusin's six:
  [John Rusin](https://drjohnrusin.com/6-foundational-movements-that-every-person-on-earth-needs-to-master/),
  [Breaking Muscle](https://breakingmuscle.com/go-beyond-the-5-fundamental-movement-patterns/)
- The anti-movement model for core training:
  [NFPT](https://nfpt.com/anti-core-training-the-importance-of-stabilizing-the-spine/)

## Data

- [free-exercise-db](https://github.com/yuhonas/free-exercise-db) by yuhonas, released into the
  public domain (Unlicense). Used to find exercises missing from the library and to cross-check
  muscles.
