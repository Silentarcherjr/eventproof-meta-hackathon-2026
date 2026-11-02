# License inventory

Project license: PENDING (task C-04; participant decision).

| Component | Version | License | Use |
|---|---|---|---|
| FastAPI / Starlette | >=0.115 | MIT / BSD-3 | backend API |
| Pydantic | >=2.9 | MIT | schemas |
| uvicorn | >=0.32 | BSD-3 | dev server |
| openai (Python SDK) | >=1.50 | Apache-2.0 | OpenAI-compatible client for Meta Model API |
| numpy | >=2.0 | BSD-3 | renderer |
| Pillow | >=13 | MIT-CMU (HPND) | overlay text |
| python-dotenv | >=1.0 | BSD-3 | local env |
| python-multipart | 0.0.32 | Apache-2.0 | form/file uploads |
| FFmpeg (system tool, not bundled) | apt/brew | LGPL/GPL (build dependent) | encode/probe; invoked as external program |
| Next.js | 15.5.28 | MIT | studio frontend |
| React / React DOM | 19.1.0 | MIT | studio frontend |
| Tailwind CSS | 4 | MIT | styles |
| Geist / Geist Mono (via next/font) | - | SIL OFL 1.1 | fonts |
| Playwright | 1.56.1 | Apache-2.0 | e2e smoke tests (dev only) |
| pytest, hypothesis, ruff, httpx, eslint, typescript | dev | MIT / MPL-2.0 (hypothesis) / Apache-2.0 | dev only |
| Pexels video 5903898 "Packages Moving on a Conveyor Belt" (not redistributed; URL + sha256 in benchmark/real/pexels/labels.json) | - | Pexels License | real-footage perception check |
| (full transitive list to be regenerated from `uv tree` / `npm ls` before going public) | | | |

Meta Model API is used under Meta's API terms (not redistributed). Model names: Muse Spark, SAM 3.1. Attribution text: "Built using Meta Model API, Muse Spark and SAM 3.1." No Meta logos/trademarks used to imply endorsement.
