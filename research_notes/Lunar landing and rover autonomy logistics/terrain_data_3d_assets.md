# Terrain data, imagery and 3D assets for a lunar south pole 3D web simulation (Artemis landing region)

Research date: 2026-10-15. Scope: public elevation data, textures/tile services, 3D models, landing-page imagery (and their licences), and web rendering approaches for a scientifically grounded, visually professional Three.js/CesiumJS simulation of the Shackleton rim / Connecting Ridge / de Gerlache / Malapert / Mons Mouton (Leibnitz Beta) area. Every URL below was fetched or returned by search during this session unless marked otherwise. Session web-search budget ran out near the end; the affected items are listed under Gaps.

---

## Key question 1 — Elevation data: exact URLs, formats, sizes; which product to use for a ~20 km base model at 5–20 m; how to crop a 20×20 km window to a web heightmap

### Takeaway
The best public DEM for a ~20 km Artemis-region base model is NASA GSFC PGDA's LOLA 5 m/px work: either one of the per-site 20 km × 20 km GeoTIFF fields (e.g. Site04 Shackleton rim, Site01 Connecting ridge, Site11 de Gerlache rim, Site23 Malapert massif, Site20v2 Leibnitz beta plateau) or a `-projwin` crop of the 3.3 GB 87°S–90°S 5 m mosaic; for a lighter 20 m base use the 2.6 GB cloud-optimized `LDEM_80S_20MPP_ADJ.TIF`. All are south polar stereographic GeoTIFFs with no registration, so a 20 km window is a 4000×4000 (5 m) or 1000×1000 (20 m) pixel crop that can be rescaled to a 16-bit PNG heightmap with GDAL.

### Cited Findings

**PGDA 5 m/px South Pole LOLA DEM Mosaic (87°S–90°S) — products/81**
- Product: "South Pole LOLA DEM Mosaic", author Michael K. Barker; 5 m/pixel; covers 87°S–90°S; GeoTIFF; south polar stereographic, X/Y in metres, MOON_ME frame, DE421 ephemeris; GMT "pixel-registered" convention (coordinates mark pixel centres) — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81)
- Files (all under `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/`): `ldem_87s_5mpp.tif` (3.3 GB, surface height Z in metres, interpolated where empty); `ldem_87s_5mpp_hillshade.tif` (820 MB); `ldsm_87s_5mpp.tif` (4.9 GB, slope in degrees); `ldec_87s_5mpp.tif` (140 MB, LOLA return count per pixel); context map `ContextMap_87S.png` — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81)
- Built by mosaicking 97 individual 20 km × 20 km fields, each overlapping its neighbours by 2 km, aligned by rigid 3‑D translation and blended with a cosine taper; typical RMS residual vs the individual fields 30–55 cm — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81)
- No registration mentioned; links are direct downloads — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81)
- Citation: Barker et al. 2021, "Improved LOLA Elevation Maps for South Pole Landing Sites: Error Estimates and Their Impact on Illumination Conditions", Planetary & Space Science 203, 105119, doi:10.1016/j.pss.2020.105119 — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81)

