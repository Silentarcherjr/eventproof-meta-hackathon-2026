# MEVA data in this folder

`tracks/*.json.gz` and `population.json` are derived from the MEVA dataset, "Multiview Extended Video with Activities",
by Kitware Inc. and the Intelligence Advanced Research Projects Activity (IARPA). It is licensed under the Creative
Commons Attribution 4.0 International License (https://creativecommons.org/licenses/by/4.0/; https://mevadata.org/).

**Source:** the official Kitware activity annotations in meva-data-repo
(https://gitlab.kitware.com/meva/meva-data-repo), `annotation/DIVA-phase-2/MEVA/kitware`, for cameras hospital.G436,
school.G336, school.G424, school.G328, school.G339 and bus.G340.

**What we changed:**
- kept only vehicle actors that move (a track of at least 1 s, and a bottom-centre movement of at least 5 % of the
  frame width);
- kept every 3rd annotated frame (10 fps);
- reduced each actor's activities to one flag: whether it has a `vehicle_stops` activity.

No video is redistributed.

**Please cite:** Corona, K., Osterdahl, K., Collins, R., Hoogs, A. "MEVA: A Large-Scale Multiview, Multimodal Video
Dataset for Activity Detection." WACV 2021.
