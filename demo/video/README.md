# Demo video

`build.sh` produces the 3-minute demo from the real studio: Playwright records the studio replaying recorded runs
(cached Meta outputs, 0 live calls), cards are rendered from HTML with numbers read from committed files
(`benchmark/real/POOLED.json`), and the narration (`narration.txt`, taken from `docs/DEMO_SCRIPT.md`) is spoken by the
macOS synthetic voice "Samantha".

    # API with 0 live calls + studio, then:
    sh demo/video/build.sh /tmp/ep-video        # -> /tmp/ep-video/eventproof_demo.mp4 (1920x1080, H.264 + AAC)

The rendered MP4 is not committed (`*.mp4` is ignored); a local copy goes to `demo/video/out/`.