**PGDA individual 5 m/px site products (the natural "20 km base model" files) — products/78**
- Per-site GeoTIFF sets at 5 m/px, same projection (south polar stereographic, metres, MOON_ME, DE421). Base URL pattern `https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/SiteXX/` with files `SiteXX_final_adj_5mpp_surf.tif` (DEM), `_ldec.tif` (count), `_slp.tif` (slope), `_toterr.tif` (total Z uncertainty), `_slperr.tif` (slope uncertainty), `SiteXX_final_adj.xyzi` (point cloud), `SiteXX_ROIs.tgz` (shapefiles), plus `Clones/..._0001_err.tif`–`_0100_err.tif` (100 DEM clones for uncertainty) — [PGDA products/78](https://pgda.gsfc.nasa.gov/products/78)
- Sites listed: Site01 Connecting ridge; Site04 Shackleton rim; Site06 Nobile rim 1; Site07 Peak near Shackleton; Site11 de Gerlache rim; Site20 and Site20v2 Leibnitz beta plateau (v2 = extended boundaries, added 2022‑08‑15, prefix `Site20v2_`); Site23 Malapert massif; Site42 de Gerlache‑Kocher massif; plus Haworth, Shoemaker, DM1 Amundsen rim, DM2 Nobile rim 2, SL2 de Gerlache rim, SL3 Connecting ridge extension, NPA Cabeus exterior wall 1, NPB Amundsen 1, NPC Idel'son L crater 1, NPD Malapert crater 1, LM1 Shackleton Rim B, LM2–LM8 Shoemaker Rims A–F / Faustini Rim A. Site numbering follows Mazarico et al. (2011). The page does not use the name "Mons Mouton"; the equivalent is "Leibnitz beta plateau" — [PGDA products/78](https://pgda.gsfc.nasa.gov/products/78)
- Stated accuracy (Sites 1, 4, 7, 11): track geolocation ~10–20 cm horizontal, 2–4 cm vertical; median RMS Z error ~0.30–0.50 m; median RMS slope error ~1.5–2.5°; about 90 % of 5 m pixels are interpolated — [PGDA products/78](https://pgda.gsfc.nasa.gov/products/78)
- README (`https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README`): `*_surf.tif` = surface height Z in metres with interpolation; `*.xyzi` = binary double-precision X, Y, Z (km), RDRid (YYDOYHHMM); GeoTIFF X/Y are in metres; pixel-registered; cites Barker et al. 2021 and Mazarico et al. 2011 (Icarus 211, 1066–1081, doi:10.1016/j.icarus.2010.10.030) — [PGDA LOLA_5mpp README](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README)

**PGDA 10/20/30/40/60/80/120/240 m south polar products ("A New View of the Lunar South Pole from LOLA") — products/90**
- Base URL `https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/`; all TIFs are Cloud-Optimized GeoTIFFs; south polar stereographic, metres, MOON_ME / DE421; file pattern `PREFIX_LAT_PIX_ADJ[_STEM].TIF`; citation Barker et al. 2023, Planetary Science Journal 4, 183, doi:10.3847/PSJ/acf3e1; data DOI 10.60903/gsfcpgda-lola-spole — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- Key DEM files and sizes: `LDEM_80S_20MPP_ADJ.TIF` 2.6 GB (20 m, 80–90°S); 10 m / 83°S LDEM 4.8 GB; 30 m / 75°S 2.7 GB; 60 m / 60°S 2.9 GB; 40 m / 80°S 685 MB; 80 m / 80°S 181 MB; 120 m / 60°S 785 MB; 240 m / 60°S 210 MB. Companion stems per resolution: `_HILL` hillshade (45° alt/45° az; 1.3 GB at 20 m), `_ERR` height error, `_EFFRES` effective resolution, `LDSM` slope, `LDSM_ERR`, `LDEC` counts — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- PSR products on the 20 m basis: `LPSR_80S_20MPP_ADJ.TIF` (148 MB raster), `.SHP` (154 MB, all 506,349 PSRs) and `_1km2.SHP` (20 MB, 1,531 PSRs > 1 km²) with CSV/DBF/PRJ/SHX — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- Roughness products `LDRM_80S_{1000,50}MPP_ADJ_*` (height roughness, plane-fit slope, RMSD, Hurst exponent, RGB composite) — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- Point clouds: `LDEM_80S_ADJ.XYZI` 13 GB; `LDEM_60S_ADJ.XYZI` 48 GB — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)

**PDS LOLA GDR polar products (IMG + LBL; alternative archive)**
- `LDEM_87S_5M` 30336×30336 px, 5 m; `LDEM_85S_10M` 30336×30336, 10 m; `LDEM_80S_20M` 30400×30400, 20 m; `LDEM_75S_30M` 30496×30496, 30 m; `LDEM_60S_60M` 31040×31040, 60 m; `LDEM_45S_100M` 28880×28800, 100 m; all 16‑bit integer, polar stereographic, IMG with detached LBL; also `_FLOAT.IMG` and `.JP2` variants; HEIGHT = DN × SCALING_FACTOR (values in the .LBL) — [ODE LOLA GDR DEM help](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/LOLA/GDR/GDRDEM.htm)
- Archive: `https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr` — [ODE LOLA GDR DEM help](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/LOLA/GDR/GDRDEM.htm)

**LOLA polar illumination / PSR / sky-visibility maps — PGDA products/69**
- Products: average solar illumination `AVGVISIB_{65S,75S,85S}_{240M,120M,060M}_201608`; permanent shadow `LPSR_...`; Earth visibility `..._EARTH`; sky visibility `SKYV_65S_240M`. Resolutions: 240 m (65–90°S), 120 m (75–90°S), 60 m (85–90°S) — [PGDA products/69](https://pgda.gsfc.nasa.gov/products/69)
- Formats/URLs: GeoTIFF and COG at `https://pgda.gsfc.nasa.gov/data/MoonIllumination/` (e.g. `AVGVISIB_85S_060M_201608_COG.TIF`); PDS IMG/JP2 at `http://imbrium.mit.edu/EXTRAS/ILLUMINATION/`; polar stereographic, reference radius 1737.4 km, true scale at pole; no file sizes listed; some PSR links on the page point to wrong files — [PGDA products/69](https://pgda.gsfc.nasa.gov/products/69)
- Method: hourly timesteps over a full ~18.6‑year nutation cycle; Sun treated as a finite disc; cite Mazarico et al. 2011 — [PGDA products/69](https://pgda.gsfc.nasa.gov/products/69)

**LROC NAC DTMs (stereo) of the south-polar sites**
- 2013 release of three DLR-produced NAC DTMs: Connecting Ridge (`data.lroc.im-ldi.com/lroc/dtm_detail/181`), Shackleton Crater rim (`/dtm_detail/182`), Malapert Massif (`/dtm_detail/180`), originally for the ESA Lunar Lander study — [LROC news 709](https://lroc.im-ldi.com/news/709)
- Shackleton rim DTM `NAC_DTM_ESALL_SR12`: 2.0 m post spacing, 1 m/px source images; RMS error 0.5 m against 560 LOLA tracks; bounds lat −89.84 to −89.63, lon 180.8–226.6 °E; produced by DLR Institute of Planetary Research, GeoTIFF versions by ASU; products: 32‑bit GeoTIFF DTM, PDS IMG (`NAC_DTM_ESALL_SR12_P897S2037`), confidence, slope, shaded relief, colourshade, orthoimages/orthomosaic at 1 m and 2 m (`_NACMOS_1M`, `_NACMOS_2M`); orthophotos have several-metre horizontal offsets relative to the DTM — [LROC dtm_detail/182](https://data.lroc.im-ldi.com/lroc/dtm_detail/182); [NAC_DTM_ESALL_SR12 README](https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/DATA/SDP/NAC_DTM/ESALL_SR12/NAC_DTM_ESALL_SR12_README.TXT)
- LROC PDS archive paths now redirect from `pds.lroc.im-ldi.com` to `https://pds.mcp.nasa.gov/data/...` (observed 302) — [redirect observed on NAC_DTM README](https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/SDP/NAC_DTM/ESALL_SR12/NAC_DTM_ESALL_SR12_README.TXT)
- Newer (Sept 2025) shape-from-shading NAC DTMs of south-polar landing sites by Hemmi & Inoue (JAXA/ISAS): `DataS1.zip` 76.1 MB containing ROI shapefiles (CR1, GR1, GR2, LP1, MP1, MP2), 32‑bit GeoTIFF DTMs, orthomosaics and height-uncertainty maps; licence CC BY 4.0; DOI 10.5281/zenodo.17153447 — [Zenodo 17153447](https://zenodo.org/records/17153447)

**LROC NAC controlled mosaics of Artemis III candidate sites (texture source)**
- Example: `NAC_ROI_DEGERRIMLOC` "de Gerlache Rim 315–335° sub-solar longitude low-Sun controlled NAC mosaic (C)", centre lat −88.5, lon 293.3; 1.00 m/px with 5 m and 20 m versions; polar stereographic (code `P885S2933`); absolute positional accuracy 5–20 m; credit "NASA/GSFC/Arizona State University"; cite Henriksen et al. 2023, "Optimized Illuminated Terrain Coverage of the Candidate Artemis III Landing Sites with LROC NAC Controlled Mosaics", European Lunar Symposium — [LROC NAC_ROI_DEGERRIMLOC](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLOC)
- Other ROI mosaic pages surfaced for Mons Mouton (`NAC_ROI_MTMOUTONLOB/LOC/LOE`), Mons Mouton Plateau (`NAC_ROI_MOUTNPLTLOE`), Peak near Cabeus B (`NAC_ROI_CABEUSPKLOA/LOB/LO2`), de Gerlache‑Kocher (`NAC_ROI_DEGERKCHLO1`), Malapert (`NAC_ROI_MALAPERTLOG`) — [LROC view_rdr/NAC_ROI_MTMOUTONLOC](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_MTMOUTONLOC); [NAC_ROI_MALAPERTLOG](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_MALAPERTLOG)
- LROC RDR search supports filtering by prefix (NAC_DTM, NAC_ROI, NAC_POLE, WAC …), coordinate range and "Topographic Products" — [LROC rdr_product_select](https://data.lroc.im-ldi.com/lroc/rdr_product_select?filter%5Bprefix%5D%5B%5D=NAC_DTM&filter%5Bcenter_latitude%5D=-90..-84&page_size=100)

**ShadowCam (KPLO)**
- PDS archive at `https://pds.shadowcam.im-ldi.com/`, portal `https://data.im-ldi.com/`; derived products include Cloud-Optimized GeoTIFFs, histogram CSVs and smear maps; June 2025 release = 4,937 observations (Apr–Jun 2024), 6.27 TiB; credit "NASA/KARI/ASU" — [ShadowCam news 1454](https://shadowcam.im-ldi.com/news/1454)
- ShadowCam releases are imagery of shadowed terrain, not an illumination-map product — [search summary; ShadowCam news 1454](https://shadowcam.im-ldi.com/news/1454)

**Artemis III candidate regions (to pick the window)**
- NASA (28 Oct 2024) named nine regions: Peak near Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2, de Gerlache Rim 2, Slater Plain; analysed with LRO data — [NASA release 24‑136](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)

**Cropping tooling**
- GDAL `gdal_translate -projwin ulx uly lrx lry` selects a subwindow in georeferenced (dataset SRS) coordinates; `-srcwin` by pixel offsets; `-ot` forces output type (Byte/Int16/UInt16/…); `-scale` linearly rescales to the output type's range; `-outsize` resamples; `-a_nodata` sets NoData; source may be "either file name, URL of data source or subdataset name" — [GDAL gdal_translate](https://gdal.org/en/stable/programs/gdal_translate.html)
- COG = tiled (512 px default) TIFF with overviews and a layout "to minimize the number of GET requests needed by a reader doing random read access"; first 16 KB range returns all IFDs — [GDAL COG driver](https://gdal.org/en/stable/drivers/raster/cog.html)
- NASA SVS packs LOLA height into uint16 as half-metres with +20,000 offset so all values are positive (subtract 20,000, divide by 2 for metres) — a ready-made recipe for 16‑bit web heightmaps — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)

### Inferences
- Recommended base: for the cleanest provenance, download the single ~20 km per-site 5 m field you need (Site04 Shackleton rim, Site01 Connecting ridge, Site11 de Gerlache rim, Site23 Malapert massif, Site20v2 Leibnitz beta plateau) from products/78; these are already 20 km × 20 km fields (the mosaic page says it was built from 97 such fields with 2 km overlaps), so no cropping is needed beyond trimming the 2 km overlap. For arbitrary windows (e.g. de Gerlache Rim 2, Mons Mouton Plateau), crop the 3.3 GB 87°S mosaic or the 2.6 GB 20 m COG.
- Window arithmetic (my calculation): 20 km at 5 m = 4000 × 4000 px (float32 ≈ 64 MB raw, uint16 ≈ 32 MB raw, much less as 16‑bit PNG); at 10 m = 2000²; at 20 m = 1000². A 1000–2000 px 16‑bit PNG plus a precomputed normal map is a browser-friendly payload; use the 5 m data for a near-field detail tile around the lander.
- Crop recipe (combining the sourced GDAL options): `gdal_translate -projwin <ulx> <uly> <lrx> <lry> -ot UInt16 -scale <zmin> <zmax> 0 65535 -of PNG <src.tif> height.png`; store `<zmin>/<zmax>` as metadata so the shader recovers metres. Because PGDA files are COGs, reading them over HTTP with GDAL's `/vsicurl/` prefix should fetch only the needed tiles — note `/vsicurl/` was not confirmed on the two GDAL pages fetched (it is a standard GDAL virtual file system; verify locally).
- The X/Y window must be given in south polar stereographic metres (MOON_ME, radius 1737.4 km as used by the illumination products); convert the site centre lat/lon (e.g. de Gerlache rim mosaic centre −88.5°, 293.3°E; Shackleton DTM bounds −89.84…−89.63°, 180.8…226.6°E) with GDAL/pyproj — the exact PROJ string was not retrieved and should be read from the GeoTIFF's own metadata.
- Realistic lighting validation: the 60 m/85°S average-illumination and 20 m PSR rasters give ground truth for checking that simulated shadows and the PSR floors of Shackleton/de Gerlache behave correctly.

### Gaps
- PGDA products/90 does not state pixel dimensions or bit depth; the ODE page's 30400 × 30400 applies to the PDS IMG version, not necessarily the PGDA COG. The products/78 page and README do not list site centre coordinates or exact field extents (20 km fields is inferred from products/81's mosaic description).
- Could not confirm which NAC stereo DTMs exist for Mons Mouton / de Gerlache Rim 2 / Nobile: the LROC RDR filter URL returned anaglyph products instead of NAC_DTM, and the LROC "New NAC Topography" post is from 2013. The Zenodo ROI codes (CR1, GR1, GR2, LP1, MP1, MP2) are not mapped to site names on the record page.
- No ShadowCam-derived illumination map product was found; only imagery releases.
- Moon Trek south-pole layer identifiers (LOLA DEM/hillshade tiles) were not retrieved (API doc page loads them via JS; search budget exhausted).

---

## Key question 2 — Textures and globes: CGI Moon Kit, WAC mosaics, Moon Trek / tile services, Cesium Moon

### Takeaway
For a whole-Moon globe use the NASA SVS CGI Moon Kit (2025 colour map up to 2.4 GB TIFF, LOLA displacement 23040×11520), but note its polar colour is filled from a lower-resolution LOLA albedo map and it is "optimized for aesthetics, not science"; for the 20 km site the right texture is the 1 m/px LROC NAC controlled mosaic of the specific Artemis III site, with PGDA hillshades as a fallback. Moon Trek exposes OGC WMTS tiles (verified URL pattern, 9 zoom levels for the WAC layer) and Cesium ion serves "Cesium Moon" 3D Tiles (asset 2684829) with 5 m terrain / 1 m NAC imagery at the poles, but under Cesium's ToS (logo display, no offline storage).

### Cited Findings

**NASA SVS CGI Moon Kit (SVS 4720)**
- Colour maps (2025 version, Dec 2025, "preserves more of the color and dynamic range" and adds polar detail): `lroc_color.exr` float16 linear 942.8 MB; `lroc_color_16bit_srgb.tif` 2.4 GB; 16k TIFF 909.4 MB; 8k 232.0 MB; 4k 59.0 MB; 2k JPG 447 KB. 2019 version: `lroc_color_poles.tif` 27360×13680, 494.1 MB, down to 1k JPG — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)
- Displacement maps: `ldem_64.tif` 23040×11520 float km 1012.6 MB; `ldem_64_uint.tif` uint16 half-metres 506.3 MB; `ldem_16.tif` 5760×2880 63.3 MB; `ldem_4.tif` 1440×720 4.0 MB; heights relative to a 1737.4 km sphere; uint16 values offset by +20,000 — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)
- Sources: LROC WAC Hapke-normalized mosaic (643/566/415 nm as R/G/B); the 2025 colour map's source covers 70°N–70°S and the polar gaps (>20 % of pixels, ~6 % of surface) are filled with the lower-resolution LOLA LDAM albedo map; displacement from LOLA gridded products as of spring 2019 — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)
- Caveat: "optimized for aesthetics, not science"; credit line "NASA's Scientific Visualization Studio"; visualizer Ernie Wright (USRA), scientist Noah Petro — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)

**LROC WAC global mosaic (USGS Astrogeology)**
- "Moon LRO LROC WAC Global Morphology Mosaic 100m": 109,164 × 54,582 px, 8‑bit, 5.5 GB TIFF, simple cylindrical; polar areas were projected onto the LOLA shape model (80–90°) and GLD100 (60–80°); access constraint "public domain", use constraint "Please cite authors" (Speyerer et al. 2011, Wagner et al. 2015, Sato et al.) — [USGS Astropedia WAC mosaic](https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m); download `https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LROC-WAC_Mosaic_global_100m_June2013.tif`

**LROC NAC polar mosaics**
- NAC south pole mosaic README is in the LROC RDR volume at `.../DATA/BDR/NAC_POLE/NAC_POLE_SOUTH/NAC_POLE_SOUTH_README.TXT` — [LROC PDS NAC_POLE_SOUTH README](https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/NAC_POLE/NAC_POLE_SOUTH/NAC_POLE_SOUTH_README.TXT); the LROC RDR collection includes NAC DTMs, NAC ROI mosaics and NAC North/South polar mosaics — [LROC 30th PDS release](https://www.lroc.asu.edu/news/976)
- PGDA hillshade rasters for shading-only textures: `ldem_87s_5mpp_hillshade.tif` 820 MB; `LDEM_80S_20MPP_ADJ_HILL.TIF` 1.3 GB (45° altitude, 45° azimuth) — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81); [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- PGDA also publishes 20 m/px map-projected NAC image pairs (`M{ID}LE_20MPP.TIF`, `M{ID}RE_20MPP.TIF`, I/F) and simulated images (`_MODEL.TIF`, W/m²) for nine south-polar NAC frames — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)

**Moon Trek WMTS**
- Trek API page gives the pattern `https://{WMTS endpoint}/1.0.0/{Style}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.png`, with Style/TileMatrixSet read from each layer's GetCapabilities; projections offered: Equirectangular, North Pole, South Pole; "Some services are .png and some are .jpg" — [Trek WMTS API doc](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon)
- Verified example: `https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml` → layer `LRO_WAC_Mosaic_Global_303ppd_v02`, format image/jpeg, TileMatrixSet `default028mm`, TileMatrix ids 0–8, CRS `urn:ogc:def:crs:EPSG::104903`, ResourceURL `https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0//{Style}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.jpg` — [Trek WAC GetCapabilities](https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/WMTSCapabilities.xml)
- No usage terms, rate limits or attribution requirements are stated on the API page (footer "© 2016 Trek") — [Trek WMTS API doc](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon)

**Cesium Moon (Cesium ion)**
- Sources: LROC WAC Global Morphology Mosaic (mid-latitudes), WAC Global Morphologic Map (poles), LROC NAC images of the poles; terrain from LOLA RDR gridded data (poles) and Kaguya TC shaded-relief merge (60N–60S); every source credited "NASA and the USGS Astrogeology Science Center" — [Cesium Moon product page](https://cesium.com/platform/cesium-ion/content/cesium-moon/)
- Resolution tiers (polar, mirrored for south): imagery 100 m (60–90°), NAC 1 m (85.5–90°); terrain 60 m (60–90°), 30 m (75–90°), 20 m (80–90°), 10 m (85–90°), 5 m (87.5–90°); asset ID 2684829; requires a Cesium ion account; engines CesiumJS, Cesium for Unreal, Unity; renamed from "Cesium Moon Terrain" to "Cesium Moon" in September 2025 — [Cesium Moon product page](https://cesium.com/platform/cesium-ion/content/cesium-moon/); [Cesium blog 2024‑08‑06](https://cesium.com/blog/2024/08/06/introducing-cesium-moon-terrain/)
- Community (free) plan: 10 GB storage, 15 GB/month streaming, "Personal and non-commercial use", also exploratory commercial/government evaluation and unfunded education; paid licence required if the company has >$50K revenue/funding, for government projects, funded research, or above limits; Commercial $149/month individual — [Cesium ion pricing](https://cesium.com/platform/cesium-ion/pricing/)
- ToS §2.2.3: "the 'Cesium ion' logo must be prominently displayed on the main application window of Your Application" (splash/about page acceptable for mobile/immersive); §2.2.2: "You may not copy, store, or redistribute any portion of Cesium Data Output" for offline/local use, general-purpose caching excepted; third-party attribution requirements (Appendix B) are the user's responsibility — [Cesium ion Terms of Service](https://cesium.com/legal/terms-of-service/)
- Community report (CesiumJS 1.141): Cesium Moon terrain appears ~2.5 km higher than LOLA/SLDEM2015 at the same lon/lat; no official answer found — [Cesium community thread](https://community.cesium.com/t/cesium-ion-moon-terrain-appears-2-5-km-higher-than-lola-sldem2015-dem-at-the-same-lon-lat/46282)

### Inferences
- For the 20 km site, WAC-derived colour (100 m/px) is far too coarse and the CGI kit's polar colour is a LDAM fill; the professional-looking choice is the 1 m NAC controlled mosaic of the exact Artemis III site (downsampled 5 m/20 m versions exist), or, where no NAC ROI exists, a hillshade/albedo synthesized from the 5 m DEM.
- Use the CGI Moon Kit only for the distant globe/context view (4k–8k sRGB TIFF + `ldem_16_uint.tif`), credited to "NASA's Scientific Visualization Studio".
- Trek WMTS south-pole layers (polar stereographic) can be consumed by any OGC client once their GetCapabilities are located; the verified EQ pattern suggests the SP endpoint is `https://trek.nasa.gov/tiles/Moon/SP/{layer}/1.0.0/…`, but the layer names must be read from Trek's catalog.
- Cesium Moon is the quickest path to a streaming, LOD globe with real NAC polar imagery, but the logo and no-offline clauses and the free-tier limits matter for a public site; the reported ~2.5 km vertical offset must be checked before overlaying LOLA-derived positions.

### Gaps
- Exact Moon Trek south-pole layer identifiers and their GetCapabilities URLs were not retrieved.
- Cesium's "Content Usage and Attribution Guide" and "Cesium Global 3D Content" terms were not found (the /legal/ index lists only ToS, privacy, cookies).
- File sizes for the LROC NAC ROI 1 m mosaics were not listed on the product page.

---

## Key question 3 — 3D models: NASA 3D Resources, Artemis-era landers/rovers, what is public domain vs restricted, alternatives

### Takeaway
NASA's 3D Resources (now at science.nasa.gov/3d-resources, mirrored on GitHub as "free and without copyright") include an Apollo Lunar Module (3DS, 100,628 polygons), Lunar Reconnaissance Orbiter (STL + Blender), Gateway, SLS Block 1, RASSOR and a Space Exploration Vehicle, but no Lunar Roving Vehicle, Orion, or any Artemis-era lander; no official public models of Blue Moon, Starship HLS, LTVs or CLPS landers were found — only paid marketplace models — so procedural/low-poly stand-ins built from public specs (e.g. Starship HLS "roughly 50 meters tall") are the legally cleanest route.

### Cited Findings
- NASA 3D Resources (old nasa3d.arc.nasa.gov redirects to science.nasa.gov/3d-resources): "All of these assets are free to download and use"; assets mirrored on GitHub; users directed to NASA Images and Media Usage Guidelines — [NASA 3D Resources listing](https://science.nasa.gov/3d-resources/?exclude_child_pages=false&layout=grid&listing_page=no&listing_page_category_id=0&number_of_items=15&order=asc&orderby=title&current_page=1&requesting_id=447593&science_only=false&show_content_type_tags=yes&show_excerpts=no&show_pagination=true&show_publish_date=no&show_readtime=no&show_thumbnails=yes&science_org=6504&response_format=html&show_drafts=false&use_content_term_filters=true&post_types=any)
- GitHub mirror README: assets are "free and without copyright", linking NASA's usage guidelines; folders `3D Models/`, `3D Printing/`, `Images and Textures/` — [nasa/NASA-3D-Resources](https://github.com/nasa/NASA-3D-Resources)
- `3D Models/` folder names relevant to this project: "Apollo Lunar Module", "Lunar Reconnaissance Orbiter (A)" and "(B)", "Lunar Atmosphere and Dust Environment Explorer (LADEE)", "Gateway", "Space Launch System Block 1", "Regolith Advanced Surface Systems Operations Robot (RASSOR)", "Space Exploration Vehicle", "Habitat Demonstration Unit", "Mars 2020 Perseverance Rover", "Curiosity Rover (MSL)", "Viking Lander", "InSight Cruise Lander", "Saturn V"; no folder named Lunar Roving Vehicle/LRV, Orion, Artemis or VIPER appears in the two halves of the listing — [GitHub API contents, part 1](https://api.github.com/repos/nasa/NASA-3D-Resources/contents/3D%20Models); [GitHub tree view](https://github.com/nasa/NASA-3D-Resources/tree/master/3D%20Models)
- Apollo Lunar Module model: 3DS format, 100,628 polygons / 60,845 vertices; data.gov entry says "License not specified"; landing page `http://nasa3d.arc.nasa.gov/detail/lunarlandernofoil-c`; download `http://nasa3d.arc.nasa.gov/shared_assets/models/lunarlandernofoil-c/lunarlandernofoil-c.zip` — [data.nasa.gov Apollo Lunar Module](https://data.nasa.gov/dataset/nasa-3d-models-apollo-lunar-module)
- LRO model: `Lunar Reconnaissance Orbiter.stl` 0.41 MB and `.7z` Blender 4.54 MB; STL "may not yet be ideal for printing" — [search result for nasa3d jpl-vtad-lro](https://nasa3d.arc.nasa.gov/detail/jpl-vtad-lro) (page now redirects to science.nasa.gov/3d-resources)
- Other NASA 3D Resources lunar items are landing-site terrain assets: "Apollo 11 – Landing Site", Apollo 12/14/15/16 landing sites, "Apollo 11 – View of the Moon" — [NASA 3D Resources listing](https://science.nasa.gov/3d-resources/)
- Smithsonian: high-resolution 3D model of the Apollo 11 Command Module "Columbia" with downloadable data (3d.si.edu/apollo11cm); a secondhand report says Smithsonian Open Access released ~3 million images including 3D scans under CC0; no Lunar Module or LRV scan surfaced — [Smithsonian newsdesk](https://dashboard.si.edu/newsdesk/releases/smithsonian-releases-high-resolution-3-d-model-apollo-11-command-module-explore-and-print); [New Atlas on Open Access](https://newatlas.com/good-thinking/smithsonian-open-access/)
- Blue Moon / Starship HLS models found are commercial marketplace items only: "Blue Moon Mk1 Lunar Lander" $35 Blender, royalty-free licence (CGTrader); "Blue Moon Human Landing System" (CGTrader); Starship HLS interior/rigged Blender model $249 (Superhive); Starship HLS STL $5.99 (CGTrader); print files on Printables/Cults3D/MakerWorld — [CGTrader Blue Moon Mk1](https://cgtrader.com/3d-models/space/spaceship/blue-moon-mk1-lunar-lander); [CGTrader Blue Moon HLS](https://www.cgtrader.com/3d-models/space/spaceship/blue-moon-lunar-lander); [Superhive Starship HLS](https://superhivemarket.com/products/spacex-starship-hls--interior--rigged-3d-model); [CGTrader Starship HLS STL](https://cgtrader.com/3d-models/science/engineering/spacex-starship-hls-lunar-lander-adjustable-human-landing-system)
- Reference facts for modelling: NASA HLS page states Starship HLS is "roughly 50 meters tall", serves Artemis III and IV; Blue Moon appears only in an image caption; no credit lines displayed; page last updated 25 Mar 2026 with an editor's note that it is being updated for recent Artemis program changes — [NASA Human Landing System](https://www.nasa.gov/humans-in-space/human-landing-system/)
- NASA insignia (Meatball, Worm, Seal) are not public domain and are protected by law; images including logos may need clearance for promotional use; identifiable current astronauts/employees cannot be used commercially — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- A Three.js south-pole demo (Hack Club "Stardance") uses a 256×256 grid synthesized from LOLA crater profiles rather than real tiles — an example of the procedural route — [Stardance project 2554](https://stardance.hackclub.com/projects/2554)

### Inferences
- Legally usable now: NASA's Apollo LM, LRO, Gateway, SLS Block 1, RASSOR and Space Exploration Vehicle models (NASA guidelines: credit NASA, no implied endorsement, remove/avoid insignia textures in a commercial product). The LM 3DS will need conversion to glTF/GLB for Three.js.
- Not available as public-domain assets: Lunar Roving Vehicle, Orion, Blue Moon Mk1/Mk2, Starship HLS, LTV concepts (Intuitive Machines, Lunar Outpost, Astrolab), CLPS landers (Blue Ghost, Nova‑C). Marketplace models carry seller licences and may also embed company trademarks; company renders are copyrighted (see KQ4).
- Practical recommendation: parametric low-poly stand-ins (cylinder + legs for Blue Moon; 9 m-diameter, ~50 m tall cylinder for Starship HLS; generic 4-wheel rover for LTV) with neutral liveries, labelled "representative, not to scale/official", avoids both copyright and trademark issues while still reading as professional if lit and shadowed with the real terrain.

### Gaps
- Could not open individual science.nasa.gov/3d-resources model pages (LRO, LM) to confirm current formats/sizes; data came from the data.gov mirror and search snippets.
- No official public 3D model or dimensioned drawing of Blue Moon Mk1/Mk2 was retrieved (blueorigin.com returned HTTP 429 on all three attempts). NASA's LTV page returned 404 at `/humans-in-space/lunar-terrain-vehicle/`; current LTV provider status (as of Oct 2026) is unverified because the search budget ran out.
- Smithsonian 3D licensing was only confirmed secondhand (New Atlas); 3d.si.edu was not fetched.

---

## Key question 4 — Imagery for landing/about pages: NASA image API queries and usage rules; ESA/JAXA/SpaceX/Blue Origin image rights

### Takeaway
The NASA Image and Video Library API (`https://images-api.nasa.gov/search?q=…&media_type=image`) works without an API key and returns Collection+JSON with `nasa_id`, `title`, `description`, `secondary_creator` (used as credit, e.g. "NASA/GSFC/Arizona State University") and rendition `links`; NASA material is generally not copyrighted in the US but must not imply endorsement, must not use the NASA insignia/logotype, and must respect identifiable-person and third-party-copyright limits; ESA and JAXA permit editorial/educational use with credit but exclude commercial use without permission; SpaceX's Flickr licence status is unverified today (history: CC BY‑NC → CC BY → public domain in 2015, with a 2019 report of a change back to CC 2.0); Blue Origin terms could not be retrieved.

### Cited Findings

**NASA Image and Video Library API**
- Live query `https://images-api.nasa.gov/search?q=lunar%20south%20pole&media_type=image&page_size=3` returned `collection` {version "1.1", href, items, metadata, links}; each item has `href` (collection.json of renditions), `data[]` with `center`, `date_created`, `description`, `description_508`, `keywords`, `media_type`, `nasa_id`, `secondary_creator`, `title` (no `photographer` field), and `links[]` with `href`, `rel` (alternate/preview/canonical), `render`, `width`, `height`, `size`; `metadata.total_hits` = 133; `links[0]` rel "next" → page=2; first hit `PIA13523` "The Lunar South Pole", secondary_creator "NASA/GSFC/Arizona State University", center JPL; no api_key parameter was used — [images-api.nasa.gov search](https://images-api.nasa.gov/search?q=lunar%20south%20pole&media_type=image&page_size=3)
- Official API doc PDF sections: performing a search, errors/HTTP status codes, retrieving a media asset's manifest, metadata location, video captions, album contents; references Collection+JSON spec — [images.nasa.gov API docs PDF](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf) (text not extractable in this session)
- Suggested query strings (same endpoint, untested beyond the one above): `q=Artemis%20III`, `q=lunar%20terrain%20vehicle`, `q=Blue%20Moon%20lander`, `q=Blue%20Ghost`, `q=LRO%20south%20pole`, `q=Shackleton%20crater`; filter with `media_type=image`, `year_start`, `year_end`, `center` (parameters named in the task; parameter list not confirmed from the unreadable PDF)

**NASA media usage guidelines**
- NASA content "generally not subject to copyright in the United States"; may be used for educational/informational purposes including "textbooks, exhibits, simulations, websites"; credit "NASA should be acknowledged as the source of the material" — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- Commercial use must not "explicitly or implicitly suggest NASA endorsement"; NASA Insignia (Meatball), Logotype (Worm) and Seal are not public domain; images including logos may need clearance for cover art/promotion; merchandise via NASA Merchandise Guidelines — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- Third-party copyrighted material on NASA sites is marked with the holder's name and NASA's permission does not extend to others — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- Identifiable people: current astronauts/employees cannot appear in commercial products/ads; retired ones may grant permission but their NASA affiliation cannot promote a product; spacesuited astronauts can still trigger restrictions via name tags/context — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- AI clauses: insignia may not appear with AI-generated imagery; outputs should be attributed to the AI product, not NASA ("according to NASA" prohibited); NFTs: NASA does not want its materials used for NFTs — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
- Contacts: nasa-merchandise-&-brand-team@mail.nasa.gov; images 202‑358‑1900; video 202‑358‑0309 — [NASA media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)

**Data-provider credit lines**
- LROC products: credit "NASA/GSFC/Arizona State University", cite the relevant paper (e.g. Henriksen et al. 2023 for NAC ROI mosaics) — [LROC NAC_ROI_DEGERRIMLOC](https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_ROI_DEGERRIMLOC)
- ShadowCam: "NASA/KARI/ASU" (figure captions also "NASA/KARI/ASU/Intuitive Machines") — [ShadowCam news 1454](https://shadowcam.im-ldi.com/news/1454)
- USGS WAC mosaic: public domain, "Please cite authors" — [USGS Astropedia WAC mosaic](https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m)
- SVS CGI Moon Kit: credit "NASA's Scientific Visualization Studio" — [NASA SVS 4720](https://svs.gsfc.nasa.gov/4720)
- PGDA DEMs: cite Barker et al. 2021 (5 m) / Barker et al. 2023 (20 m suite, data DOI 10.60903/gsfcpgda-lola-spole) / Mazarico et al. 2011 (illumination) — [PGDA products/81](https://pgda.gsfc.nasa.gov/products/81); [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/); [PGDA products/69](https://pgda.gsfc.nasa.gov/products/69)
- Hemmi & Inoue SfS DTMs: CC BY 4.0 — [Zenodo 17153447](https://zenodo.org/records/17153447)

**ESA**
- ESA images/videos are copyrighted; some are CC BY‑SA 3.0 IGO; free use "for educational, editorial, or informational purposes" without separate authorisation, but "shall not be used for a commercial purpose" without written authorisation; credit format e.g. "Photo: ©ESA", "Image: ESA/NASA - SOHO/LASCO"; ESA logo protected (Paris Convention Art. 6ter), use requires written authorisation; no implied ESA endorsement of commercial products; third-party-credited images need the holder's approval; contacts spaceinimages@esa.int — [ESA image terms](https://www.esa.int/ESA_Multimedia/Terms_and_conditions_of_use_of_images_and_videos_available_on_the_esa_website)

**JAXA**
- JAXA materials may be used without permission for press, research, education or private purposes; business/commercial use requires prior permission; credit "Provided by Japan Aerospace Exploration Agency (JAXA)" or "Courtesy of JAXA" (short form "JAXA"); modification prohibited beyond what the credit needs (no cropping, colour changes, flipping); JAXA logo is a registered trademark; images of individuals/astronauts need permission — [JAXA site policy](https://global.jaxa.jp/policy.html)

**SpaceX**
- History: March 2015 Flickr launch under CC BY‑NC 2.0; changed to CC BY 2.0 Generic later in 2015; then Flickr added Public Domain Mark/CC0 options and SpaceX was among the first to switch; December 2019 report that SpaceX "quietly" moved official Flickr photos from CC0 to a CC 2.0 licence — [Techdirt 2015](https://archive.techdirt.com/articles/20150319/07030230368/spacex-photos-now-using-creative-commons-license-with-restrictions.shtml); [EFF 2015](https://eff.org/deeplinks/2015/04/not-just-space-photos-flickr-now-allows-all-users-expand-public-domain); [Gigazine 2019](https://gigazine.net/gsc_news/en/20191212-spacex-copyright-restrictions-photos)
- Current Flickr account page shows "1,486 Photos" but no licence text was visible in the fetched content; spacex.com/media page returned no licence text — [SpaceX Flickr](https://www.flickr.com/photos/spacex/); [SpaceX media](https://www.spacex.com/media/)

**Blue Origin / Firefly / others**
- blueorigin.com (gallery, terms-of-use, blue-moon pages) returned HTTP 429 on every attempt; a Getty listing of a Blue Origin facility photo is "Intended for editorial use" only — [Getty Blue Origin facility photo](https://www.gettyimages.com/detail/photo/blue-origin-rocket-engineering-facility-in-florida-royalty-free-image/1683847652)

### Inferences
- Safe landing-page imagery set: NASA-credited images from images-api.nasa.gov (check `secondary_creator`; if it names SpaceX, Blue Origin, Intuitive Machines, Firefly, Axiom, ESA or JAXA, treat as third-party copyrighted and seek their terms), PGDA/LROC data visualisations (credit NASA/GSFC/ASU), SVS renders (credit SVS). Avoid any image containing the NASA meatball/worm in a promotional context and any identifiable astronaut on a commercial page.
- Company renders of Blue Moon, Starship HLS, LTVs and CLPS landers are copyrighted by the companies even when hosted on nasa.gov; ESA and JAXA imagery is usable for an educational/informational site with the prescribed credit but not for a commercial product without permission.
- An "About" page should carry a consolidated credits block: NASA/GSFC/ASU (LROC), NASA/GSFC (LOLA, PGDA, Barker et al. 2021/2023, Mazarico et al. 2011), NASA SVS, USGS Astrogeology, NASA/KARI/ASU (ShadowCam), Hemmi & Inoue 2025 (CC BY 4.0), and "Cesium ion" logo if Cesium Moon is used.

### Gaps
- NASA image API parameter list and rate limits were not confirmed (PDF unreadable; api.nasa.gov page is JS-rendered). The live call succeeded without a key.
- Current SpaceX Flickr licence (2026) is unverified; the account page content did not expose licence tags.
- Blue Origin media terms not retrieved (HTTP 429). Firefly (Blue Ghost), Intuitive Machines, Lunar Outpost and Astrolab media terms not researched (search budget exhausted).

---

## Key question 5 — Web rendering: Three.js / CesiumJS approaches for DEM terrain, low-sun lighting, laptop-GPU performance; existing examples and what makes them look professional

### Takeaway
Two viable stacks: (a) Three.js with a DEM-driven mesh (16‑bit heightmap + precomputed normal map, since Three.js "can not recompute surface normals from the displaced vertices") and cascaded shadow maps (`SunLightShadow`, 2 cascades, 1024² default, or the `three-csm` library) tuned with tight shadow frusta and bias for grazing sun; or (b) CesiumJS / NASA-AMMOS 3DTilesRendererJS streaming Cesium Moon 3D Tiles (asset 2684829, `Ellipsoid.MOON`) for an LOD globe with real 1 m NAC imagery at the pole. What makes Cesium Moon look professional is real polar NAC imagery on 5 m LOLA terrain with a correct lunar ellipsoid and streaming LOD; no NASA Three.js+LOLA reference repo was found.

### Cited Findings

**Three.js material and shadow primitives**
- `displacementMap`: "the displaced vertices can cast shadows, block other objects, and otherwise act as real geometry… For best results, pair a displacement map with a matching normal map, since the renderer can not recompute surface normals from the displaced vertices"; `displacementScale` (black = none, white = max) and `displacementBias` are added to the scaled sample; `normalMap` "RGB values affect the surface normal for each pixel fragment"; `roughness` 1.0 = fully diffuse; `metalness` 0.0 for stone — [three.js MeshStandardMaterial](https://threejs.org/docs/pages/MeshStandardMaterial.html)
- `SunLightShadow` (addon `three/addons/lights/SunLightShadow.js`): shadow configuration for `SunLight` using two cascaded shadow maps fitted automatically to slices of the view frustum up to `camera.far`; adjacent cascades blend over a small depth range; default `mapSize` 1024×1024 per cascade; `getCamera(cascadeIndex)` returns each cascade's OrthographicCamera — [three.js SunLightShadow](https://threejs.org/docs/pages/SunLightShadow.html)
- `three-csm` library: CSMs "usually used for shadows cast by the sun over a large terrain", giving higher shadow resolution near the camera — [vtHawk/three-csm](https://github.com/vtHawk/three-csm); [StrandedKitty/three-csm](https://awesome.ecosyste.ms/projects/github.com%2Fstrandedkitty%2Fthree-csm)
- Forum guidance: tightening the shadow camera's near/far/left/right/top/bottom concentrates the shadow map resolution ("the tighter… the less area the shadow mapSize is distributed over") — [three.js discourse 48732](https://discourse.threejs.org/t/how-to-deal-with-choppy-shadows-light-bias-is-not-an-issue/48732); a heightmap-terrain CSM user hit stripes/acne, with an overly large shadow far plane causing precision issues and bias/normalBias tuning needed — [Babylon.js forum 54820](https://forum.babylonjs.com/t/terrain-self-shadow-with-cascadedshadowgenerator/54820)
- Shadow mapping on terrain "suffers from aliasing and self-shadowing artifacts", worse at low sun angles; a thesis proposes a dedicated heightmap sun-shadow method — [Boğaziçi thesis: shadow height maps](https://digitalarchive.library.bogazici.edu.tr/items/6570ac0f-836b-4afe-8c45-7739c3512246)
- Reusable heightmap demos for Three.js: meetar's "heightmap-demos" (not lunar-specific) — [meetar on GitHub](https://www.github.com/meetar); `dem2mesh` npm package converts DEMs to meshes — [dem2mesh](https://www.npmjs.com/package/dem2mesh)
- NASA GCAS tool uses JavaScript and three.js to display lunar terrain — [NASA TM‑20230016076](https://ntrs.nasa.gov/api/citations/20230016076/downloads/TM-20230016076.pdf)

**3D Tiles in Three.js (NASA-AMMOS)**
- 3DTilesRendererJS: 3D Tiles renderer on Three.js (also Babylon.js, r3f); Apache‑2.0; examples include "Cesium Ion Lunar: Lunar surface tiles" and "Cesium Ion Mars" (need a Cesium ion API key), "Offscreen Shadows", TMS/XYZ, WMTS, WMS and Quantized Mesh plugins; LRU cache `maxSize`/`maxBytesSize` are hard caps (monitor `lruCache.isFull()`, raise `errorTarget` if needed) — [NASA-AMMOS/3DTilesRendererJS](https://github.com/NASA-AMMOS/3DTilesRendererJS)

**CesiumJS**
- Loading recipe: `Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON; new Cesium.Viewer(..., {globe:false, sceneModePicker:false, baseLayerPicker:false, geocoder:false}); Cesium3DTileset.fromIonAssetId(2684829)`; 2D/Columbus views, imagery layers and geocoder unsupported for the Moon — [Cesium Moon product page](https://cesium.com/platform/cesium-ion/content/cesium-moon/)
- Cesium engines were updated to support non‑WGS84 ellipsoids "so the lunar surface is represented accurately for analysis and measurement"; used by NASA's Advanced Operations Concept Lab (XOSS) and Ansys STK for lunar polar comms analysis; demonstrated at JPL's Digital Twin for Lunar Development Workshop — [Cesium blog 2024‑08‑06](https://cesium.com/blog/2024/08/06/introducing-cesium-moon-terrain/)
- Known issue: ~2.5 km vertical offset vs LOLA reported, unresolved in the thread — [Cesium community thread](https://community.cesium.com/t/cesium-ion-moon-terrain-appears-2-5-km-higher-than-lola-sldem2015-dem-at-the-same-lon-lat/46282)

**Existing examples**
- NASA Eyes on the Solar System: 2013 version used the Unity engine with a browser plug-in; a 2022 browser version and a WebGL "orrery" exist; engine name/open-source status not confirmed — [Manufacturing.net 2013](https://www.manufacturing.net/home/news/13085487/nasa-gives-public-new-internet-tool-to-explore-the-solar-system); [Vatican Observatory on the WebGL orrery](https://www.vaticanobservatory.org/sacred-space-astronomy/nasas-new-web-based-solar-system-orrery)
- Cesium Moon polar tiers: 1 m NAC imagery 85.5–90°, 5 m terrain 87.5–90°, 10 m 85–90°, 20 m 80–90° — [Cesium Moon product page](https://cesium.com/platform/cesium-ion/content/cesium-moon/)
- Hobby Three.js south-pole map uses a synthesized 256×256 terrain grid "so it runs offline" — [Stardance project 2554](https://stardance.hackclub.com/projects/2554)

**Physical lighting reference**
- LOLA illumination modelling treats the Sun as a finite disc and steps hourly over an 18.6‑year nutation cycle; PSR = never lit; products at 60–240 m and PSR polygons at 20 m — [PGDA products/69](https://pgda.gsfc.nasa.gov/products/69); [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)
- PGDA 20 m hillshade uses 45° altitude / 45° azimuth — unrealistic for the pole (real sun elevation is a few degrees), so it is a shading aid, not a lighting ground truth — [PGDA products/90](https://pgda.gsfc.nasa.gov/products/90/)

### Inferences
- Three.js recipe for the 20 km site (synthesised from the sourced primitives): (1) crop DEM → 16‑bit PNG (KQ1); (2) precompute a tangent-space normal map from the DEM offline (GDAL/numpy) because Three.js cannot recompute normals after displacement; (3) `PlaneGeometry` with 1–2 vertices per heightmap pixel (e.g. 1024² segments ≈ 1 M vertices, fine for laptop GPUs) or a quadtree of tiles with the 5 m detail only near the lander; (4) `MeshStandardMaterial` with `displacementMap`, `normalMap`, `roughness≈1`, `metalness=0`, albedo from the NAC mosaic or a constant regolith grey; (5) `SunLight` + `SunLightShadow` (or `three-csm`) with a tight shadow far plane, `normalBias`, and 2048–4096² maps for the near cascade; (6) sun azimuth/elevation from an ephemeris (e.g. an astronomy library) to drive the near-horizontal sun; (7) validate against the PGDA average-illumination/PSR rasters (Shackleton floor must stay dark).
- At grazing sun angles the terrain is largely self-shadowed; a per-pixel horizon/shadow map precomputed from the DEM for a set of sun azimuths (as the thesis suggests) or a ray-marched height-field shadow in a custom shader will beat shadow maps for the far field; use shadow maps only for the lander/rover and near terrain.
- Alternative "pro" path: 3DTilesRendererJS + Cesium Moon inside Three.js gives streaming LOD and real NAC texture while keeping Three.js lighting, at the cost of Cesium ion terms (logo, no offline) and the free-tier 15 GB/month streaming cap.
- What makes NASA/Cesium visuals read as professional: real high-resolution imagery at the pole (1 m NAC), correct body ellipsoid and coordinate frame, continuous LOD without seams, physically plausible low-sun lighting with long shadows, and credited data provenance in-app.

### Gaps
- No open-source Three.js project rendering real LOLA polar tiles was found (results were hobby demos with synthesized terrain). Moon Trek's own 3D engine was not identified (search budget exhausted before the query ran).
- `SunLightShadow` introduction version and extra options are not on the doc page; check `examples/jsm/lights/SunLightShadow.js` in the installed three.js version.
- Cesium's attribution guide and whether NASA/USGS credits must be shown on-screen (beyond the Cesium ion logo) were not confirmed.
