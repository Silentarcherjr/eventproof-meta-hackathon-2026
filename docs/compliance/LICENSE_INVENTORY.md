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
| Pexels video 15411757 "High Angle View of a Busy Intersection in Novi Sad, Serbia" (not redistributed; URL + sha256 in benchmark/real/novisad/PREREGISTRATION.md) | - | Pexels License | real traffic loop |
| Pexels video 36366105 "Busy urban intersection in Wroclaw, Poland" (not committed; URL + sha256 in benchmark/real/traffic_v2/PREREGISTRATION.md) | - | Pexels License | real traffic, second city |
| Pexels video 35172060 (drone view of an intersection; six crops, not committed; URL + sha256 in benchmark/real/fresh_v1/PREREGISTRATION.md) | - | Pexels License | fresh camera view |
| Pexels videos 15928375 and 37247586 (bike lane, zebra crossing; not committed; benchmark/real/domains/PREREGISTRATION.md) | - | Pexels License | new domains |
| Pexels videos 39026834 and 39044387 (bike path, Santos; not committed; benchmark/real/santos/PREREGISTRATION.md) | - | Pexels License | new country |
| Pexels video 39488108 (rainy crossing from above; not committed; benchmark/real/with_umbrella/PREREGISTRATION.md) | - | Pexels License | two-object rule |
| INTERACTION dataset, drone trajectories and Lanelet2 maps (Zhan et al., arXiv:1910.03088); small derived trajectories committed in benchmark/interaction/, raw archive not committed | DR v1.1 | CC BY 4.0 (attribution and changes in benchmark/interaction/ATTRIBUTION.md) | stop-law sensitivity at scale |
| MEVA annotations (benchmark/meva/ATTRIBUTION.md) | - | CC BY 4.0 | scale attempt, reported as not usable |
| MnDOT Report 2020-17 (cited in README, not redistributed) | 2020 | public report, cited | definitions used by human coders |
| Transitive dependencies | lockfiles | their own licenses (`backend/uv.lock`, `frontend/package-lock.json`) | |

Meta Model API is used under Meta's API terms (not redistributed). Model names: Muse Spark, Muse Wonder, SAM 3.1. Attribution text: "Built using Meta Model API, Muse Spark and SAM 3.1." No Meta logos/trademarks used to imply endorsement.

Pexels clips are never committed to this repository. The live studio streams the clips it judges (and short crops of
them), which the Pexels License allows; no clip is sold or offered as stock.
