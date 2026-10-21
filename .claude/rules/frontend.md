---
paths:
  - "frontend/**"
---

# The app

- The look is locked (since 2026-10-04): fonts, the colours in `frontend/src/index.css`, type
  sizes, spacing, icons, and the layout of existing screens. New screens reuse them. Propose any
  visual change, label text included, and wait for Apoorva's yes.
- A screen's main action goes in `BottomBar` (`aboveTabs` on screens with tabs). Secondary and
  destructive actions are small text at the end of the content. Sheets use `Sheet`.
- Anything that changes saved data (programs, following, deleting) asks first or offers Undo.
