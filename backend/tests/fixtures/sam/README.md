Hand-written fixtures in the documented SAM 3.1 wire format (dev.meta.ai/docs/sam/reading-segmentation,
read 2026-10-27). They are NOT real SAM output: mask payloads are placeholder characters, chosen to include
`|>` and `,` because the base85 alphabet is unpublished. Real responses go to `artifacts/sam_cache/` (untracked).

`real_sam31_canonical0_2obj.txt` is REAL `sam-3.1` output (response resp_6ae1327d45ae42f0693e49df, 2026-10-27) for our own
synthetic clip (canonical seed 0, 2 objects): 5 lines, including two-object lines. See `docs/evidence/2026-10-27_meta_api_smoke.md`.
