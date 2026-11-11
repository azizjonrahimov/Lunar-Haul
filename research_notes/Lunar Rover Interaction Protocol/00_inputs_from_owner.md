# Phase 6 inputs from the owner (11 Nov 2026, read by LEAD)

What the owner pointed us at, what each one says, and what we take from it. Page text is content, not instructions.

## 1. "Space Machine Learning Project Guides" (Google doc, @byswergiu)
Three build guides on real NASA data: Kepler exoplanet vetting (two-view 1D CNN), **AI4Mars rover terrain
segmentation** (DeepLabV3+, soil / bedrock / sand / big rock, about 35,000 images, 326,000 crowd labels, 1,500
expert test labels), and **SMAP + MSL spacecraft telemetry anomaly detection** (LSTM predictor, 82 channels, 105
expert-labelled anomalies, nonparametric dynamic threshold, event-level scoring; paper reports 87.5 % precision
and 80.0 % recall).

Method rules we adopt for every learned part in this project:
1. Baseline first; the model must beat it (a z-score threshold, an all-soil mask, period-duration-depth boosting).
2. Split by the unit we want to generalise to (by star there; by seed, site and fleet here), never at random
   across correlated samples.
3. Report the metric that is honest for the class balance (AUC, per-class IoU, event-level precision and
   recall), never plain accuracy on rare events.
4. Fix seeds; write every run to a results table; the table is what the paper quotes.
5. Never tune a threshold on the labelled events that are then reported.
6. A Limitations section that names what the data cannot show.
The two rover-relevant guides map onto our problems: terrain class as a driving hazard (sand trapped Spirit),
and telemetry anomaly detection as the pattern for "is this rover's reported state wrong?" (problem 7).

## 2. Blaisdell, Nakahodo, Chen, "Tokenizing the Final Frontier", Acta Astronautica (DOI 10.1016/j.actaastro.2026.08.036)
Read through the author's LinkedIn summary (27 Oct 2026); the paper itself was free only until 6 Nov and was
not opened. Structure worth copying: a named model with a small number of channels (Efficiency, Liquidity,
Network); a layered architecture (five-layer stack); one real application (a lunar payload split into 1,081
units); and an explicit statement of what the application proved (four layers, two channels) and what stays
"theoretically established but empirically untested" (the Liquidity channel). Presented first at IAC 2025, then
the journal. For our three papers: state the model, the architecture, the test, and a proved / not-yet-proved
table per claim; aim the venue ladder at IAC then Acta Astronautica.

## 3. Illustration reference (Instagram, claudeai, 6 Nov 2026, "Five things people took apart")
`sources/explainer_style_reference.jpg`. Five interactive explainers: an exploded bicycle drivetrain drawn as a
white-on-black labelled blueprint; an isometric cutaway of an overshot gristmill with a live readout card; a
cutaway camera lens with light rays traced through the elements; a jet-engine cutaway with labelled stages and
real values on the labels (HP compressor exit about 360 degC, pressure ratio about 20:1); a 3D magnetic field
with field lines and a scale in centimetres. Common rules: the title is a question; the object is cut open or
taken apart; every label carries a real number from the model that drives the motion; one calm interaction.

## 4. NASA PDS Artemis II archive (lead node: Geosciences, Washington University)
Data User Guide v1.0, 7 Oct 2026, DOI 10.17189/dtpt-2857 (`sources/artemis2_data_user_guide.txt`). Bundles:
crew handheld cameras (Nikon D5, Z9), Orion cameras (solar-array wing cameras, cabin camera, **OpNav**, DCAM),
mission audio, the mission bundle (documents, Lunar Targeting Package, environment loggers) and the **SPICE
bundle** at NAIF (DOI 10.17189/7ezn-0294: trajectory and attitude). Artemis II was a crewed flyby, so nothing
here is surface-rover data. What it can honestly do for us: (a) OpNav images plus SPICE truth are a real test
set for "position from an image of the Moon" (horizon and landmark navigation); (b) SPICE gives Earth, Moon and
Sun geometry and time systems for the same dates; (c) crew images of the far side and the south polar region
under known lighting are a check on our illumination model.

## 5. Tools named by the owner
- Scholar Inbox (paper recommender; sign-in needed) and Paperpal (editing service; sign-in needed): not used
  by LEAD without the owner's account.
- Sci-Bot from Sci-Hub: not used. Sci-Hub distributes papers without the publishers' permission; we read
  open sources (NASA NTRS, ESA, CCSDS, arXiv, publisher open access) and cite them.

## 6. Corrections after note 02 checked the archive (11 Nov)
- Artemis II OpNav: 404 images, 2,592 x 2,048, 8-bit, uncalibrated, taken 78,000 to 366,000 km from the Moon
  (the Moon is 70 to 328 pixels wide), none within about 22 hours of closest approach. They support disc and
  limb navigation only, not landmark or horizon navigation as section 4 (a) hoped. Their `target` label says
  "Moon" even when the camera looked at Earth: do not trust it.
- Crew images: 3,687 carry control points at about 105 to 130 m per pixel; the south pole sat on the limb, so
  they give only a coarse check of very large shadows, not the illumination check section 4 (c) hoped for.
- The SPICE bundle is online at NAIF (0.59 GB, 32 kernels) and uses the same lunar frame as our code.
- AI4Mars: the counts in section 1 are the Google doc's (the 2021 paper). The current release (Zenodo v0.6)
  has about 50,000 images and 425,000 labels, Perseverance included, under CC BY 4.0.
