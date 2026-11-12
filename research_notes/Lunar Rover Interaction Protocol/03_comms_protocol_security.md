# Lunar Rover Interaction Protocol, part 3: communication, the protocol itself, reliability and security

Research note for Phase 6 (sections 4, 5 and 7 of the owner's question list). Written 11 November 2026.
Positioning and time, maps, and coordination and market are in the other notes of this folder and are not
repeated here.

How to read the flags. A number is followed by a source key in square brackets; the keys are listed in
section G with the document number, year and URL. Only sources opened in this session are cited. **UNVERIFIED**
marks a claim whose source could not be opened, with what was tried. **Computed** marks our own arithmetic
(scripts kept outside the repository; every formula is written out in section E so it can be re-run).
**Project** marks a number taken from the repository (`research_notes/Lunar ATC/vehicles_comms_internals.md`,
`data/scenarios/E48-design.json`, `lunarsim/atc/`).

---

## A. Summary in plain language (the 12 answers)

**Communication**

1. **Which channels?** Near the base, Wi-Fi 6 and 4G/LTE (both named in CCSDS 883.0-B-2, May 2024); everywhere,
   a narrow-band UHF or S-band channel; upward, S and Ka band to a relay satellite and X band straight to Earth
   when Earth is above the horizon; between rovers, mesh relaying on the same radios. No cellular rate or range
   has been measured on the Moon: Nokia's network on IM-2 (March 2025) ran for 25 minutes and never connected a
   device. UHF is barred on the far side, which is kept quiet for radio astronomy.
2. **Behind a hill?** The link is lost, not weakened: a ridge in the path costs 6 to 20 dB and more, and low antennas
   already lose signal with the fourth power of distance on flat ground. The remedies are geometric: relay
   through a rover, mast or dropped node that sees both sides, fall back to UHF, or store the message and
   deliver it later.
3. **Latency and dropouts?** Delay-tolerant networking (Bundle Protocol version 7, RFC 9171): each node stores
   a message until the next hop is reachable. LunaNet requires it, NASA has run it as an operational service
   since January 2026, and CAPSTONE flew it in lunar orbit. It costs about 48 bytes per bundle, so it carries
   what must arrive, not the once-a-second beacon.
4. **Existing standards?** The layers below the application are covered: CCSDS Proximity-1 (211.x), Space
   Packet (133.0), AOS (732.0), USLP (732.1), link security (355.0, 355.1), file delivery (727.0), Bundle
   Protocol (734.x), surface wireless (883.0), and the LunaNet Interoperability Specification version 5 (29
   January 2025). None defines what two rovers of different owners say to each other; that is the gap this
   protocol fills.

**The protocol**

5. **Message types?** Eight are enough: POSITION, STATUS, INTENT, ALERT, TASK (announce, bid, award, state),
   RESERVE (request, grant, release), CAPABILITY (query, manifest) and MAP_NOTICE, plus a HELLO heartbeat.
   Fields, units and bit widths are in section C.
6. **Publish/subscribe or request/response?** Both. State that is refreshed anyway (position, status, alerts)
   is published to whoever listens; anything that gives a right (a task, a road reservation) is a request with
   a signed answer and a timeout. ROS 2 on DDS is too chatty for a narrow shared radio, Zenoh or MQTT-SN fit
   better, and only the Bundle Protocol survives long outages.
7. **Describing capabilities?** Each rover publishes a small signed manifest: identity, size and limits,
   radios, navigation accuracy, the message versions it speaks, and a list of named, versioned capabilities
   with typed parameters. This is the idea behind tool descriptions in the Model Context Protocol and the
   VDA 5050 factsheet for factory robots. A manifest is about 1.2 kB as JSON and about 250 bytes in compact
   binary.
8. **Different manufacturers?** One published schema, a version in every message, a rule that unknown fields
   are skipped and numbers never reused, and a public conformance test before a vehicle is admitted. VDA 5050
   (version 3.0.0, March 2026) is the closest working precedent.
9. **Minimum message size?** A position report is 13 bytes of content and 41 bytes on the air with a packet
   header, our header, a counter and an 8-byte authentication code (49 with a 16-byte code). Twenty rovers at
   once a second need 6.6 kbit/s; at ten times a second 66 kbit/s. The earlier guess (100 B/s per robot,
   16 kbit/s for 20) holds at 1 Hz and one hop; it fails at 10 Hz, with random channel access, or when every
   message is relayed twice.

**Reliability and security**

10. **Spoofing and interference?** Every message carries a counter and a keyed authentication code, so forged
    and replayed messages are rejected; a forged 8-byte code passes with probability 5 x 10^-20. Each owner
    holds a certificate signed by the base, and awards, grants and manifests are signed. Jamming cannot be
    stopped by cryptography, only survived: two bands, a narrow-band fallback, and the behaviour of answer 12.
11. **Wrong position from another rover?** Compare the report with your own range or bearing to that rover: if
    the normalised squared difference exceeds the chi-square threshold (10.8 for a range, 13.8 for range and
    bearing) on 3 of the last 5 reports, treat the rover as non-conforming and tell the others. Where many
    rovers must agree on a value, each drops the F highest and F lowest values it hears before averaging
    (W-MSR), which needs at least 2F + 1 neighbours.
12. **Total loss of communication?** A fixed, published ladder: finish the reserved stretch, stop at a safe
    point and hold for 10 minutes, go back to where the link last worked, after 1 hour go to a pre-agreed
    meeting point, then safe mode with a beacon; the others keep the silent rover's space blocked. It is the
    lost-link rule of uncrewed aircraft and the radio-failure rule of instrument flight: do what the others
    expect.

---

## B. Evidence per question

### Q1. Which channels can realistically be used?

**Direct answer.** Use two surface radios on every rover (a broadband one near the base and a narrow-band UHF
or S-band one everywhere), a mast or relay rover at the base, an orbital relay for the 14 days a month when
Earth is below the horizon, and X-band direct to Earth otherwise. Spectrum is not free to choose: the SFCG
recommendation lists the surface bands and the far side is protected for radio astronomy.

**Table B1. Channels (frequency, rate, range, status as of 11 November 2026).**

| Channel | Frequency | Data rate | Range | Status and source |
|---|---|---|---|---|
| UHF proximity (CCSDS Proximity-1) | forward 435-450 MHz, return 390-405 MHz; hailing channel 1 = 435.6 / 404.4 MHz | coded symbol rates 1, 2, 4 ... 4,096 ksps (powers of two) | built for orbiter to surface; on the surface limited by the horizon (Table E1) | Blue books in force: 211.1-B-4 (Dec 2013), 211.0-B-6 (Jul 2020), 211.2-B-3 (Oct 2019) [P1-PHY][P1-DLL][P1-CS]. Revisions 211.0-P-6.2, 211.1-P-4.2, 211.2-P-3.2 and a new 235.1 session-control book were listed as under agency review on 11 Nov 2026 [CCSDS-WEB]. LNIS v5 says Proximity-1 "is currently being updated from the original UHF band and Mars application to S-band and K-band" [LNIS5 §4.1] |
| Surface UHF (SFCG surface list) | 390-405, 410-420 (EVA), 435-450 MHz | narrow-band; not specified | horizon-limited | Recommended in SFCG REC 32-2R5 (June 2023) as quoted in [SFCG24] and CCSDS 883.0-B-2 Table 3-3 [WPN]. 390-405 and 435-450 MHz only outside the shielded zone of the Moon [SFCG24 note 3] |
| S-band proximity to a relay (LunaNet) | forward 2025-2110 MHz, return 2200-2290 MHz | 0.5 ksps to 5 Msps (LNIS Table 7) | surface to orbit | LNIS v5, 29 Jan 2025 [LNIS5]; rates as quoted in the Project note §2.1. NASA's reference relay design asks for 50 bit/s to 100 kbit/s S-band with ranging [ESPER25] |
| K/Ka-band proximity to a relay | forward 23.15-23.55 GHz, return 27.0-27.5 GHz | from 1 Msps, upper bound "TBD" [LNIS5]; reference relay: 10 Mbit/s to the surface, 50 Mbit/s from it [ESPER25] | surface to orbit, needs a pointed antenna | LNIS v5 [LNIS5]; DRM-0 reference requirements [ESPER25] |
| Wi-Fi 6 (IEEE 802.11ax) | 2.400-2.480 GHz and 5.15-5.835 GHz on the lunar surface | 802.11ax "capable of 9.6 Gb/s" at the PHY [WPN §2]; no lunar measurement | about 300 m in NASA's surface-relay concept [LSR23] | CCSDS 883.0-B-2 (May 2024): "Infrastructure shall be compliant with Wi-Fi CERTIFIED 6" (§3.3.2.1) [WPN]. LNIS v5 lists "IP over Wi-Fi" as LunaNet 1.0: No [LNIS5 Table 3] |
| 3GPP 4G/LTE, later 5G | SFCG surface bands 2.5035-2.655, 3.5-3.8, 5.15-5.835, 5.855-5.925 GHz, 25.25-25.5, 27.225-27.5, 27.5-28.35 GHz [SFCG24] | not measured on the Moon | 10 km from a 10 m mast "depending on local terrain" [LSR23]; 6.8-22 km free-space range for a 30 dBm, 0 dBi small-lander budget depending on band [LUNARRF] | CCSDS 883.0-B-2: "shall be compliant with 3GPP LTE Rel-12" (§3.4.1.2) [WPN]. LNIS v5: LS3 "3GPP rel. 16 (and higher) (LTE and 5G TBD)", not a LunaNet 1.0 item, bands "under investigation" [LNIS5]. WRC-27 agenda item 1.15 studies 2,400-2,690, 3,500-3,800, 5,150-5,925 MHz and 25.25-28.35 GHz [SFCG26] |
| Nokia LTE on IM-2 | 1.8 GHz (3GPP Band 3) per [LUNARRF] | none measured | none measured | Landed 6 Mar 2025. "The NIB ran without any service interruption for the entire 25-minute power window"; base station, radio and core reported "on-air"; the hopper's device module had cooled "well below operational range" and "a connection ... could no longer be established"; no call [NOKIA25, 10 Mar 2025]. The 1.8 GHz band is "outside the SFCG surface allocations" [LUNARRF] |
| Mesh between rovers | whatever surface radio is carried | traffic of a two-rover convoy controller: 13.8 kB/s on 2.4 GHz Wi-Fi (Project, Krawciw et al.) | one hop each; hop count as in `lunarsim/atc/radio.py` | CADRE (three rovers, flight on IM-3) uses a "mesh communication protocol between rovers, lander with a TCP-IP interface" [CADRE-AAMAS as summarised by search; slide deck not read page by page: UNVERIFIED wording]; leader re-election within 10 s [CADRE25] |
| Orbital relay: Lunar Pathfinder (ESA/SSTL) | S-band to lunar users, X-band to Earth | "2 x 2.7 Mbps S-band", "5 Mbps X-band" [SSTL24] | elliptical frozen orbit over the south | Not launched. "NET 2027" on Blue Ghost Mission 2; "In October 2026, the spacecraft was undergoing final environmental test campaign" [WIKI-LP, edit of 14 Oct 2026]. A UHF user channel is in the Project note; not confirmed in the text we could extract from [SSTL24]: UNVERIFIED |
| Orbital relay: LCRNS (NASA, commercial; Intuitive Machines) | S and Ka proximity as above; PNT signal at 2483.5-2500 MHz | reference: 10 / 50 Mbit/s Ka, up to 100 kbit/s S [ESPER25] | one relay covers the south pole 41 % of the time in the reference orbit; three give 100 % [ESPER25] | First satellite rides IM-3; NASA calls it "a commercial lunar relay, now in development" [NASA-DTN, page updated 15 Oct 2026]. Launch slipped to early 2027 (Project note; trackers, Medium) |
| Orbital relay: Queqiao-2 (China) | X-band to the surface (10 channels each way), S and Ka to Earth | Ka 100 Mbit/s average; S-band up to 6 Mbit/s as backup; surface uplink 50 kbit/s (omni) or 5 Mbit/s (dish) | 254 x 16,941 km orbit, 4.2 m dish | Launched 20 Mar 2024, operating [WIKI-QQ2, Medium]. Chang'e-7, which it is to serve at the south pole, was delayed from August 2026 to 2027 [SCIAM-CE7, update of 24 Aug 2026] |
| ESA Moonlight | not given | not given | "prioritise coverage of the lunar south pole" | "initial operations by the end of 2028 and full operations by 2030"; one communication and four navigation satellites [ESA-ML, 15 Oct 2024] |
| Direct to Earth | X-band 7190-7235 MHz up, 8450-8500 MHz down; Ka for high rate | VIPER design: up to 8 Msps down (Project) | Earth-Moon | Earth is below the horizon at the pole "nominally for 14 days every month" [LSR23]; yearly availability 17-43 % direct, 80-86 % with one relay, 100 % with two (Project note, from Esper 2025) |

**Spectrum rules that constrain the design.**

- The surface list of SFCG REC 32-2R5 is: 390-405 MHz, 410-420 MHz, 435-450 MHz, 2.4-2.48 GHz, 2.5035-2.655
  GHz, 3.5-3.8 GHz, 5.15-5.835 GHz, 5.855-5.925 GHz, 25.25-25.50 GHz, 27.225-27.5 GHz, 27.5-28.35 GHz, and
  67-70 GHz under study [SFCG24].
- The 2483.5-2500 MHz band is kept for lunar navigation signals. Surface radios at 2.4-2.48 and 2.5035-2.62
  GHz need "sufficient OOB filtering" to protect it [WPN Table 3-3]; SFCG REC 43-1 (2024) sets the limit
  [SFCG25].
- The shielded zone of the Moon (the far side, out of sight of anything within 100,000 km of Earth's centre) is
  protected by Radio Regulations 22.22-22.25; ITU-R RA.479-5 "recommends that frequencies below 2 GHz be
  reserved for the use of radio astronomy systems in the SZM" [SFCG25]. The UHF fallback is therefore a
  near-side and polar tool only.
- SFCG REC 41-1: lunar links with occupied bandwidth under 6 MHz may use S, X or Ka band; wider links "should
  use Ka-band only" [SFCG24 note 6]. A narrow coordination channel fits this rule; video does not.
- Frequencies are pre-coordinated through the NASA Lunar Spectrum Manager under SFCG RES A40-1 (2022) [SFCG25].
- New allocations for lunar links are on the agenda of the World Radiocommunication Conference 2027 (item
  1.15); the bands under study are 390-406.1, 420-430, 440-450 MHz (outside the shielded zone), 2,400-2,690,
  3,500-3,800, 5,150-5,570, 5,570-5,725, 5,775-5,925, 7,190-7,235, 8,450-8,500 MHz and 25.25-28.35 GHz [SFCG26,
  February 2026]. Until then the surface bands are recommendations, not allocations.

### Q2. What happens behind a hill?

**Direct answer.** The direct link is lost in a step, over tens of metres of travel. The protocol must treat
loss of line of sight as normal: route through a neighbour, a mast or a dropped relay; fall back to UHF; and
store and forward what is not urgent.

**Evidence.**

- *Horizon.* On a smooth Moon of radius 1,737.4 km a 4 m mast and a 1.5 m receiver see each other to 6.0 km
  (3.7 + 2.3 km) [LUNARRF]; our own table gives 2.64 km for two 0.5 m antennas and 5.27 km for two 2 m
  antennas (Table E1, Computed; same formula as the Project note).
- *Flat-ground loss at low antenna height.* NASA JSC modelled lunar surface propagation with the geometrical
  theory of diffraction, at 401 MHz and 2.1 GHz, antenna heights 2, 6 and 10 m, ground permittivity 3 and
  conductivity 10^-11 to 10^-1 S/m. Findings: at short range loss follows 1/R^2 with peaks and nulls; at long
  range "path loss increases in proportion to 1/R^4" because the reflection coefficient approaches -1 at
  grazing incidence; at 401 MHz and 2 m height the loss is 10 dB above free space at 200 m; beyond about 180 m
  "the path loss is independent of frequencies"; higher antennas lose less [HWU08]. This is the two-ray model
  of section E1, confirmed for lunar ground by a NASA study.
- *Regolith properties.* The south-pole regolith "has yet to be directly sampled". For the highlands simulant
  NU-LHT-2M NASA Glenn measured real permittivity 2.75 (standard deviation 0.115) and loss tangent 0.047
  (0.015) at 50 MHz, room temperature; models give 2.8 to 3.3 [GRC23]. The 2026 coverage atlas uses 3.7 and
  0.01 [LUNARRF]. The sweep for the simulator is therefore 2.7 to 3.7.
- *Terrain diffraction and coverage.* A GPU study of the whole area south of 80 deg S (20 m cells, 11,827
  candidate 4 m masts, ITU-R P.1812 Delta-Bullington diffraction, 30 dBm, 0 dBi, 1.5 m receivers) finds a mast
  covers "about 90 % of its visible area within its budget-set range"; with every candidate mast active 90.5 %
  of the disc is coverable at 1.8 GHz, 59 % at 5.855 GHz and 10 % at 25.375 GHz (84, 43 and 5 % after a measured
  3-4 dB optimism); free-space ranges for that budget are 22.0, 15.4, 10.9, 6.8 and 1.6 km at 1.8, 2.58, 3.65,
  5.855 and 25.375 GHz [LUNARRF, preprint of 19 October 2026, not yet peer reviewed]. NASA's earlier
  single-tower study found 10.6-23.7 % of a 20 x 20 km Malapert area in view of a 4 m tower [LSR23, Project].
  The two results agree: one mast covers a small share; coverage comes from many relay points.
- *Knife-edge loss.* 6 dB at grazing, 13.9 dB when the ridge is one Fresnel-parameter unit into the path,
  20.5 dB at 2.4 units (ITU-R P.526, Project note §2.5). At 0.4 GHz the first Fresnel zone at 1 km is 13.7 m
  wide against 5.6 m at 2.4 GHz (Project note), so the same ridge is a smaller obstacle at UHF.
- *Measurements.* No published in-situ measurement of rover-height surface-to-surface path loss at the lunar
  south pole was found. IM-2 would have been the first at 1.8 GHz; it returned none [NOKIA25]. All numbers
  above are models. This is the largest physical uncertainty in the radio layer.
- *Relay options.* Other rovers (the Project's mesh: hop counts from `RadioMesh.hops`); the 10 m base mast; a
  mobile relay on a VIPER-class chassis, 0.8 km/h, 100 km per lunar day [LSR23, Project]; hoppers as temporary
  high points. No flown example of a dropped relay node on the Moon was found in the sources opened.
- *Store and forward.* See Q3. The DTN node on each rover holds bundles until a neighbour or the mast is in
  view; CAPSTONE showed exactly this behaviour in lunar orbit ("The spacecraft stored the remaining data until
  the next communications opportunity, and transmission resumed automatically") [NASA-CAP].

### Q3. Latency and link dropouts

**Direct answer.** Split the traffic in two. Beacons that are worthless after a second go out unacknowledged
on the local radio and are never queued. Everything that must arrive (awards, grants, ledger entries, alerts,
map notices, logs for Earth) is wrapped in a Bundle Protocol version 7 bundle with a lifetime and, where
needed, custody transfer, and is carried over whatever link exists.

**Evidence.**

| Item | Fact | Source |
|---|---|---|
| Bundle Protocol v7 | RFC 9171, January 2022. Primary block is a CBOR array of 8 to 11 items; times are milliseconds since 2000-01-01; a bundle is dropped when its age exceeds its lifetime; a clock-less node may use time 0 with a Bundle Age block | [RFC9171] |
| Custody | Not in RFC 9171 itself (moved to bundle-in-bundle encapsulation). CCSDS defines custody transfer and compressed status reporting as extensions (orange books "expected to be published in 2025"); NASA's bplib "follows the CCSDS Compressed Bundle Status Reporting and Custody Signaling Orange Book" | [RFC9171 App.][LNIS5 §3.1.2][BPLIB] |
| Security | BPSec, RFC 9172: integrity block (BIB) and confidentiality block (BCB). Default contexts, RFC 9173: HMAC-SHA2 (default variant 384) and AES-GCM (default 256-bit key) | [RFC9172][RFC9173] |
| Convergence layers | TCP (RFC 9174), UDP, LTP (RFC 5326; CCSDS 734.1-B-1, May 2015), CCSDS Encapsulation Packets over AOS or USLP | [LNIS5 Table 4][RFC9174][RFC5326][LTP-C] |
| CCSDS BP book | CCSDS 734.2-B-1 (September 2015) is a profile of RFC 5050, i.e. BP version 6. LNIS v5 cites the draft "CCSDS 734.2-P-1.1x ... to be published as CCSDS 734.2-B-2" for version 7. We could not find 734.2-B-2 on the CCSDS server on 11 Nov 2026 (tried `public.ccsds.org/Pubs/734x2b2.pdf` and the blue-book listing): publication UNVERIFIED | [BP6][LNIS5] |
| LunaNet choice | "The Bundle Protocol version 7 (BPv7) shall be used"; on surface IP networks bundles ride on TCP or UDP; routing "based on pre-scheduled links" | [LNIS5 §3.1.2] |
| Routing | Contact graph routing over a contact plan: CCSDS 734.3-B-1, Schedule-Aware Bundle Routing, July 2019 | [SABR] |
| Implementations | ION (JPL; BP, LTP, CFDP, AMS in one package) [ION]; HDTN (NASA Glenn; C++, BPv6 and BPv7, LTP, TCPCL v3 and v4) [HDTN]; bplib with the cFS application BPNode (NASA Goddard; BPv7, custody, fixed memory pool) [BPLIB]; uD3TN (D3TN, "space-tested", POSIX) [UD3TN] | READMEs opened 11 Nov 2026 |
| PACE | "In 2024, NASA's PACE mission became the first NASA Class-B mission to use DTN operationally"; "Over 34 million bundles ... with a 100% success rate" | [NASA-DTN] |
| NASA networks | DTN "is now an operational service in both NASA's Near Space Network and the Deep Space Network" (January 2026) | [NASA-DTN] |
| ISS and LCRD | Two HDTN nodes on the ISS reached the ground through the ILLUMA-T laser terminal and LCRD (above 1 Gbit/s), across four network areas, with BPSec | [HYLTON24] |
| CAPSTONE (lunar orbit) | Extended mission ended June 2026. "CAPSTONE became the first to fly the latest DTN protocols beyond Earth orbit" and "the first to run them in NASA's core Flight System". BPv7 with CCSDS custody transfer; BPNode "scaled down to link rates as low as 2 Kbps" (abstract as summarised; full paper not read) | [NASA-CAP, 6 Jul 2026][SMALLSAT26] |
| Other lunar tests | Korea's KPLO carried a DTN payload (Project note, Medium). ESA, NASA, Morehead State and D3TN ran an emulated Lunar IceCube experiment with bplib, ION and uD3TN | [DUDUKOVICH25] |
| Lunar surface | No DTN demonstration on the lunar surface was found as of 11 November 2026 | search, this session |
| 3GPP | Release 19 studies "Store and Forward (S&F) Satellite operation for delay-tolerant communication service" | [3GPP-NTN] |

**Cost of a bundle (Computed, section E7).** Primary block 39 bytes (node numbers 200 and 291, CRC-16),
payload block header 7 bytes, array framing 2 bytes: 48 bytes of overhead. A BPSec integrity block with a
32-byte HMAC-SHA-256 result adds 60 bytes. A 27-byte position packet becomes 75 bytes in a bundle and 135 bytes
with BPSec. That is why the 1 Hz beacon does not use bundles.

**Latency figures to model.** Earth round trip 2.6 s of light time plus 2.4 s processing (Project). Surface hop
10 ms (Project, Assumed). DTN adds the wait for the next contact, which is minutes to hours behind terrain and
up to about 14 days for Earth without a relay.

### Q4. What standards already exist?

**Direct answer.** The stack below the application is standardised and should be reused unchanged. Table B2
lists each book as opened, with issue and date.

**Table B2. Standards by layer.**

| Layer | Standard (number, issue, date) | What it fixes | Source |
|---|---|---|---|
| Physical, proximity | CCSDS 211.1-B-4, Proximity-1 Physical Layer, Dec 2013 | UHF 435-450 / 390-405 MHz, 8 channels, hailing on channel 1, rates 1 to 4,096 ksps | [P1-PHY] |
| Coding | CCSDS 211.2-B-3, Proximity-1 Coding and Synchronization, Oct 2019 | 24-bit sync marker FAF320, CRC-32 per frame | [P1-CS] |
| Coding | CCSDS 131.0-B-5, TM Synchronization and Channel Coding, Sep 2023 | codes for AOS/USLP links; LNIS uses its LDPC options | [TMSC][LNIS5] |
| Link | CCSDS 211.0-B-6, Proximity-1 Data Link Layer, Jul 2020 | 5-byte frame header, frames up to 2,048 bytes, hailing, go-back-N ARQ | [P1-DLL] |
| Link | CCSDS 732.0-B-4, AOS Space Data Link Protocol, Oct 2021 | fixed-length frames, virtual channels | [AOS] |
| Link | CCSDS 732.1-B-3, Unified Space Data Link Protocol, Jun 2024 | variable frames, primary header 4 to 14 bytes, can run over the Proximity-1 coding sublayer | [USLP] |
| Link security | CCSDS 355.0-B-2, Space Data Link Security, Jul 2022 | security header (16-bit SPI, IV, sequence number) and trailer (MAC) on TM, TC, AOS and USLP frames | [SDLS] |
| Key management | CCSDS 355.1-B-1, SDLS Extended Procedures, Feb 2020 | over-the-air rekeying (OTAR), key verification, key states, master and session keys | [SDLS-EP] |
| Algorithms | CCSDS 352.0-B-2, Cryptographic Algorithms, Aug 2019 | AES-GCM, AES-CMAC, HMAC-SHA-256; RSA and ECDSA signatures | [CRYPTO] |
| Packet | CCSDS 133.0-B-2, Space Packet Protocol, Jun 2020 | 6-byte primary header, 11-bit APID, packets of 7 to 65,542 bytes | [SPP] |
| File transfer | CCSDS 727.0-B-5, CFDP, Jul 2020 | Class 1 unreliable and Class 2 reliable file delivery | [CFDP] |
| Network (DTN) | CCSDS 734.2-B-1 (Sep 2015, BPv6); RFC 9171 (BPv7); CCSDS 734.1-B-1 LTP (May 2015); CCSDS 734.3-B-1 routing (Jul 2019) | store and forward, custody, contact plans | [BP6][RFC9171][LTP-C][SABR] |
| Surface wireless | CCSDS 883.0-B-2, High Data Rate Wireless Proximity Network Communications, May 2024 | Wi-Fi 6 and WPA3; LTE Release 12 with roaming between agencies' cores; lunar frequency tables | [WPN] |
| Data description | CCSDS 660.0-B-2, XTCE version 1.2, Feb 2020; CCSDS 876.0-B-1, SOIS electronic data sheets, Apr 2019 | XML descriptions of telemetry, commands and device interfaces | [XTCE][SEDS] |
| System | LunaNet Interoperability Specification, LNIS V005, 29 January 2025 (version 4 was 12 September 2022) | see below | [LNIS5] |
| Cellular in space | 3GPP non-terrestrial networks: Release 17 (frozen June 2022) first normative; Release 18 added bands; Release 19 adds regenerative payloads and store and forward | Earth-orbit satellites; the UE "shall autonomously pre-compensate the Timing Advance, as well as the frequency Doppler shift" | [3GPP-NTN] |
| Human spaceflight | International Communication System Interoperability Standards (ICSIS), one of nine deep-space interoperability standards | Gateway-era link standards between agencies | [ICSIS] |

**What LNIS v5 fixes, layer by layer** [LNIS5].

- *Frequencies:* S-band for proximity only, X-band for direct with Earth, K/Ka for high rate; surface cellular
  bands "under investigation".
- *Link:* AOS and USLP with Encapsulation Packets; IP over CCSDS (702.1-B-1).
- *Network:* IPv4, IPv6 and BPv7. "Sub-IP" surface details "must be bilaterally defined" (Project note §2.1).
- *Security:* the security specification is still "LNIS-TBD-AD0008"; the security section "is considered
  informational".
- *Messaging:* provider-to-user messages only (almanac, alerts, space weather, search and rescue: the MSG-G
  series); "The specific standards for messaging are still being determined". Nothing covers one user's rover
  talking to another user's rover.
- *Not in LunaNet 1.0:* IP over Wi-Fi, IP over 3GPP, optical links.
- A version 6 was not found; a February 2026 workshop deck gave a public release of applicable document 5
  (reference system and time) for November 2026, not confirmed (search, this session).

**IOAG.** LNIS v5 cites the IOAG "Future Lunar Communication Architecture" (final version 1.3, 31 January 2022)
[LNIS5]. The IOAG PDF itself did not download (the server returned an HTML page): content UNVERIFIED.

### Q5. Message types

**Direct answer.** The minimal set is in section C2 (catalogue) with a field table for each message. The
choice follows three working precedents:

- *VDA 5050 version 3.0.0* (factory robots of mixed vendors; released by VDA on 19 March 2026): topics
  `order`, `instantActions`, `state`, `visualization`, `connection`, `factsheet`, `zoneSet`, `responses`
  [VDA5050]. Our POSITION is its `visualization`, STATUS its `state`, TASK its `order`, CAPABILITY its
  `factsheet`, HELLO its `connection`.
- *MassRobotics AMR Interoperability Standard:* two messages only, `identityReport` (required: uuid,
  timestamp, manufacturer, model, serial, envelope) and `statusReport` (required: uuid, timestamp,
  operationalState, location; optional velocity, batteryPercentage, remainingRunTime,
  loadPercentageStillAvailable, errorCodes, destinations, path) [MASSROB]. This is the smallest set anyone has
  agreed across manufacturers; ours is a superset.
- *The project's own traffic model* (E48): status, reservation_request, grant, release, bid, award, claim,
  landing_announcement, ledger_entry (Project). All nine map onto the catalogue.

### Q6. Publish/subscribe, request/response, or both?

**Direct answer.** Both, with a strict split by content. State that is periodically refreshed is published
without acknowledgement (latest value wins). Anything that changes who may be where, or who does what, is a
request with a signed response and a timeout. The radio profile decides the middleware; the message schema
does not depend on it.

**Table B3. Middleware compared.**

| Option | Pattern | Overhead and discovery | Works over DTN? | Evidence |
|---|---|---|---|---|
| ROS 2 on DDS (RTPS) | pub/sub, services, actions | RTPS header: "RTPS" + version + vendor + 12-byte GUID prefix = 20 bytes before any submessage; every participant announces itself to all others, by default every 30 s ("SPDPbuiltinParticipantWriter.resendPeriod = {30, 0}"), and endpoint discovery grows with participants x topics | No. Needs a live, low-delay path and multicast or a discovery server | [RTPS §9.4.4, §9.6] |
| Zenoh (and rmw_zenoh for ROS 2) | pub/sub, queries (request/response), storage | "minimal wire overhead of 5 bytes" per data message; Zenoh "overhead in the wire is 98%, 75% and 64% smaller when compared to OPC-UA, XRCE-DDS and MQTT" (vendor figures); replaced DDS discovery with "97% to 99,9% traffic reduction in tested scenarios" (vendor post, 23 March 2021) | Not natively; runs over TCP, UDP, serial; a store can bridge gaps | [ZENOH-PICO][ROS-DISC21] |
| Zenoh benchmark | | Single machine, 8-byte payload: Zenoh peer mode above 4 M msg/s, Cyclone DDS about 2 M, Kafka 53-62 k, MQTT 32-38 k; latency Zenoh peer 10 us, Cyclone DDS 8 us, Zenoh-pico 5 us, Kafka 27 us, MQTT 73 us. Written by Zenoh's vendor team and a university group | | [ZENOH23] |
| MQTT / MQTT-SN | pub/sub through a broker | MQTT-SN: 2- or 4-byte header, 2-byte topic id, sleeping clients whose messages the gateway buffers, QoS -1 for one-way publish without a session. VDA 5050 runs on MQTT 3.1.1 with QoS 0 for all topics but `connection` | Broker is a single point; store and forward only at the gateway | [MQTTSN][VDA5050 §4] |
| CoAP | request/response, observe | "fixed-size 4-byte header" over UDP; message size bound 1,152 bytes | Not designed for it | [RFC7252] |
| Space ROS | ROS 2 with flight-style assurance | "An open-source space robotics framework for developing flight-quality robotic and autonomous space systems"; inherits the ROS 2 middleware choice | No | [SPACEROS] |
| MAVLink 2 (drones) | broadcast stream plus command/ack microservices | 12 bytes of framing; optional 13-byte signature (link id, 48-bit timestamp, 48-bit truncated SHA-256) | No | [MAVLINK] |
| Bundle Protocol | datagram store and forward | 48 bytes per bundle (Computed) | Yes, it is DTN | [RFC9171] |

**What flight rovers use.**

- *CADRE (JPL, three rovers).* Flight software in F Prime ("uses F' as the software framework" [CADRE-SW]);
  centralised planning on an elected leader, distributed execution; "loss of the leader results in at most ten
  seconds of idle time" [CADRE25]. State is synchronised to the leader rather than shared by all, to cut
  traffic [CADRE25]. No ROS 2 in the flight stack was found.
- *VIPER (NASA Ames).* On-board software "Utilizes Core Flight System (cFS)" on a RAD750; the ground side is
  "an ensemble of Robot Operating System 2 (ROS2) nodes" [VIPER24]. Telemetry and commands are described in
  XTCE for both flight and ground [VIPER-XTCE].
- *Commercial rovers.* No public protocol description was found for the Lunar Outpost, Astrolab or
  Intuitive Machines vehicles: UNVERIFIED (searched vendor pages in earlier project notes).

**Consequence for LRIP.** The on-board bus is the owner's business (cFS software bus, F Prime ports, ROS 2
topics). LRIP is the wire format between vehicles. It is defined as packets with a topic number, so a cFS app,
an F Prime component or a ROS 2 / Zenoh bridge can each publish it with a few hundred lines of glue.

### Q7. Describing capabilities

**Direct answer.** A capability manifest: a small document, signed by the owner, that any other party can
fetch, containing typed and versioned capability entries. Section C3 gives two complete examples.

**Prior art, and what we take from each.**

| Prior art | How capabilities are described | What we take | Source |
|---|---|---|---|
| Model Context Protocol | A server declares a `tools` capability; the client calls `tools/list` and gets, per tool, `name`, `description`, `inputSchema` (JSON Schema) and optional `outputSchema`; `tools/call` invokes; a `listChanged` notification says the list changed; protocol version is negotiated at start | name + typed parameters + "list changed" notice + version handshake | [MCP] |
| VDA 5050 factsheet | JSON document per robot type: `typeSpecification` (class, kinematics, `maximumLoadMass`, localisation and navigation types), `physicalParameters` (speeds, accelerations, size), `protocolLimits`, `protocolFeatures` (optional parameters and supported actions), geometry, `loadSpecification`, configuration; published retained and on request | the split into physical limits, protocol features and load; "robot shall communicate which optional parameters it needs" | [VDA5050 §6.10, §7.10] |
| MassRobotics identity report | manufacturer, model, envelope, max speed, max run time, cargo type, volume, weight | the minimum any vendor will agree to publish | [MASSROB] |
| MAVLink | a 64-bit `capabilities` bitmask (`MAV_PROTOCOL_CAPABILITY`) in one message, plus named microservices | a 16-bit capability bitmask inside TASK_ANNOUNCE for fast filtering | [MAVLINK] |
| ROS 2 interfaces, DDS discovery, DDS-XTypes | typed message, service and action definitions; nodes and topics discoverable at run time; XTypes defines extensible and mutable types | typed interfaces; but discovery by broadcast is too costly on our link (Q6) | [RTPS]; ROS documentation page blocked a scripted fetch: UNVERIFIED wording; [XTYPES] title page only |
| JAUS (SAE AS-4) | AS5710A Core Service Set: "service definitions for transport, events, access control, management, time, liveness and discovery" | discovery and liveness as standard services; access control before command | [JAUS-W] (Wikipedia; SAE page blocked) |
| FIPA | agents register service descriptions with a directory facilitator; the Contract Net protocol is call for proposals, propose or refuse, accept or reject, inform or failure, with deadlines | TASK_ANNOUNCE / TASK_BID / TASK_AWARD / TASK_STATE are exactly this sequence | fipa.org blocked the fetch (Cloudflare); spec numbers SC00029 and SC00023 from memory: UNVERIFIED |
| STANAG 4586 | levels of interoperability for control of uncrewed aircraft | the idea of graded levels (receive data, task, control) | Wikipedia page opened but gave no usable text: UNVERIFIED |
| OPC UA companion specification | OPC 40010-1, OPC UA for Robotics Part 1: Vertical Integration, version 1.02 of 8 September 2025: an information model per device class | versioned, namespaced information models per vehicle class | [OPCUA-R] |
| IEEE 1872-2015 | "A core ontology that specifies the main, most general concepts, relations, and axioms of robotics and automation" (CORA); status inactive-reserved | vocabulary only; too heavy for the wire | [IEEE1872] |
| CCSDS XTCE and SEDS | XML description of every telemetry and command field, and of device interfaces | the ground-side description of LRIP packets is generated as XTCE, as VIPER does | [XTCE][SEDS][VIPER-XTCE] |

### Q8. How do different manufacturers understand each other?

**Direct answer.** One schema, owned by a neutral body, with five rules: (1) every message carries a
major.minor version; (2) minor versions only add; (3) receivers skip what they do not know; (4) numbers,
units and identifiers are never reused; (5) conformance is tested with public test vectors before a vehicle
is admitted to the site.

**Table B4. Encodings compared.**

| Encoding | Self-describing? | Unknown-field tolerance | Size for our position report (application PDU) | Source |
|---|---|---|---|---|
| Fixed bit-packed binary in a Space Packet | No; needs the schema and version | By rule: new fields are appended; the packet length tells the receiver how much to skip | 21 bytes | Computed; [SPP] |
| CBOR (RFC 8949) with a CDDL schema (RFC 8610) | Types yes, meaning no | Arrays: append only; maps with integer keys: any unknown key is skipped | 33 bytes as an array, 45 as a map with integer keys | Computed; [RFC8949][RFC8610] |
| Protocol Buffers | Field numbers and wire types | Unknown field numbers are skipped; a tag is "(field_number << 3) \| wire_type"; integers are base-128 varints | 36 bytes | Computed; [PROTOBUF] |
| ASN.1 unaligned PER (ITU-T X.691) | No | Extension markers must be declared in advance | about the same as bit-packed (not computed) | [X691] title page only |
| MAVLink XML dialects | No | MAVLink 2 truncates trailing zero bytes; extension fields are appended and excluded from the CRC seed | 12 bytes framing + payload | [MAVLINK] |
| CCSDS XTCE / SEDS | Describes any of the above from outside | n/a | n/a (description language) | [XTCE][SEDS] |
| JSON (VDA 5050, MassRobotics) | Yes | Yes | several hundred bytes | [VDA5050] |

**How the precedents handle versions.**

- *VDA 5050.* Every message header carries `version` "[Major].[Minor].[Patch]"; the major version is a level
  of the MQTT topic ("vda5050/v3/KIT/0001/order"); 3.0.1 is reserved for fixes, 3.1.0 for "Non-breaking,
  backward-compatible changes", 4.0.0 for breaking changes. A robot that receives an optional field it cannot
  use must reject the order with error `UNSUPPORTED_PARAMETER`, and the fleet control "shall only send
  optional fields that the mobile robot supports", which it learns from the factsheet. Version 3 introduced
  "extensible enums" [VDA5050]. Note the difference from our rule 3: VDA 5050 rejects, we skip, because a
  rover out of contact cannot ask again.
- *LunaNet.* The whole specification is versioned (V004 in 2022, V005 in 2025). Each interface row is tagged
  "LunaNet 1.0: Yes/No" and open items carry numbered "LNIS-TBD" placeholders; details move into applicable
  documents AD1 to AD8 [LNIS5].
- *CCSDS.* Blue books carry issue numbers and are re-confirmed every five years; old issues stay available as
  historical documents (883.0-B-1 is marked "Historical") [WPN].
- *MAVLink.* A version handshake and per-message CRC seed derived from the field layout, so two ends with
  different layouts of the same message cannot silently misread each other [MAVLINK].

**Conformance testing.** VDA 5050 publishes JSON schemas per topic; MassRobotics ships a reference sender and
receiver; MAVLink derives a checksum from the definition. No lunar surface conformance suite exists. LRIP
should ship: the schema (CDDL and an XTCE export), a set of golden packets with their decoded values, a
reference decoder, and a simulator scenario every newcomer must pass (this repository can host all four).

### Q9. Minimum message size on a narrow-band link

**Direct answer.** See section E2 for the byte-by-byte derivation. Results:

**Table B5. Bytes on the air for four messages (Computed).**

| Message | Content bits | Content bytes | + LRIP header 8 | + Space Packet header 6 | + security 14 (MAC 8) | + security 22 (MAC 16) | CBOR, secured (MAC 8) | protobuf, secured (MAC 8) |
|---|---|---|---|---|---|---|---|---|
| POSITION | 104 | 13 | 21 | 27 | **41** | 49 | 53 | 56 |
| STATUS | 120 | 15 | 23 | 29 | **43** | 51 | 55 | 64 |
| TASK_BID | 72 | 9 | 17 | 23 | **37** | 45 | 46 | 50 |
| ALERT | 112 | 14 | 22 | 28 | **42** | 50 | 53 | 60 |

Add 12 bytes per message inside a Proximity-1 frame (3-byte sync marker, 5-byte header, 4-byte CRC) [P1-CS]
[P1-DLL], or 48 bytes inside a BPv7 bundle, or 108 bytes inside a bundle with a BPSec integrity block.

**Table B6. Bit rate for N rovers sending one secured position report each (41 bytes; Computed).**

| N | 0.1 Hz | 1 Hz | 10 Hz |
|---|---|---|---|
| 5 | 0.16 kbit/s | 1.64 kbit/s | 16.4 kbit/s |
| 20 | 0.66 kbit/s | 6.56 kbit/s | 65.6 kbit/s |
| 50 | 1.64 kbit/s | 16.4 kbit/s | 164 kbit/s |
| 100 | 3.28 kbit/s | 32.8 kbit/s | 328 kbit/s |

With a 16-byte MAC multiply by 49/41; with Proximity-1 framing by 53/41; in secured bundles by 135/41.

**Comparison with the project's earlier assumption.** E48 assumed a 48-byte status at 1 Hz with an 8-byte
header and no security, measured 48 B/s per robot and 7.68 kbit/s for 20 robots, against targets of 100 B/s
and 16 kbit/s (Project). The LRIP beacon set is POSITION at 1 Hz plus STATUS and INTENT at 0.1 Hz: 41 + 4.3 +
3.8 = 49 B/s per robot with an 8-byte MAC (59 B/s with a 16-byte MAC), or 7.9 kbit/s (9.4 kbit/s) for 20
robots. So the earlier figure is confirmed at one hop and 1 Hz, and it now includes authentication. It is
exceeded when (a) the rate is 10 Hz: 66 kbit/s; (b) the channel is random access: slotted ALOHA carries at
most 1/e = 37 % of its rate, so 7.9 kbit/s of offered load needs a 21 kbit/s channel; (c) messages are relayed:
E48 counted bytes generated, and a message relayed over h hops occupies the shared channel h times.

### Q10. Protecting the link from interference and spoofing

**Direct answer.** Authenticate every message at the message level, encrypt only what is confidential
(commercial bids), manage keys per owner under a base trust anchor, count every message to stop replay, and
accept that jamming is handled by diversity and by safe behaviour, not by cryptography.

**Evidence.**

- *Link-layer security.* SDLS adds a security header (mandatory 16-bit security parameter index; optional
  initialisation vector 1-32 bytes, sequence number 2-8 bytes, pad length) and a trailer with a MAC of 8 to 64
  bytes. Baseline for telecommand: AES-CMAC, 256-bit key, 32-bit anti-replay sequence number in a 6-byte header
  and a 16-byte MAC. Baseline for telemetry, AOS and USLP: AES-GCM, 256-bit key, 96-bit IV sent in a 14-byte
  header, 16-byte MAC. The MAC may be truncated to the agreed transmitted length; the shortest allowed is 8
  bytes [SDLS §4.1, Table 6-1, Annex E]. Proximity-1 frames are not among the frame types SDLS covers; USLP
  is, and USLP can run over the Proximity-1 coding sublayer [SDLS][USLP].
- *Why 256-bit keys.* "the well-known Grover algorithm divides by 2 the exponent of the number of trials for
  brute force attack ... the key length for baseline mode of SDLS was doubled to 256-bit" [SDLS-GB, January
  2024]. Symmetric SDLS is therefore already quantum-resistant.
- *Replay.* The receiver keeps the highest sequence number seen and discards a frame outside a "sequence
  number window" sized "for predicted delays and gaps in RF transmission" [SDLS §2.3.2.3]. The 32-bit counter
  allows "about 4 billion invocations before the counter rolls over" [SDLS-GB].
- *MAC length.* NIST: a forged MAC of Tlen bits is accepted with probability 2^-Tlen per try; "For most
  applications, a value for Tlen that is at least 64 should provide sufficient protection"; shorter values only
  where the number of failed verifications per key is limited [NIST38B App. A]. For GCM, tags of 64 or 32 bits
  are allowed only with a cap on the number of decryptions per key: 2^32 for 64-bit tags on packets up to 2^15
  bytes [NIST38D App. C]. MAVLink 2 signs with a 48-bit truncated hash and a 48-bit timestamp against replay
  [MAVLINK], a working precedent for small authenticated robot messages.
- *Key management for many owners.* SDLS Extended Procedures give master keys (never used for traffic) and
  session keys, key states (pre-activation, active, deactivated, destroyed), over-the-air rekeying and key
  verification between one initiator and one recipient [SDLS-EP]. They assume one mission, not a site with
  several owners. CCSDS algorithms include RSA and ECDSA signatures [CRYPTO], which is the hook for per-owner
  certificates. The surface-wireless book already requires certificates for Wi-Fi: WPA3-Enterprise with
  EAP-TLS, certificates "shall be renewed", SHA-384 and 3,072-bit keys [WPN §3.3.3], and LTE roaming between
  agencies' cores with "Visiting UE IMSI Authentication" [WPN §3.4.4]. LunaNet's own security specification is
  still a placeholder [LNIS5].
- *Bundle security.* BPSec integrity and confidentiality blocks; defaults HMAC-SHA2 and AES-GCM
  [RFC9172][RFC9173]; used on the ISS-LCRD test [HYLTON24].
- *Post-quantum.* No CCSDS book standardises post-quantum key establishment yet; a January 2024 green book
  notes the threat and answers it for symmetric keys only [SDLS-GB]. Research in 2025-2026 proposes
  post-quantum over-the-air rekeying for SDLS (ESA Security for Space 2025; IACR ePrint 2026/2354; found by
  search, papers not opened: UNVERIFIED). Sizes matter on our link: an ML-DSA-44 signature is 2,420 bytes and
  its public key 1,312 bytes [FIPS204]; an ML-KEM-768 encapsulation key is 1,184 bytes and a ciphertext 1,088
  bytes [FIPS203]; an Ed25519 signature is 64 bytes [RFC8032]. Post-quantum signatures cannot go on a 1 Hz
  beacon; they can be used once per key period when a vehicle enrols.
- *Broadcast authentication.* With one shared group key any member can forge any other member's beacon.
  TESLA gives source authentication for broadcast with only symmetric operations and delayed key disclosure;
  it "requires no trust between receivers" but receivers "must be loosely time-synchronized" [RFC4082].
- *Jamming and interference.* CCSDS lists "communications system jamming resulting in denial of service" and
  "replay of recorded authentic communications traffic" among the threats to every mission class [THREAT].
  Protection criteria for space research links are an interference-to-noise density ratio of -6 dB for 0.1 %
  of the time (ITU-R SA.609, as quoted in [SFCG26]). Unintended interference is the likelier case on the Moon:
  another operator's Wi-Fi or LTE in the same band, or a surface transmitter leaking into the 2483.5-2500 MHz
  navigation band [SFCG25].
- *Incidents.* (1) Landsat-7 "experienced 12 or more minutes of interference" on 20 October 2007 and again
  on 23 July 2008; Terra EOS AM-1 two or more minutes on 20 June 2008 and nine or more minutes on 22 October
  2008, where "The responsible party achieved all steps required to command the satellite but did not issue
  commands" [USCC11, PDF page 224]. Lesson: an unauthenticated command link is one step from loss of control.
  (2) KA-SAT, 24 February 2022: a "misconfiguration in a VPN appliance" gave access to "the trusted management
  segment"; destructive commands "overwrote key data in flash memory on the modems"; "tens of thousands of
  modems" went offline; the satellite was not touched [VIASAT22]. Lesson: the management plane (here: the base
  computer and key distribution) is the target, and a command valid for all terminals at once is the danger.
  LRIP therefore has no message that reprograms or disables another owner's vehicle.

### Q11. Detecting wrong position data from another rover

**Direct answer.** Three layers. (1) Plausibility: time, speed, map and radio-geometry checks that need no
sensor. (2) A statistical test of the reported position against the receiver's own range or bearing
measurement of the sender (chi-square on the normalised innovation). (3) Agreement among several witnesses
that tolerates F liars (trimmed consensus, W-MSR), plus Byzantine-fault-tolerant agreement for the ledger.

**Evidence.**

- *Innovation test.* Standard Kalman-filter gating; stated and worked in section E5. With one false alarm in
  1,000 tests the threshold is 10.83 for one measurement and 13.82 for two (Computed). The project already has
  a deterministic cousin: R9 declares a vehicle non-conforming beyond e_conf = 3 sigma_nav + 5 m = 11 m
  (Project); the chi-square version gives 9.4 m for sigma_nav = 2 m and a 0.3 m ranging error, so the two agree.
- *RAIM-style redundancy.* Receiver autonomous integrity monitoring checks the consistency of redundant
  measurements to give "timely warnings to the user when the service should not be used" [NAVIPEDIA]. Applied
  here: with n range measurements to one rover and 2 unknowns (its horizontal position) the residual has n - 2
  degrees of freedom; 3 witnesses can detect one bad report, 4 can say which one (section E5).
- *W-MSR and robustness.* Each normal node discards up to F values above and F below its own among those it
  hears, then averages. Definition: a graph is (r, s)-robust if for every pair of disjoint non-empty node sets
  at least one set is entirely made of nodes with r or more neighbours outside it, or the two sets together
  contain at least s such nodes. Theorem: with at most F malicious nodes in the whole network, the normal nodes
  reach agreement "if and only if the network topology is (F + 1, F + 1)-robust"; with at most F in each
  neighbourhood, (2F + 1)-robustness is sufficient and (F + 1)-robustness necessary; "the minimum in-degree of
  an (F + 1, F + 1)-robust digraph is at least 2F + 1" [LEBLANC12; the report proves these for the
  continuous-time protocol ARC-P; the discrete-time W-MSR paper (LeBlanc et al., IEEE JSAC 2013) states the
  same conditions but is paywalled and was not opened: UNVERIFIED for W-MSR by direct reading].
