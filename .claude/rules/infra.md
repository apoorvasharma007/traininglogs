---
paths:
  - "infra/**"
  - ".github/workflows/**"
---

# Infrastructure

- Change Google Cloud only through Terraform in `infra/`, never by hand in the console. Read
  `infra/README.md` first.
- An unattended agent run never edits `.github/workflows/`.