- *Multi-robot results.* A communication graph built from the Voronoi tessellation of robot positions is
  robust enough to reject one non-cooperative robot, and can be extended to reject two [SAULNIER22]. A
  decentralised blocklist protocol built on robots accusing each other after cross-checking observations lowers
  the connectivity requirement of W-MSR "from (2F+1)-connected to (F+1)-connected" [WARDEGA23]. A 2021 survey
  places these methods in a taxonomy of resilience for robot teams [PROROK21]. Cooperative localisation
  methods differ strongly in how they degrade under weak data association [KHOSRAVI26].
- *Byzantine agreement bound.* With unsigned messages agreement is possible only if "more than two-thirds of
  the generals are loyal", i.e. n >= 3m + 1 for m traitors; "With unforgeable written messages, the problem is
  solvable for any number of generals" [LAMPORT82]. Since LRIP messages are authenticated, the ledger needs
  3f + 1 voters only if we want agreement without trusting clocks and delivery times; for f = 1 that is 4.
- *Telemetry anomaly detection* (owner's input 1): an LSTM predictor with a dynamic threshold reached 87.5 %
  precision and 80.0 % recall on spacecraft telemetry (Project, `00_inputs_from_owner.md`). It is the pattern
  for a learned detector, to be compared against the chi-square baseline, never to replace it.

### Q12. Behaviour after a complete loss of communication

**Direct answer.** A deterministic ladder known to everyone in advance (section C7). The guiding rule from
aviation is predictability: a vehicle without a link does exactly what its last filed plan and the published
procedure say, so the others can plan around it.

**Evidence.**

- *Uncrewed aircraft.* FAA Notice N JO 7110.724 (effective 11 October 2016, later merged into Order JO
  7110.65): "Lost link procedures are programmed into the flight management system and associated with the
  flight plan being flown"; the aircraft squawks the dedicated code 7400; the controller must "Determine the
  lost link procedure" from the operating approval and "Coordinate, as required, to allow UAS to execute the
  lost link procedure" [FAA16]. Three ideas carry over: the procedure is filed in advance, the loss is
  announced by a dedicated signal, and everyone else makes room.
- *Crewed aircraft under instrument rules.* 14 CFR 91.185: fly the route "assigned in the last ATC clearance
  received", else the route ATC said to expect, else the filed route; at "the highest of" the assigned,
  minimum and expected altitudes; leave the clearance limit at the expect-further-clearance time [CFR91185].
  Our equivalent: keep the last confirmed reservation, then the filed intent, never something new.
- *Drone autopilots.* PX4 triggers a data-link-loss failsafe after a configurable timeout (`COM_DL_LOSS_T`);
  the action (`NAV_DLL_ACT`) is one of hold, return, land, disarm or terminate; a "distance-aware return"
  starts the return when remaining endurance equals the time needed to get back [PX4].
- *Spacecraft.* Safe mode is "an operating mode ... during which all non-essential systems are shut down and
  only essential functions such as thermal management, radio reception and attitude control are active",
  entered automatically on a predefined condition [WIKI-SAFE].
- *Factory robots.* VDA 5050: "If the mobile robot disconnects from the broker, it keeps all the order
  information and fulfills the order up to the last released node"; the broker publishes a last-will message
  `CONNECTION_BROKEN` so the fleet control knows [VDA5050 §4.1, §6.5]. This is the Project's rule R7 almost
  word for word.
- *CADRE.* After a cooling shutdown the rovers wake about every 30 minutes and re-elect a leader (Project
  note); a lost leader is replaced within 10 s [CADRE25].
- *Project rules already in the simulator.* R7: a vehicle that loses the mesh keeps only the reservations it
  holds, stops at the next safe point, and others treat its last reserved volume as occupied; hold timeout 10
  min, sweep 1-60 min. R9: 1 Hz broadcast, non-conforming after 60 s late. Auction rendezvous timeout 1 h,
  sweep 0.5-2 h. Leader re-election 0.5 h (Project).

---

## C. Our design: the Lunar Rover Interaction Protocol (LRIP) v0.1

Design rules. (1) Reuse every standard below the application layer. (2) One schema, two encodings: profile N
(narrow-band, bit-packed) and profile B (broadband, CBOR), with identical fields. (3) Authenticate everything,
sign what moves rights. (4) Nothing in LRIP can command another owner's vehicle; it can only inform, ask and
agree. (5) Every behaviour without a link is fixed in advance.

### C1. Layered stack

```
Application  LRIP messages: POSITION STATUS INTENT ALERT TASK_* RESERVE_* CAP_* MAP_NOTICE HELLO;
             lost-link ladder (C7); fault detector (C8); capability manifest (C3)
Messaging    publish/subscribe topics for state; request/response calls for rights (C5)
             profile N: CCSDS Space Packet, APID = topic, bit-packed payload
             profile B: the same fields as CBOR (CDDL schema) on Zenoh or MQTT-SN keys, or UDP
Security     per message: SPI (2 B) + sequence number (4 B) + AES-CMAC truncated to 8 B (N) or 16 B (B);
             Ed25519 signature (64 B) on AWARD, GRANT, MANIFEST and site-wide ALERT;
             bundles: BPSec integrity block; bids encrypted (AES-GCM) until the auction closes
Network      one-hop broadcast + mesh relay with a hop limit of 5;
             DTN: Bundle Protocol v7 (RFC 9171) with custody transfer for anything that must survive an
             outage; contact plan from the base (CCSDS 734.3-B-1); IP where it exists
Link         near the base: IEEE 802.11ax or 3GPP LTE (CCSDS 883.0-B-2) with their own link security;
             narrow-band: USLP frames (CCSDS 732.1-B-3) with SDLS (355.0-B-2), or Proximity-1 frames;
             to orbit: AOS / USLP as in LNIS v5
Physical     UHF 390-405 / 435-450 MHz (not on the far side); S 2.4-2.48 and 2.5035-2.655 GHz;
             5.15-5.835 GHz; relay S 2025-2110 / 2200-2290 MHz, K 23.15-23.55 / 27.0-27.5 GHz;
             Earth X 7190-7235 / 8450-8500 MHz
```

### C2. Message catalogue

**Common framing, profile N.** All multi-byte fields big-endian, bit fields packed most significant bit first.

| Part | Field | Type | Unit / meaning | Bits |
|---|---|---|---|---|
| Space Packet primary header [SPP] | version, type, secondary-header flag | fixed | 000, 0, 1 | 5 |
| | APID | uint | 0x500 + msg_type (range to be registered with SANA) | 11 |
| | sequence flags, sequence count | uint | 11 (unsegmented), per-APID counter | 16 |
| | packet data length | uint | bytes after this header minus 1 | 16 |
| LRIP header | ver_major, ver_minor | uint | schema version, 0.1 = (0, 1) | 4 + 4 |
| | msg_type | enum | see catalogue | 8 |
| | sender_id | uint | vehicle number issued at enrolment | 16 |
| | t_valid | uint | 0.1 s since the LRIP epoch on the site time base; wraps after 13.6 years | 32 |
| Security header (after the payload) | spi | uint | which key: owner, key epoch, MAC or signature | 16 |
| | seq | uint | per sender and key, strictly increasing | 32 |
| Security trailer | mac | bytes | AES-CMAC over everything before it, truncated | 64 (N) or 128 (B) |

Fixed overhead: 6 + 8 + 6 + 8 = 28 bytes (profile N), 36 bytes with the 16-byte MAC, 84 bytes when signed.

**Catalogue.** Sizes are payload / secured packet with 8-byte MAC. "E48" is the size assumed earlier (Project).

| ID | Message | Pattern | Default rate | Payload B | Secured B | E48 B | Carried by |
|---|---|---|---|---|---|---|---|
| 1 | POSITION | publish | 1 Hz moving, 0.1 Hz parked (sweep 0.1-10) | 13 | 41 | 48 (status) | broadcast, not queued |
| 2 | STATUS | publish | 0.1 Hz and on change | 15 | 43 | | broadcast, not queued |
| 3 | INTENT | publish | 0.1 Hz and on change | 10 | 38 | | broadcast, not queued |
| 4 | ALERT | publish, repeated | on event, 3 repeats, then 0.1 Hz while valid | 14 | 42 (98 signed) | 64 (landing) | broadcast and bundle |
| 5 | TASK_ANNOUNCE | publish | on event | 16 | 44 | | bundle |
| 6 | TASK_BID | request | on event | 9 | 37 | 40 | bundle, encrypted |
| 7 | TASK_AWARD | response | on event | 8 | 92 signed | 32 | bundle, custody |
| 8 | TASK_STATE | publish | on change | 5 | 33 | 32 (claim) | bundle |
| 9 | RESERVE_REQ | request | on event | 7 | 35 | 32 | direct, else bundle |
| 10 | RESERVE_GRANT | response | on event | 10 | 94 signed | 32 | direct, else bundle |
| 11 | RESERVE_RELEASE | publish | on event | 3 | 31 | 16 | direct, else bundle |
| 12 | CAP_QUERY | request | on first contact or new manifest_crc | 3 | 31 | | direct |
| 13 | CAP_MANIFEST | response, retained | on query | about 250 (CBOR) | about 330 signed | | bundle or CFDP |
| 14 | MAP_NOTICE | publish | on change | 10 | 38 | | bundle; the map itself by CFDP |
| 15 | HELLO | publish | 1 Hz when nothing else was sent | 2 | 30 | | broadcast |

**POSITION** (104 bits). Frame and datum are defined in the positioning note; here only the encoding.

| Field | Type | Unit, range | Bits |
|---|---|---|---|
| e | int | 0.01 m east in the site grid, +/- 83.9 km | 24 |
| n | int | 0.01 m north, +/- 83.9 km | 24 |
| h | int | 0.1 m above the site datum, +/- 3.28 km | 16 |
| heading | uint | 0.1 deg clockwise from grid north, 0-359.9 | 12 |
| speed | uint | 0.01 m/s, 0-10.23 | 10 |
| sigma_h | uint | 0.05 m, one-sigma horizontal error, 0-12.7; 255 = unknown | 8 |
| nav_src | enum | 0 dead reckoning, 1 visual, 2 LANS, 3 ranging to beacons, 4 cooperative, 5 surveyed (parked) | 3 |
| moving | flag | 1 = wheels or thrusters active | 1 |
| spare | | zero | 6 |

**STATUS** (120 bits).

| Field | Type | Unit, range | Bits |
|---|---|---|---|
| mode | enum | 0 idle, 1 driving, 2 working, 3 charging, 4 waiting, 5 hold (lost link), 6 returning, 7 safe, 8 fault, 9 teleoperated, 10 hopping | 4 |
| health | flags | mobility, power, thermal, comms, navigation, payload, brake, e-stop, 4 spare | 12 |
| soc | uint | percent of usable battery | 7 |
| energy | uint | 10 Wh remaining, 0-40.95 kWh | 12 |
| power | int | 10 W, + discharging, +/- 5.11 kW | 10 |
| cargo_mass | uint | kg, 0-2,047 | 11 |
| cargo_type | enum | site cargo catalogue | 8 |
| task_id | uint | 0 = none | 16 |
| progress | uint | percent | 7 |
| temp | int | deg C, electronics bay | 8 |
| link_snr | uint | dB to the best neighbour, 0-63 | 6 |
| hops | uint | hops to the base, 7 = no path | 3 |
| manifest_crc | uint | CRC-16 of the current manifest; a change triggers CAP_QUERY | 16 |

**INTENT** (80 bits): segment_id (16), direction (1), reservation_id (16), t_enter (12, s after t_valid),
t_exit (12, s), v_target (10, 0.01 m/s), dest_site (8), spare (5).

**ALERT** (112 bits).

| Field | Type | Unit, range | Bits |
|---|---|---|---|
| alert_id | uint | per sender | 8 |
| type | enum | 1 all-stop, 2 landing closure, 3 hazard, 4 vehicle fault, 5 crew nearby, 6 position dispute, 7 link degraded, 8 plume (hop) | 6 |
| severity | enum | 0 info, 1 caution, 2 warning, 3 emergency | 2 |
| e, n | int | 0.01 m, centre of the affected area | 24 + 24 |
| radius | uint | m, 0-4,095 | 12 |
| valid | uint | s after t_valid, up to 18.2 h | 16 |
| subject_id | uint | vehicle concerned, 0 = none | 16 |
| ack | flag | receivers must answer with an acknowledgement | 1 |
| repeat | uint | repetition number | 3 |

**TASK_ANNOUNCE** (128 bits): task_id (16), task_type (8), from_site (8), to_site (8), mass kg (11),
cap_mask (16, required capability bits), t_earliest (16, 10 s), t_deadline (16, 10 s), reserve_price (16),
bid_close (8, s), priority (3), spare (2).

**TASK_BID** (72 bits).

| Field | Type | Unit, range | Bits |
|---|---|---|---|
| task_id | uint | as announced | 16 |
| cost | uint | site unit of account (market note), 0-65,535 | 16 |
| t_start | uint | 10 s after t_valid, up to 11.4 h | 12 |
| t_finish | uint | 10 s after t_valid | 12 |
| soc_after | uint | percent expected at completion | 7 |
| bundle_pos | uint | position in the bidder's bundle, 0 = single | 3 |
| bid_seq | uint | replaces earlier bids with a lower number | 6 |

**TASK_AWARD** (64 bits): task_id (16), winner_id (16), price (16), lease (12, 10 s), award_seq (4).
**TASK_STATE** (40 bits): task_id (16), state (4: claimed, started, loaded, delivered, failed, abandoned,
ack), result (4), progress (7), spare (1), eta (8, min).
**RESERVE_REQ** (56 bits): resource_id (16), direction (1), priority class (3), t_start (16, s), duration
(12, s), req_seq (8). **RESERVE_GRANT** (80 bits): resource_id (16), reservation_id (16), verdict (4: granted,
denied, queued), t_start (16), t_end (16), free_at (12). **RESERVE_RELEASE** (24 bits): reservation_id (16),
reason (4), spare (4). **CAP_QUERY** (24 bits): target_id (16), known_rev (8). **MAP_NOTICE** (80 bits):
tile_id (24), layer (4), version (12), hash (32), size kB (8). **HELLO** (16 bits): link margin dB (6),
neighbours heard (5), bundles queued (5).

Profile B carries the same fields as a CBOR array in the same order, header fields first; a CDDL file is the
normative schema. Sizes: Table B5.

### C3. Capability manifest

Rules. The manifest is JSON for humans and CBOR on the wire, with every key and every enumerated string
replaced by a small integer from the published registry and decimals as fixed-point integers. It is signed by
the owner's key. `rev` increases on every change; STATUS carries its CRC-16. A capability is `name`
(namespaced, lower case), `ver` (major.minor) and typed `params`; unknown capabilities and unknown params are
ignored by the reader. Values below are examples; class figures follow the Project's vehicle table.

**Small rover** (1,200 bytes minified JSON; 942 bytes CBOR with text keys; 548 with integer keys; 247 bytes
with integer keys, enumerated strings and fixed-point numbers; Computed).

```json
{"lrip": "0.1", "rev": 7,
 "vehicle": {"id": 291, "owner": "OWNER-B", "model": "small-rover-example", "class": "small_rover"},
 "physical": {"mass_kg": 300, "length_m": 1.6, "width_m": 1.2, "height_m": 0.9, "antenna_m": 1.0,
              "v_max_mps": 0.83, "brake_mps2": 0.5, "slope_max_deg": 20},
 "energy": {"battery_wh": 2000, "drive_wh_per_km": 120, "charge_w": 400, "night_survival": false},
 "comms": [{"band": "S", "std": "3GPP-LTE", "tx_w": 0.25, "relay": true},
           {"band": "UHF", "std": "LRIP-NB", "tx_w": 1.0, "relay": true}],
 "nav": {"sources": ["visual_odometry", "lans", "uwb_ranging"], "sigma_h_m": 1.0,
         "ranging": {"type": "uwb", "sigma_m": 0.3, "range_m": 200}},
 "messages": {"pub": ["POSITION/1", "STATUS/1", "INTENT/1", "ALERT/1", "TASK_BID/1"],
              "sub": ["ALERT/1", "TASK_ANNOUNCE/1", "TASK_AWARD/1", "RESERVE_GRANT/1"]},
 "capabilities": [
  {"name": "transport.carry", "ver": "1.0",
   "params": {"mass_kg": {"max": 200}, "volume_m3": {"max": 0.5}, "interface": ["tray-A"]}},
  {"name": "relay.store_forward", "ver": "1.0", "params": {"buffer_mb": {"max": 64}}},
  {"name": "survey.image", "ver": "1.0", "params": {"gsd_mm": {"min": 2}, "bands": ["rgb"]}},
  {"name": "team.lift", "ver": "0.1", "params": {"share_kg": {"max": 90}}}],
 "lost_link": {"t_hold_s": 30, "t_return_s": 600, "t_rendezvous_s": 3600,
               "policy": "stop-return-rendezvous"}}
```

**Hopper** (1,210 bytes minified JSON; 947 bytes CBOR with text keys; 512 with integer keys; 251 bytes fully
compact; Computed).

```json
{"lrip": "0.1", "rev": 3,
 "vehicle": {"id": 517, "owner": "OWNER-C", "model": "hopper-example", "class": "hopper"},
 "physical": {"mass_kg": 250, "length_m": 1.5, "width_m": 1.5, "height_m": 1.0, "antenna_m": 1.0,
              "v_max_mps": 0.0, "brake_mps2": 0.0, "slope_max_deg": 15},
 "energy": {"battery_wh": 1500, "propellant_kg": 120, "hop_range_km": 2.0, "total_range_km": 50,
            "charge_w": 300, "night_survival": false},
 "comms": [{"band": "S", "std": "3GPP-LTE", "tx_w": 0.5, "relay": true},
           {"band": "UHF", "std": "LRIP-NB", "tx_w": 1.0, "relay": true}],
 "nav": {"sources": ["terrain_relative", "lans", "imu"], "sigma_h_m": 5.0,
         "ranging": {"type": "none", "sigma_m": 0, "range_m": 0}},
 "messages": {"pub": ["POSITION/1", "STATUS/1", "INTENT/1", "ALERT/1", "TASK_BID/1"],
              "sub": ["ALERT/1", "TASK_ANNOUNCE/1", "TASK_AWARD/1", "RESERVE_GRANT/1"]},
 "capabilities": [
  {"name": "transport.hop", "ver": "1.0",
   "params": {"mass_kg": {"max": 10}, "range_km": {"max": 2.0}, "pad_clear_m": {"min": 50}}},
  {"name": "survey.psr", "ver": "1.0", "params": {"dwell_min": {"max": 45}, "bands": ["ir", "neutron"]}},
  {"name": "relay.high_point", "ver": "0.1", "params": {"height_m": {"max": 100}, "dwell_s": {"max": 60}}}],
 "hazard": {"plume_keepout_m": 100, "notice_s": 300},
 "lost_link": {"t_hold_s": 30, "t_return_s": 0, "t_rendezvous_s": 0, "policy": "land-and-hold"}}
```

The hopper shows why the manifest must be open-ended: `propellant_kg`, `hazard.plume_keepout_m` and
`transport.hop` do not exist for a rover, and a rover's software must simply skip them.

### C4. Versioning rule

1. Every message carries `ver_major.ver_minor` of the schema; every capability carries its own version.
2. A minor version may only append fields at the end of a payload, use spare bits, or add enumeration values
   and message types. It may never move, resize, rename or change the unit of an existing field.
3. A receiver processes the fields it knows and skips the rest (the packet length says how much). An unknown
   message type is counted and dropped. An unknown enumeration value is treated as the most cautious known
   value (unknown alert type = hazard; unknown mode = fault).
4. Field numbers, APIDs, enumeration codes and capability names are never reused.
5. A major version is a new APID range and a new topic prefix (`lrip/2/...`). The site runs majors N and N-1
   in parallel for a stated overlap; the manifest lists which a vehicle speaks; the base refuses enrolment
   when there is no common major.
6. A release is the CDDL schema, its XTCE export, golden packets with decoded values, and the conformance
   scenario. A vehicle is admitted only after its recorded packets pass the reference decoder.

### C5. Topics and calls

**Published topics** (key `lrip/<major>/<site>/<topic>/<sender>`; in profile N the APID replaces the key).

| Topic | Message | Publisher | Subscribers | Delivery |
|---|---|---|---|---|
| `pos` | POSITION | every vehicle | neighbours, base | latest value only, never queued |
| `status` | STATUS | every vehicle | owner, base, bidders | latest value only |
| `intent` | INTENT | every vehicle | neighbours, base | latest value only |
| `alert` | ALERT | anyone; all-stop and landing closure only signed by the base | all | repeated, also bundled |
| `task/announce` | TASK_ANNOUNCE | task owner or base | capable vehicles (by cap_mask) | bundle, lifetime = bid_close |
| `task/state` | TASK_STATE | winner | task owner, base, ledger | bundle |
| `reserve/release` | RESERVE_RELEASE | holder | base, neighbours | direct, else bundle |
| `map/notice` | MAP_NOTICE | base, surveyors | all | bundle |
| `link` | HELLO | every vehicle | neighbours | never queued |
| `cap` | CAP_MANIFEST | every vehicle | all | retained at the base |

**Request/response calls.**

| Call | Request -> response | Timeout | On timeout |
|---|---|---|---|
| `cap.get` | CAP_QUERY -> CAP_MANIFEST | 10 s | ask the base for its retained copy |
| `reserve.request` | RESERVE_REQ -> RESERVE_GRANT (granted, denied or queued) | 3 s direct, 60 s by bundle | no reservation; stop before the entry (R3, R7) |
| `task.bid` | TASK_BID -> TASK_AWARD to the winner, nothing to the others | bid_close + 30 s | bid void |
| `task.claim` | TASK_AWARD -> TASK_STATE(claimed) | 60 s | award void, task re-announced |
| `alert.ack` | ALERT(ack = 1) -> TASK_STATE(ack) | 3 repeats | sender lists non-responders to the base |
| `map.fetch` | MAP_NOTICE -> file by CFDP class 2 or bundles | bundle lifetime | keep the old tile, widen margins |

### C6. Keys

- The base (or the site authority on Earth) is the trust anchor. Each owner has a certificate signed by it;
  each vehicle has an Ed25519 key certified by its owner. Enrolment happens once per key period over the
  broadband link or before launch; post-quantum signatures, if required, are used only there.
- From enrolment each vehicle holds: a pairwise 256-bit key with the base, its owner's fleet key, and the
  site broadcast key of the current epoch (delivered encrypted under the pairwise key, as in SDLS-EP rekeying).
- Beacons are authenticated with the site broadcast key: this stops outsiders, not a compromised insider.
  Insider lies are caught by C8. Messages that move rights are signed by the sender's own key.
- Key epoch 24 h for the site key (sweep 1 h to 30 days); a vehicle is expelled by not giving it the next key.

### C7. Lost-link state machine

"Link" means an authenticated message from the base, directly or relayed, within the stated time.

| State | Entered when | Behaviour | Leaves when |
|---|---|---|---|
| LINKED | base heard within T1 | normal | no base for T1 = 5 s |
| DEGRADED | no base for 5 s, neighbours still heard | switch to the narrow-band channel; no new reservations (R7); keep held ones; send through neighbours; bundle what must arrive | base heard: LINKED. No base for T2 = 30 s, or no neighbour: ISOLATED |
| ISOLATED | T2 expired or nobody heard for 5 s | finish the reserved segment at reduced speed; never stop inside a single-lane segment, a landing zone or a crew zone; stop at the next safe point | stopped: HOLD |
| HOLD | stopped at a safe point | beacon HELLO and POSITION at 0.1 Hz; listen on both bands | link: RESYNC. T_hold = 600 s: RETURN (if the manifest allows) |
| RETURN | hold expired | retrace the driven path to the last point where the link margin was good; half speed; sight-distance rules only; wait at the entry of any single-lane segment | link: RESYNC. Arrived and still no link for T_rdv = 3,600 s: RENDEZVOUS |
| RENDEZVOUS | at the last-link point for 1 h | drive to the nearest pre-agreed meeting point (listed in the site plan, in view of the mast) by open terrain only | link: RESYNC. Arrived, no link: SAFE |
| SAFE | energy reserve reached at any time, or rendezvous failed | park, minimum power, beacon every 60 s on the UHF hailing channel, wait for a helper | link: RESYNC |
| RESYNC | link returns | fresh sequence numbers; send STATUS and POSITION; receive the reservation table and queued bundles; resume only after the base confirms conformance | confirmed: LINKED |

Rules for the others. The base and neighbours keep the silent vehicle's last reserved volume blocked. After
T_hold the base converts it into a blocked zone around the last reported position plus the distance it could
have covered, and it stays blocked until the vehicle is heard or seen. An awarded task whose winner is silent
for the lease returns to the pool (the Project's 1 h). Energy overrides the ladder: when the charge needed
to reach a charger or sunlight plus a margin equals the charge left, the vehicle goes there (the drone
autopilot's distance-aware return).

### C8. Fault-detection rule

For each neighbour j whose POSITION is less than 2 s old, vehicle i:

1. *Plausibility.* Reject and count if: the time stamp is in the future or older than 10 s; the implied speed
   since the last report exceeds the manifest's v_max plus 3 sigma_h per second; the position is inside a
   mapped obstacle or outside the site; or the message was received directly although the terrain mask says the
   two positions cannot see each other.
2. *Innovation test.* With its own range and/or bearing to j, compute the innovation v = z - h(p_i, p_j), its
   covariance S = R + H_i P_i H_i^T + H_j P_j H_j^T (P_j from the reported sigma_h), and d2 = v^T S^-1 v.
   Flag the report if d2 > gamma, with gamma = 10.83 (range only) or 13.82 (range and bearing): a false-alarm
   probability of 10^-3 per test.
3. *Persistence.* Declare j *suspect* when 3 of the last 5 tests are flagged (false-alarm probability about
   10^-8 per window). Inflate j's occupied volume as for a non-conforming vehicle (R9) and publish
   ALERT(type 6, subject j).
4. *Agreement.* The base (or the elected leader) declares j non-conforming when F + 1 = 2 vehicles of
   different owners report it within 10 s. Shared quantities that many vehicles average use W-MSR with F = 1,
   which needs each to hear at least 3 others.

---

## D. Simulation parameters (for the backend engineer)

"Project" = already in the repository; "LRIP" = chosen in section C; "Assumed" = no source, sweep it.

| Parameter | Value | Sweep range | Unit | Source |
|---|---|---|---|---|
| Broadband surface carrier | 2.4 | 2.4, 2.58, 3.65, 5.8 | GHz | Project `radio.py`; [SFCG24]; [LUNARRF] |
| Narrow-band fallback carrier | 0.4 | 0.39-0.45 | GHz | [P1-PHY]; [SFCG24] (not on the far side) |
| Antenna height: rover / small robot / mast | 2.5 / 1.0 / 10 | 0.5-2.5; mast 4-20 | m | Project; [LSR23]; [LUNARRF] uses 4 and 1.5 |
| Smooth-Moon horizon | sqrt(2 R h1) + sqrt(2 R h2), R = 1,737.4 km | 2.64 km (0.5 m) to 5.27 km (2 m) | m | E1; [LUNARRF] |
| Path loss in line of sight | free space to d_b = 4 h1 h2 / lambda, then 40 log d - 20 log(h1 h2) | exponent 2-4 | dB | [HWU08]; E1 |
| Blocked path | knife-edge loss on the terrain profile, else no link | 6-20.5 | dB | ITU-R P.526 (Project note) |
| Regolith relative permittivity; loss tangent | 3.0; 0.01 | 2.7-3.7; 0.01-0.05 | - | [GRC23]; [HWU08]; [LUNARRF] |
| Transmit power: LTV, cargo / small / hopper / base | 1 / 0.25 / 0.5 / 5 | 0.1-5 | W | Project E48 (Assumed); [LUNARRF] 30 dBm, 23 dBm |
| Antenna gain | 3 | 0-6 | dBi | Project E48; [LUNARRF] 0 dBi |
| Receiver noise figure | 5 | 3-7 | dB | Project E48; [LUNARRF] 7 (device), 3 (base) |
| Noise temperature | 290 | 150-290 | K | Project E48; [LUNARRF] 150 K |
| Bandwidth: broadband / narrow-band | 1,000 / 25 | 12.5-20,000 | kHz | Project E48; Assumed |
| Link margin | 10 | 3-15 | dB | Project E48 |
| Narrow-band channel rate | 16 | 2, 8, 16, 64 | kbit/s | Project target; 2 kbit/s flown on CAPSTONE [SMALLSAT26]; Proximity-1 steps [P1-PHY] |
| Wi-Fi range | 300 | 100-500 | m | [LSR23] |
| LTE cell from a 10 m mast | 10 | 5-22 | km | [LSR23]; [LUNARRF] |
| Relay proximity rate: S-band / Ka-band | 100 / 10,000 down, 50,000 up | 0.05-100 / 1,000-50,000 | kbit/s | [ESPER25] reference design |
| Lunar Pathfinder user link | 2 x 2,700 | - | kbit/s | [SSTL24] |
| Relay in view, one satellite / three | 0.41 / 1.0 | 0.4-1.0 | share of time | [ESPER25] |
| Earth hidden without relay | 14 | 13-15 | days per month | [LSR23] |
| Earth round trip | 2.6 + 2.4 | - | s | Project |
| Range cap `d_max_m` | min(horizon, budget range of E1) instead of a fixed 5,000 | 1,000-10,000 | m | Project (provisional 5 km); E1 |
| Per-hop message loss | 0.10 | 0, 0.10, 0.25, 0.40 | - | Project `messages.py` |
| Mean loss burst | 10 | 1-100 | messages | Project (Assumed) |
| Hop latency | 10 | 5-100 | ms | Project (Assumed) |
| Relay hop limit | 5 | 1-8 | hops | LRIP |
| Channel access efficiency | 0.8 (scheduled) | 0.18 (ALOHA), 0.37 (slotted), 0.8 | - | E3 |
| Bundle overhead; with BPSec integrity | 48; 108 | 40-120 | B | E2; [RFC9171][RFC9173] |
| Bundle lifetime: award, grant / alert / logs | lease / `valid` / 14 d | 60 s-14 d | - | LRIP |
| Custody retransmission timer, surface | 10 | 3-60 | s | Assumed (implementation parameter) |
| Custody retransmission timer, via relay or Earth | 15 while in contact | 10-60 | s | Assumed: 2 x round trip + 5 s |
| DTN store per rover | 64 | 8-512 | MB | Assumed (manifest example) |
| POSITION / STATUS / INTENT on the air | 41 / 43 / 38 (MAC 8); 49 / 51 / 46 (MAC 16) | - | B | E2 |
| ALERT / TASK_BID / RESERVE_REQ / RELEASE / HELLO | 42 / 37 / 35 / 31 / 30 | - | B | E2 |
| TASK_AWARD / RESERVE_GRANT (signed) | 92 / 94 | - | B | E2; [RFC8032] |
| Capability manifest, compact and signed | 330 | 250-1,300 | B | C3 |
| Frame overhead (Proximity-1) | 12 | 0-12 | B per message | [P1-CS][P1-DLL] |
| POSITION rate | 1 | 0.1, 1, 10 | Hz | Project R9; LRIP |
| STATUS and INTENT rate | 0.1 | 0.02-1 | Hz | LRIP |
| Offered load per robot | 49 (MAC 8), 59 (MAC 16) | - | B/s | E3; Project measured 48 |
| MAC length | 8 (narrow-band), 16 (broadband) | 8, 16 (4 for sensitivity only; below the SDLS minimum) | B | [SDLS]; [NIST38B] |
| Anti-replay: freshness window; counter | 10 s; 32-bit | 2-60 s | - | LRIP; [SDLS-GB] |
| Site key rollover | 24 | 1-720 | h | Assumed; cap 2^32 uses for 64-bit GCM tags [NIST38D] |
| Forgery probability per attempt | 5.4 x 10^-20 (8 B); 2.9 x 10^-39 (16 B) | - | - | E4 |
| Innovation test false-alarm rate | 10^-3 per test | 10^-2 to 10^-5 | - | E5 |
| Threshold gamma (1 / 2 measurements) | 10.83 / 13.82 | 6.63-19.51 / 9.21-23.03 | - | E5 |
| Persistence rule | 3 of 5 | 2 of 3 to 4 of 5 | - | E5 |
| False suspect rate per pair | 10^-8 per window | - | - | E5 |
| Navigation error sigma_nav | 2 | 0.5-5 | m | Project R9 |
| Inter-rover ranging error | 0.3 | 0.1-5 | m | Assumed (UWB class; CADRE carries UWB, accuracy not public) |
| Smallest detectable position error (90 %) | 13 (sigma_nav 2 m), 6.6 (1 m) | - | m | E5 |
| Liars tolerated F; neighbours needed | 1; 3 | 0-2; 1-5 | - | [LEBLANC12] |
| Ledger voters for f = 1 | 4 | 4-7 | - | [LAMPORT82] |
| Lost link: T1 suspect / T2 isolate | 5 / 30 | 3-10 / 10-120 | s | LRIP |
| Lost link: T_hold | 600 | 60-3,600 | s | Project R7 |
| Lost link: T_rdv | 3,600 | 1,800-7,200 | s | Project auction timeout |
| Safe-mode beacon period | 60 | 10-600 | s | LRIP |
| Reservation grace (late) | 60 | 30-300 | s | Project R9 |
| Award claim timeout | 60 | 10-300 | s | LRIP |
| Leader re-election | 1,800 | 10-1,800 | s | Project (0.5 h); [CADRE25] reports 10 s |

---

## E. Proof sketches we can put in a paper

### E1. Link budget, two-ray ground model, radio horizon

**Equations.** Received power in dBm: P_r = P_t + G_t + G_r - L(d). Noise: N = -174 + 10 log10(B) + F (dBm, B in
Hz, 290 K). Margin M. Signal-to-noise ratio: SNR = P_r - N - M.

- Free space: L_fs = 20 log10(4 pi d f / c).
- Flat ground, direct ray plus one reflected ray with reflection coefficient -1 (the grazing limit): the two
  path lengths differ by about 2 h_t h_r / d, so
  P_r / P_t = G_t G_r (lambda / 4 pi d)^2 x 4 sin^2(2 pi h_t h_r / (lambda d)).
  For d much larger than h_t h_r / lambda the sine equals its argument and
  P_r / P_t = G_t G_r (h_t h_r)^2 / d^4, i.e. **L_pe = 40 log10(d) - 20 log10(h_t h_r)**, independent of
  frequency. NASA's lunar model shows exactly this 1/R^4 law and frequency independence [HWU08].
- Breakpoint (last maximum of the sine): **d_b = 4 h_t h_r / lambda**.
- Radio horizon without atmosphere: from (R + h)^2 = R^2 + d^2, **d_h = sqrt(2 R h)** (h much smaller than R),
  R = 1,737.4 km; two antennas see each other up to d_h1 + d_h2.

**Table E1 (Computed).**

| Antenna height (both ends) | 0.5 m | 1.0 m | 1.5 m | 2.0 m |
|---|---|---|---|---|
| Horizon of one antenna | 1.32 km | 1.86 km | 2.28 km | 2.64 km |
| Mutual horizon | 2.64 km | 3.73 km | 4.57 km | 5.27 km |
| Breakpoint at 0.4 GHz | 1.3 m | 5.3 m | 12 m | 21 m |
| Breakpoint at 2.4 GHz | 8 m | 32 m | 72 m | 128 m |
| Flat-ground loss at 1 km | 132.0 dB | 120.0 dB | 113.0 dB | 108.0 dB |
| Range for 1 Mbit/s, example A | 1.19 km | 2.37 km | 3.56 km | 4.74 km |
| Range for 16 kbit/s, example A | 3.64 km | 7.29 km | 10.9 km | 14.6 km |

**Worked example A (S-band, the E48 constants).** f = 2.4 GHz, P_t = 1 W = 30 dBm, G_t = G_r = 3 dBi, B = 1 MHz,
F = 5 dB, M = 10 dB. N = -174 + 60 + 5 = -109 dBm. Shannon capacity equals B (1 Mbit/s) at SNR = 0 dB, which
allows a loss of 30 + 6 + 109 - 10 = 135 dB. Under the flat-ground law d = sqrt(h_t h_r) x 10^(135/40) =
2,371 m x sqrt(h_t h_r): 4.74 km for two 2 m antennas, inside their 5.27 km horizon. For 16 kbit/s the needed
SNR is 2^0.016 - 1 = 0.011 = -19.5 dB, the allowed loss 154.5 dB and the range 14.6 km, far beyond the horizon.
**Conclusion: the coordination channel is limited by geometry; megabit links are limited by power.** This
reconciles the Project note ("range is set by geometry") with the 2026 atlas ("this range, not the terrain,
is what limits the coverage") [LUNARRF], which assumes a 20 MHz carrier.

**Worked example B (UHF fallback).** f = 0.4 GHz, 1 W, 0 dBi antennas, B = 25 kHz, F = 5 dB: N = -125 dBm. With
SNR = 10 dB and M = 10 dB the allowed loss is again 135 dB: 2.37 km at 1 m height, 4.75 km at 2 m, with a
capacity of 25 kHz x log2(11) = 86 kbit/s. Narrow-band UHF at 0 dBi reaches as far as 1 MHz S-band at 3 dBi.

**Check against E48 (Project).** At the 5 km worst hop E48 uses free-space loss, 114.0 dB. The flat-ground law
gives 132.0 dB for two 2.5 m antennas and 148.0 dB for two 1.0 m antennas. The Shannon rates become: LTV and
cargo 6,977 -> 1,574 kbit/s; small robot 5,011 -> 18 kbit/s; hopper 5,989 -> 36 kbit/s. Two 1 m antennas are
also beyond their 3.73 km smooth horizon at 5 km. The grazing-reflection assumption holds on rough ground when
the height variation is below lambda / (8 sin psi) with psi = (h_t + h_r) / d (Rayleigh criterion, textbook, not
from an opened source): 15.6 m at 2.4 GHz, 5 km, 2.5 m antennas.

### E2. Message size, byte by byte

1. Content of a position report: 24 + 24 + 16 + 12 + 10 + 8 + 3 + 1 + 6 = 104 bits = 13 bytes (table in C2).
2. LRIP header: 4 + 4 + 8 + 16 + 32 = 64 bits = 8 bytes.
3. Space Packet primary header: 3 + 1 + 1 + 11 + 2 + 14 + 16 = 48 bits = 6 bytes [SPP §4.1].
4. Security header: 16-bit SPI + 32-bit sequence number = 6 bytes, the SDLS telecommand baseline layout
   [SDLS Annex E2].
5. Security trailer: AES-CMAC truncated to 8 bytes, the shortest MAC SDLS allows and the NIST floor of 64 bits
   [SDLS Table 6-1][NIST38B]; or 16 bytes (SDLS baseline).
6. Total 13 + 8 + 6 + 6 + 8 = **41 bytes**; 49 bytes with the 16-byte MAC.
7. In a Proximity-1 frame: + 3 (sync marker) + 5 (frame header) + 4 (CRC-32) = 53 bytes [P1-CS][P1-DLL].
8. CBOR: the 12 values (4 header, 8 content) as one array encode to 33 bytes (1 byte array head; integers
   below 24 take 1 byte, below 256 2, below 65,536 3, below 2^32 5 [RFC8949]); + 6 + 14 = 53 bytes.
9. Protocol Buffers: one tag byte per field plus a varint of 1 to 5 bytes, signed values zig-zag coded
   [PROTOBUF]: 36 bytes; + 6 + 14 = 56 bytes.
10. BPv7 bundle around the 27-byte packet: 1 (array start) + 39 (primary block: array head 1, version 1, flags
    1, CRC type 1, destination 6 (node 200), source 7 (node 291), report-to 3, creation time 9 + sequence 1 +
    array head 1, lifetime
    5, CRC-16 3) + 7 (payload block: array head 1, type 1, number 1, flags 1, CRC type 1, length 2) + 1 (array
    end) = 48 bytes of overhead, 75 bytes in total [RFC9171 §4.3]. A BPSec integrity block with HMAC-SHA-256
    is 60 bytes (target list, context id, flags, source, parameter, 32-byte result) [RFC9172][RFC9173]:
    135 bytes in total.

STATUS, TASK_BID and ALERT follow the same steps with 120, 72 and 112 content bits (Table B5).

### E3. Channel capacity and the bit rate N rovers need

- Capacity: C = B log2(1 + SNR). A 16 kbit/s channel in 25 kHz needs SNR >= 2^(16/25) - 1 = 0.56 = -2.5 dB.
- Offered load: L = 8 x sum over message types of (rate x size) x N. With POSITION 1 Hz x 41 B, STATUS 0.1 Hz
  x 43 B, INTENT 0.1 Hz x 38 B: 49.1 B/s per robot; N = 20 gives L = 7.86 kbit/s (9.39 kbit/s with 16-byte
  MACs; 10.2 kbit/s with 8-byte MACs in Proximity-1 frames).
- Shared channel: every relayed copy is another transmission in the same band. With mean hop count h and
  access efficiency eta the channel rate must satisfy **R >= L x h / eta**.
- Slotted random access: with attempt rate G per slot the success rate is S = G e^-G, largest at G = 1 where
  S = 1/e = 0.368. A scheduled (time-division) channel with 20 % guard time has eta = 0.8.
- N = 20 at 1 Hz: h = 1, eta = 0.8: 9.8 kbit/s (fits 16). h = 1, eta = 0.37: 21 kbit/s (does not fit).
  h = 2, eta = 0.8: 19.7 kbit/s (does not fit). 10 Hz, h = 1, eta = 0.8: 82 kbit/s.
- Design consequence: 1 Hz position at one hop only (neighbours and mast); relayed copies are thinned to
  0.1 Hz; the narrow-band channel is scheduled by the base, with random access only for HELLO and ALERT.

### E4. Forged messages and replay

- *Forgery.* For an ideal t-bit MAC an attacker without the key succeeds with probability 2^-t per attempt
  [NIST38B App. A], and with at most q x 2^-t over q attempts (union bound). t = 64: 5.4 x 10^-20 per attempt;
  ten attempts a second for a year (3.2 x 10^8) give 1.7 x 10^-11. t = 32: 2.3 x 10^-10 per attempt and 0.07
  over the same year, which is why 4-byte codes are excluded. NIST's sizing rule is
  t >= log2(MaxInvalids / Risk).
- *Replay.* The receiver keeps, per sender and key, the highest sequence number s_max it has accepted and
  accepts a message only if (a) its MAC verifies, (b) s > s_max, and (c) |t_valid - now| <= 10 s. A recorded
  message has s <= s_max at every receiver that heard it or any later one, so it is rejected with certainty.
  A receiver that missed them can be fed the recording only within 10 s, and then learns a true but stale
  state; POSITION older than 2 s is not used for C8. The counter must never repeat under one key: 2^32
  messages last 136 years at 1 Hz and 13.6 years at 10 Hz, so key rollover is set by policy, not by the
  counter.
- *GCM limit.* If AES-GCM with 64-bit tags were used, a key must be replaced before 2^32 verifications
  [NIST38D]: 249 days at 200 messages a second site-wide. Beacons therefore use CMAC; GCM with full 16-byte
  tags is kept for encrypted bids.

### E5. Chi-square innovation test

**Statement.** Vehicle i measures z = h(p_i, p_j) + w, w ~ N(0, R), where p_j is the neighbour's true position.
It predicts z from its own estimate (covariance P_i) and the reported position (covariance P_j). If the
report is honest and errors are Gaussian and independent, the innovation v = z - h(p_i_hat, p_j_reported) is
N(0, S) with S = R + H_i P_i H_i^T + H_j P_j H_j^T, and d2 = v^T S^-1 v follows a chi-square law with m degrees
of freedom (m = number of scalar measurements). Reject when d2 > gamma = the (1 - alpha) quantile.

**Thresholds (Computed).** For m = 2 the quantile has the closed form gamma = -2 ln(alpha).

| alpha | 10^-2 | 10^-3 | 10^-4 | 10^-5 |
|---|---|---|---|---|
| m = 1 (range) | 6.63 | 10.83 | 15.14 | 19.51 |
| m = 2 (range and bearing, or 2-D fix) | 9.21 | 13.82 | 18.42 | 23.03 |
| m = 3 | 11.34 | 16.27 | 21.11 | 25.90 |

**Detectable error.** A report wrong by b shifts the innovation mean; d2 is then non-central chi-square with
parameter lambda = b^T H_j^T S^-1 H_j b. For m = 1 and alpha = 10^-3 the threshold is 3.29 sigma_v and an error
is caught with probability 0.9 when it reaches (3.29 + 1.28) sigma_v = 4.57 sigma_v (0.99: 5.62 sigma_v). For
m = 2: lambda = 23.8, i.e. 4.88 sigma. With range only, sigma_v^2 = sigma_r^2 + 2 sigma_nav^2 along the line
between the two vehicles:

| sigma_nav | sigma_r | sigma_v | Threshold (alpha 10^-3) | Detectable error (90 %) |
|---|---|---|---|---|
| 2.0 m | 0.3 m | 2.84 m | 9.4 m | 13.0 m |
| 1.0 m | 0.3 m | 1.45 m | 4.8 m | 6.6 m |
| 0.5 m | 0.1 m | 0.71 m | 2.4 m | 3.3 m |
| 2.0 m | 5.0 m | 5.74 m | 18.9 m | 26.3 m |

The Project's fixed tolerance e_conf = 3 sigma_nav + 5 m = 11 m sits between the threshold and the detectable
error of the first row. A single range sees only the error component along the line of sight; two witnesses
at different bearings, or a bearing measurement, close the gap.

**Persistence.** With independent tests, "k of n flagged" has false-alarm probability
sum over i >= k of C(n, i) alpha^i (1 - alpha)^(n - i): 3 of 5 gives 1.0 x 10^-8 at alpha = 10^-3 and
9.9 x 10^-6 at 10^-2. For 20 vehicles (190 pairs) at one window a second that is one false suspect in about
6 days (alpha 10^-3) against one every 9 minutes (alpha 10^-2). An error with per-test detection 0.9 is caught
by 3 of 5 with probability 0.99.

**Redundancy count (RAIM logic).** n independent ranges to one vehicle with 2 unknowns leave n - 2 degrees of
freedom in the least-squares residual: n >= 3 detects one inconsistent report, n >= 4 identifies it.

### E6. W-MSR resilience condition

**Algorithm.** At each step a normal node sorts the values received from its neighbours, removes the F
largest that exceed its own value and the F smallest that are below it (fewer if there are fewer), and sets
its value to a weighted average of the rest and its own.

**Safety (one line).** At most F neighbours lie. After trimming, any surviving value from a liar lies between
two values of normal nodes, so the update is a convex combination of values inside the current range
[m(t), M(t)] of the normal nodes: the range never grows, whatever the liars send.

**Agreement.** Let S_1 be the normal nodes at the maximum and S_2 those at the minimum. If the graph is
(F + 1, F + 1)-robust, one of the two sets contains a node with at least F + 1 neighbours outside its set (or
enough such nodes in total); after removing F values it still uses one outside value and moves strictly
inside. Repeating shrinks M(t) - m(t) to zero. Conversely, without that property the liars can hold two sets
apart for ever. Hence: with at most F malicious nodes in total, agreement is reached if and only if the graph
is (F + 1, F + 1)-robust; with at most F in every neighbourhood, (2F + 1)-robustness is sufficient; every node
needs at least 2F + 1 neighbours [LEBLANC12, Definition 12, Theorems 3 and 4, proved there for ARC-P].

**What the simulator can check.** For F = 1: every vehicle hears at least 3 others (necessary, cheap);
(2, 2)-robustness by enumerating subset pairs for fleets up to about 20. Report the share of time the mesh of
`RadioMesh.graph` meets each condition. For a ledger agreed without trusting timing, n >= 3f + 1 voters
[LAMPORT82]; with signatures and bounded delays fewer suffice.

### E7. Age of information over k store-and-forward hops

Age at the receiver: A(t) = t - u(t), where u(t) is the generation time of the newest update received
[YATES20]. Assume a source that samples every T seconds, k hops, per-hop delay D, each hop lost independently
with probability p and no retry (the model of `lunarsim/atc/messages.py`). An update arrives with probability
q = (1 - p)^k. The number G of periods between arrivals is geometric with mean 1/q and second moment
(2 - q)/q^2. For a renewal process the time-average age is the delay plus E[X^2] / (2 E[X]) with X = G T:

- **mean age = k D + T (2 - q) / (2 q)**; mean peak age = k D + T / q;
- **P(age > k D + m T) = (1 - q)^m**, so age <= k D + T x ceil(ln eps / ln(1 - q)) with probability 1 - eps.

| Loss per hop | k = 1 | k = 3 | k = 5 |
|---|---|---|---|
| 0 | 0.51 s; 1.0 s | 0.53 s; 1.0 s | 0.55 s; 1.1 s |
| 0.10 | 0.62 s; 3.0 s | 0.90 s; 6.0 s | 1.24 s; 8.1 s |
| 0.25 | 0.84 s; 5.0 s | 1.90 s; 13 s | 3.76 s; 26 s |
| 0.40 | 1.18 s; 8.0 s | 4.16 s; 29 s | 12.4 s; 86 s |

(T = 1 s, D = 10 ms; first number mean age, second the 99.9 % bound; Computed.) With DTN the hop delay is the
wait for the next contact W_j plus transfer time, and nothing is lost: age <= T + sum over hops of (W_j + D_j),
bounded by the longest gap in the contact plan. Forwarding the newest update first minimises age in multihop
networks [BEDEWY17], so relay queues are last-in-first-out for POSITION and first-in-first-out for bundles.
Consequence: the 2 s freshness needed by C8 holds for direct neighbours up to 25 % loss, not across 3 hops.

---

## F. Who to partner with

| Organisation | What it owns | What we would ask | Public URL | Realistic for a small team? |
|---|---|---|---|---|
| CCSDS (Space Link Services, Security, DTN and Wireless working groups) | Proximity-1, USLP, SDLS, BP, 883.0 | comments on LRIP as input to an experimental (orange) book on surface user-to-user messaging; an APID range through SANA | https://ccsds.org | Partly: only through a member agency or as an observer; a white paper is realistic |
| NASA SCaN and the LunaNet team | LNIS and its open documents AD3 (messages), AD6 (data services), AD8 (security); the Lunar Spectrum Manager | whether user-to-user surface messaging is in scope; band guidance for a narrow-band coordination channel | https://www.nasa.gov/communicating-with-missions/lunanet/ | Partly: public comments yes, joint work unlikely |
| ESA Moonlight (Telespazio consortium, SSTL for Lunar Pathfinder) | relay and navigation services from 2028 | user terminal interface, DTN service plans | https://www.esa.int/Applications/Connectivity_and_Secure_Communications/Moonlight | Low |
| Nokia Bell Labs | the lunar LTE system | propagation data, third-party device interface | https://www.nokia.com/bell-labs/ | Low |
| Intuitive Machines | relay service, landers, CADRE's ride | relay user guide; mesh statistics after IM-3 | https://www.intuitivemachines.com | Low |
| NASA Glenn (HDTN), NASA JPL (ION), NASA Goddard (bplib, BPNode) | DTN software, open source | nothing needed to start; bug reports and questions on small-bundle profiles | https://github.com/nasa/HDTN ; https://github.com/nasa-jpl/ION-DTN ; https://github.com/nasa/bplib | High |
| D3TN | uD3TN, embedded DTN | advice on a microcontroller profile | https://gitlab.com/d3tn/ud3tn | High |
| Open Robotics / Space ROS community | ROS 2, Space ROS | host an `lrip_msgs` package and a bridge; a talk | https://space.ros.org | High |
| ZettaScale | Zenoh, zenoh-pico | measurements over narrow-band serial links | https://zenoh.io | High for the open-source side |
| VDA / VDMA with KIT (VDA 5050); MassRobotics | the industrial precedents | lessons on versioning and conformance testing | https://github.com/VDA5050/VDA5050 ; https://github.com/MassRobotics-AMR/AMR_Interop_Standard | High |
| WPI (authors of LunarRF) | the south-pole coverage atlas | atlas cells for our site; a check of the flat-ground law against their solver | https://arxiv.org/abs/2610.34554 | High (academic) |
| JPL CADRE team | the only multi-rover flight system | measured message loss and re-election times | https://www-robotics.jpl.nasa.gov | Medium |

---

## G. Open questions, risks, findings against the existing notes, and sources

### G1. Open questions and risks

1. No in-situ measurement of surface-to-surface path loss exists for the Moon. Every range in this note is a
   model. The two-ray law is supported by one NASA study [HWU08]; the atlas [LUNARRF] is a preprint.
2. No frequency is allocated for surface links. WRC-27 decides; the 2.4 GHz region must protect the navigation
   band at 2483.5-2500 MHz; UHF is barred from the far side. A narrow-band coordination channel has no home in
   the current recommendation other than the Proximity-1 UHF pairs.
3. Who is the trust anchor on a site with several agencies and companies? LunaNet's security document is still
   a placeholder. Our "base as certificate authority" is an assumption.
4. A shared site key authenticates outsiders only. Insider protection for beacons needs TESLA (needs loose time
   synchronisation, RFC 4082) or signatures (64 bytes each). We chose detection (C8) over prevention; the cost
   and benefit of TESLA should be simulated.
5. SDLS does not cover Proximity-1 frames; our message-level security copies the SDLS layout but is not SDLS.
   Standardisation would need a CCSDS decision.
6. BPv7 overhead (48 to 108 bytes) is large for small messages. Aggregating many LRIP packets in one bundle is
   the obvious fix and is not yet specified.
7. Custody transfer for BPv7 is a CCSDS extension still in draft (publication unverified); timer values are
   ours.
8. The chi-square test assumes independent Gaussian errors. Cooperative localisation correlates the errors of
   neighbours; the false-alarm rate must be measured in simulation, and a learned detector compared with it.
9. W-MSR needs 3 neighbours for one liar. With one mast covering 10-24 % of the area and 5 km links, how often
   does the mesh meet that? Not yet measured.
10. The RETURN and RENDEZVOUS steps move a vehicle that cannot ask for a reservation. Whether that is safer
    than staying put depends on energy and terrain; it must be an experiment, not a default taken on faith.
11. Post-quantum signatures do not fit the narrow-band channel; enrolment must happen on the broadband link.
12. Hoppers break the ground-vehicle assumptions (speed field, plume alerts, landing closures of their own).

### G2. Findings that differ from the existing notes or code

1. **E48 link budget.** It uses free-space loss at the 5 km worst hop (6,976 / 5,010 / 5,988 kbit/s). With the
   flat-ground law the rates are about 1,570 / 18 / 36 kbit/s, and two 1 m antennas cannot see each other at
   5 km on a smooth Moon (3.73 km). H10 still holds for the 7.68 kbit/s load, with a factor 2.4 instead of 650
   for the small robot.
2. **E48 traffic.** 7.68 kbit/s is the load generated at the sources. Airtime on a shared channel is that
   times the hop count divided by the access efficiency: 20 kbit/s for two hops on a scheduled channel.
   Authentication adds 14 to 22 bytes per message, yet the per-robot total (49 B/s) matches E48's 48 B/s
   because its 48-byte status was generous. RELEASE (31 against 16), AWARD (92 against 32) and GRANT (94
   against 32) are larger than assumed.
3. **`radio.py` defaults.** A 5 km range with zero clearance margin and no Fresnel requirement is optimistic
   for 1.0 m antennas; use the E1 range and a clearance or two-ray term.
4. **"Range is set by geometry, not by radio power"** (existing note). True for the narrow-band channel; for
   megabit links the 2026 atlas finds the opposite. Both are consistent with E1.
5. **"LunaNet does not standardise the radio link between surface vehicles."** Still true of LNIS v5. But
   CCSDS 883.0-B-2 (May 2024) does: Wi-Fi 6 and LTE Release 12. The existing note names 802.11n; the standard
   allows 802.11n only where Wi-Fi 6 is not possible. The missing piece is the application layer.
6. **DTN status.** The existing note has no lunar DTN flight after KPLO. CAPSTONE flew BPv7 with custody
   transfer in NASA's core Flight System in lunar orbit (announced 6 July 2026). Still nothing on the surface.
7. **Nokia.** The primary release (not opened before) gives both causes: no power for a call, and a hopper
   radio too cold to connect. The band was 1.8 GHz, outside the SFCG surface list.
8. **Leader re-election.** The Project assumes 0.5 h; CADRE's flight design re-elects within 10 s.
9. **`messages.py` loss levels.** At 40 % loss over 3 hops the mean age of a 1 Hz beacon is 4.2 s and the
   99.9 % bound 29 s: within R9's 60 s lateness, far outside the 2 s a cross-check needs.
10. **Dates.** Chang'e-7 slipped to 2027; Lunar Pathfinder is "NET 2027"; VDA 5050 is at 3.0.0 since March 2026.

### G3. Could not be verified

CCSDS 734.2-B-2 (BPv7 blue book) publication; the IOAG lunar architecture report (download failed); FIPA
Contract Net and JAUS primary texts (sites blocked); STANAG 4586 details; the W-MSR journal paper (paywalled;
conditions taken from the authors' open report); a UHF channel on Lunar Pathfinder; CADRE's radio band and
rates; any commercial rover's protocol; post-quantum rekeying papers for SDLS (found, not opened); the ROS 2
interface documentation page (blocked a scripted fetch); the Rayleigh roughness criterion and the ALOHA
result are textbook items stated with their derivation or flagged.

### G4. Sources (all opened 11 November 2026)

**CCSDS** (titles, issues and dates in Table B2; files under https://public.ccsds.org/Pubs/):
[P1-PHY] `211x1b4e1.pdf`; [P1-DLL] `211x0b6e1.pdf`; [P1-CS] `211x2b3.pdf`; [SPP] `133x0b2e2.pdf`;
[AOS] `732x0b4.pdf`; [USLP] `732x1b3e1.pdf`; [SDLS] `355x0b2.pdf`; [SDLS-EP] `355x1b1.pdf`;
[CRYPTO] `352x0b2.pdf`; [CFDP] `727x0b5e1.pdf`; [BP6] `734x2b1.pdf`; [LTP-C] `734x1b1.pdf`;
[SABR] `734x3b1.pdf`; [TMSC] `131x0b5.pdf`; [WPN] `883x0b2.pdf`; [XTCE] `660x0b2.pdf`; [SEDS] `876x0b1.pdf`;
[SDLS-GB] CCSDS 350.5-G-2, SDLS Concept and Rationale (green book), Jan 2024, `350x5g2.pdf`;
[THREAT] CCSDS 350.1-G-3, Security Threats against Space Missions, Feb 2022, `350x1g3.pdf`;
[CCSDS-WEB] blue-book and review listing, https://ccsds.org/publications/bluebooks/

**LunaNet, spectrum, relays, lunar links**
- [LNIS5] NASA, ESA, JAXA, LunaNet Interoperability Specification, LNIS V005, 29 Jan 2025.
  https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf
- [SFCG24] C. Sham (NASA), Lunar Spectrum Overview and World Radio Conference Update, ICG, Jun 2024.
  https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_02_01.pdf
- [SFCG25] B. Espinosa (SFCG), Spectrum framework for Lunar PNT, 12 Feb 2025. https://ioag.org (Cislunar PNT
  Workshop, session 2, file `01 IOAG-ICG on Lunar PNT-Feb2025-SFCG.pdf`)
- [SFCG26] C. Sham, Update on the spectrum regulatory framework for Lunar PNT, 10-13 Feb 2026. https://ioag.org
  (Cislunar2026, Thursday, session 05, file `0900 2026 PNT Workshop-updates on spectrum ... FEB 2026.pdf`)
- [LSR23] Scardelletti et al., Lunar Surface Relay, ICSSC 2023. https://ntrs.nasa.gov/citations/20230013361
- [ESPER25] Esper et al., LCRNS, SpaceOps 2025. https://ntrs.nasa.gov/citations/20250003321
- [HWU08] Hwu, Upanavage, Sham (NASA JSC), Lunar Surface Propagation Modeling and Effects on Communications,
  2008. https://ntrs.nasa.gov/citations/20080015374
- [GRC23] Johnson, Eckman, Swank, Zemba (NASA GRC), RF Metrology of Lunar Highlands Regolith Simulant
  NU-LHT-2M, 2023. https://ntrs.nasa.gov/citations/20230013296
- [LUNARRF] Santorelli, Wyglinski (WPI), LunarRF: A Terrain-Aware Propagation Engine and Pole-Wide 3GPP Surface
  Coverage Atlas of the Lunar South Pole, preprint, 19 Oct 2026. https://arxiv.org/abs/2610.34554
- [NOKIA25] Nokia, press release of 10 Mar 2025. https://www.nokia.com/newsroom/nokia-and-intuitive-machines-deliver-first-cellular-network-to-the-moon-achieve-some-key-mission-objectives/
- [SSTL24] B. Hooper (SSTL), Lunar Comm/Nav slides, Dec 2024.
  https://bsgn.esa.int/wp-content/uploads/2024/12/Ben-Hooper_-Lunar-Comm-Nav-Session.pdf
- [WIKI-LP] https://en.wikipedia.org/wiki/Lunar_Pathfinder (edit of 14 Oct 2026);
  [WIKI-QQ2] https://en.wikipedia.org/wiki/Queqiao-2
- [SCIAM-CE7] Scientific American, 20 Aug 2026, updated 24 Aug 2026.
  https://www.scientificamerican.com/article/chinas-change-7-moonshot-will-seek-water-ice-at-the-lunar-south-pole/
- [ESA-ML] ESA, Moonlight programme page, 15 Oct 2024. https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration
- [3GPP-NTN] https://www.3gpp.org/technologies/ntn-overview ;
  [ICSIS] https://www.internationaldeepspacestandards.com/

**DTN**
- [RFC9171] Bundle Protocol Version 7; [RFC9172] BPSec; [RFC9173] Default Security Contexts; [RFC9174] TCP
  Convergence Layer v4 (all Jan 2022); [RFC5326] LTP (2008). https://www.rfc-editor.org/rfc/rfcNNNN.txt
- [NASA-DTN] NASA, Delay/Disruption Tolerant Networking (updated 15 Oct 2026).
  https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/
- [NASA-CAP] NASA, CAPSTONE completes extended mission, 6 Jul 2026.
  https://nasa.gov/technology/space-comms/nasas-capstone-completes-extended-mission-testing-lunar-technologies
- [SMALLSAT26] Garcia-Beech et al. (NASA GSFC), Delay/Disruption Tolerant Networking in Cislunar Space,
  SmallSat 2026 (abstract page). https://digitalcommons.usu.edu/smallsat/2026/all2026/42
- [HYLTON24] Hylton et al., The ISS, Optical Communications, and DTN, ICSSC 2024.
  https://ntrs.nasa.gov/citations/20240011759
- [DUDUKOVICH25] Dudukovich, Fraire, Evolution of Interplanetary Internet, SpaceOps 2025.
  https://ntrs.nasa.gov/citations/20250002486
- READMEs: [HDTN] https://github.com/nasa/HDTN ; [ION] https://github.com/nasa-jpl/ION-DTN ;
  [BPLIB] https://github.com/nasa/bplib ; [UD3TN] https://gitlab.com/d3tn/ud3tn

**Middleware, encodings, capability descriptions**
- [RTPS] OMG DDSI-RTPS 2.5. https://www.omg.org/spec/DDSI-RTPS/2.5/PDF ; [XTYPES] OMG DDS-XTypes 1.3 (about
  page only). https://www.omg.org/spec/DDS-XTypes/1.3/About-DDS-XTypes
- [ZENOH23] Liang, Yuan, Lin, A Performance Study on the Throughput and Latency of Zenoh, MQTT, Kafka, and
  DDS, 2023. https://arxiv.org/abs/2303.09419
- [ZENOH-PICO] Zenoh blog, 9 Jun 2022. https://zenoh.io/blog/2022-06-09-zenoh-pico-above-and-beyond/
- [ROS-DISC21] Open Robotics Discourse, 23 Mar 2021.
  https://discourse.openrobotics.org/t/minimising-ros2-discovery-traffic/19614
- [MQTTSN] MQTT-SN Protocol Specification 1.2.
  https://www.oasis-open.org/committees/download.php/66091/MQTT-SN_spec_v1.2.pdf
- [RFC7252] CoAP; [RFC8949] CBOR; [RFC8610] CDDL. https://www.rfc-editor.org/rfc/rfcNNNN.txt
- [PROTOBUF] Protocol Buffers encoding guide. https://protobuf.dev/programming-guides/encoding/ (read from the
  repository source `protocolbuffers.github.io/content/programming-guides/encoding.md`)
- [X691] ITU-T X.691 (record page). https://www.itu.int/rec/T-REC-X.691
- [MAVLINK] MAVLink guide: Packet Serialization; Message Signing.
  https://github.com/mavlink/mavlink-devguide/tree/master/en/guide
- [MCP] Model Context Protocol specification, revision 2025-11-25, Tools.
  https://github.com/modelcontextprotocol/modelcontextprotocol (docs/specification/2025-11-25/server/tools.mdx)
- [VDA5050] VDA and VDMA, VDA 5050 version 3.0.0, 19 Mar 2026. https://github.com/VDA5050/VDA5050
- [MASSROB] MassRobotics AMR Interoperability Standard. https://github.com/MassRobotics-AMR/AMR_Interop_Standard
- [OPCUA-R] OPC 40010-1 v1.02, 8 Sep 2025. https://reference.opcfoundation.org/Robotics/v100/docs/
- [IEEE1872] IEEE 1872-2015 (record page). https://standards.ieee.org/ieee/1872/5354/
- [JAUS-W] https://en.wikipedia.org/wiki/JAUS ; [SPACEROS] https://space.ros.org/
- [CADRE25] Rossi et al. (JPL), Planning, scheduling, and execution on the Moon: the CADRE technology
  demonstration mission, 2025. https://arxiv.org/abs/2502.14803
- [CADRE-SW] JPL Robotics, CADRE software page. https://www-robotics.jpl.nasa.gov (flight projects, CADRE)
- [CADRE-AAMAS] JPL slides. https://ai.jpl.nasa.gov/public/documents/presentations/CADRE-AAMAS-Slides.pdf
- [VIPER24] T. Fong (NASA Ames), VIPER briefing, 2024. https://ntrs.nasa.gov/citations/20240013292
- [VIPER-XTCE] XTCE as a Unifying Model for Flight and Ground Software, SpaceOps 2025.
  https://ntrs.nasa.gov/citations/20250003286

**Security**
- [NIST38B] NIST SP 800-38B (CMAC). https://doi.org/10.6028/NIST.SP.800-38B
- [NIST38D] NIST SP 800-38D (GCM).
  https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf
- [FIPS203] ML-KEM; [FIPS204] ML-DSA; both 13 Aug 2024. https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf
  and `NIST.FIPS.204.pdf`
- [RFC8032] EdDSA; [RFC4082] TESLA. https://www.rfc-editor.org/rfc/rfcNNNN.txt
- [USCC11] U.S.-China Economic and Security Review Commission, 2011 Annual Report, PDF page 224.
  https://www.uscc.gov/sites/default/files/annual_reports/annual_report_full_11.pdf
- [VIASAT22] Viasat, KA-SAT network cyber attack overview, 2022.
  https://www.viasat.com/perspectives/corporate/2022/ka-sat-network-cyber-attack-overview/

**Fault detection, consensus, age of information**
- [LEBLANC12] LeBlanc, Zhang, Sundaram, Koutsoukos, Consensus of Multi-Agent Networks in the Presence of
  Adversaries Using Only Local Information, 2012. https://arxiv.org/abs/1205.3676
- [SAULNIER22] Saulnier, Zhou, Pappas, Kumar, Resilient Consensus via Voronoi Communication Graphs, 2022.
  https://arxiv.org/abs/2209.04381
- [WARDEGA23] Wardega, von Hippel, et al., Byzantine Resilience at Swarm Scale, 2023.
  https://arxiv.org/abs/2301.06977
- [PROROK21] Prorok et al., Beyond Robustness: A Taxonomy of Approaches towards Resilient Multi-Robot Systems,
  2021. https://arxiv.org/abs/2109.12343
- [KHOSRAVI26] Khosravi, Ventura, Basiri, Robust Cooperative Localization in Featureless Environments, 2026.
  https://arxiv.org/abs/2603.09886
- [LAMPORT82] Lamport, Shostak, Pease, The Byzantine Generals Problem, 1982.
  https://lamport.azurewebsites.net/pubs/byz.pdf
- [NAVIPEDIA] ESA Navipedia, RAIM, 2011. https://gssc.esa.int/navipedia/index.php?title=RAIM
- [YATES20] Yates et al., Age of Information: An Introduction and Survey, 2020. https://arxiv.org/abs/2007.08564
- [BEDEWY17] Bedewy, Sun, Shroff, The Age of Information in Multihop Networks, 2017.
  https://arxiv.org/abs/1712.10061

**Lost link**
- [FAA16] FAA Notice N JO 7110.724, UAS Lost Link, 11 Oct 2016.
  https://www.faa.gov/documentLibrary/media/Notice/N_JO_7110.724_5-2-9_UAS_Lost_Link.pdf
- [CFR91185] 14 CFR 91.185. https://www.govinfo.gov/link/cfr/14/91?sectionnum=185&year=mostrecent&link-type=xml
- [PX4] PX4 Autopilot, Safety (Failsafe) Configuration.
  https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/config/safety.md
- [WIKI-SAFE] https://en.wikipedia.org/wiki/Safe_mode_(spacecraft)

**Project files read:** `research_notes/Lunar ATC/vehicles_comms_internals.md` (section 2, Table A);
`research_notes/Lunar ATC/traffic_and_safety.md` (rules R1-R10);
`research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`;
`research_notes/Lunar Rover Interaction Protocol/00_inputs_from_owner.md`; `data/scenarios/E48-design.json`;
`lunarsim/comms.py`; `lunarsim/atc/radio.py`, `messages.py`, `safety.py`, `auction.py`.


---

## Addendum, 12 November 2026: diffraction over a smooth Moon (added by LEAD from BACKEND's B-104 check)

**Diffraction over a smooth Moon: ITU-R P.526-16, *Propagation by diffraction* (11/2025, in force), §§ 3.1.1.2 and 3.2.** Opened 12 Nov 2026, itu.int (PDF in `.cache/external/itu/`). Used for E48's "spherical ground" column (B-104; `lunarsim.atc.radio.spherical_loss_db`). a_e = the Moon's radius, 1,737.4 km (no atmosphere, so no effective-radius factor).
- §3.1.1.2, field relative to free space: 20 log(E/E₀) = F(X) + G(Y₁) + G(Y₂) (13). Practical units (f MHz, a_e km, d km, h m):
  - X = 2.188 β f^(1/3) a_e^(−2/3) d (14a); Y = 9.575×10⁻³ β f^(2/3) a_e^(−1/3) h (15a).
  - F(X) = 11 + 10 log X − 17.6 X for X ≥ 1.6 (17a); −20 log X − 5.6488 X^1.425 for X < 1.6 (17b).
  - G(Y) = 17.6 (B − 1.1)^(1/2) − 5 log(B − 1.1) − 8 for B > 2 (18); 20 log(B + 0.1 B³) for B ≤ 2 (18a); B = βY (18b); G not below 2 + 20 log K.
  - β = 1 for horizontal polarization at all frequencies and for vertical polarization above 20 MHz over land.
  - K (11a): for regolith (ε ≈ 3) at 2.4 GHz, K ≈ 0.0016, so the G floor (≈ −54 dB) does not bind. The text says the formulae hold for 0.001 < K < 1.
  - Accurate to 2 dB when X − (βY₁)^½ Δ(Y₁,K) − (βY₂)^½ Δ(Y₂,K) > X_lim (19).
- §3.2, any distance, 10 MHz and above (self-consistent units):
  - marginal line-of-sight distance d_los = √(2a_e)(√h₁ + √h₂) (21); if d ≥ d_los, use §3.1.1;
  - otherwise the clearance h = [(h₁ − d₁²/2a_e) d₂ + (h₂ − d₂²/2a_e) d₁] / d (22), with d₁ = d(1 + b)/2, d₂ = d − d₁, b = 2√((m+1)/3m) cos(π/3 + ⅓ arccos((3c/2)√(3m/(m+1)³))), c = (h₁ − h₂)/(h₁ + h₂), m = d² / (4a_e(h₁ + h₂)) (22a–e);
  - h_req = 0.552 √(d₁d₂λ/d) (23); if h > h_req, the loss is 0;
  - else a_em = 0.5 (d / (√h₁ + √h₂))² (24), A_h = −20 log(E/E₀) by §3.1.1 with a_em, and A = (1 − h/h_req) A_h (25), with A = 0 if A_h < 0.
- **Values at 2.4 GHz** (loss = free space + A):
  - 2.5–2.5 m at 5 km: A = 23.0 dB, 137.0 dB (flat two-ray 132.0);
  - 1.0–1.0 m at 3.73 km: A = 35.1 dB, 146.6 dB (flat 142.9);
  - 10–1.0 m at 5 km: A = 17.3 dB, 131.4 dB (flat 128.0);
  - 2.5–2.5 m at 1 km: 104.1 dB, equal to the flat law.
