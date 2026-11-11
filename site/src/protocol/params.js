// /protocol/ (F-60): every number the page shows, with its flag and source. Isomorphic: the page text reads these at
// build time (<!--@pn:key--> in protocol/index.html, vite.config.js) and the figures read them in the browser, so a
// number is written once. Sources are the research notes in research_notes/Lunar Rover Interaction Protocol/
// (N01 positioning and time, N02 map, N03 comms, protocol and security, N04 coordination and market); the bracketed
// keys are those notes' source lists. Flags: Measured = on the Moon, on Mars or in an Earth test; Spec = a published
// requirement or design value; Modelled = our own calculation or simulation; Assumed = no source, varied in sweeps.
// Until BACKEND's B-99 exports land, the figures compute from these values (each figure says so).

const N01 = 'research note 01 (positioning and time)', N02 = 'research note 02 (shared map)';
const N03 = 'research note 03 (communication, protocol, security)', N04 = 'research note 04 (coordination, market)';

export const P = {
  // 1. positioning
  dr_vo: { value: 2, unit: ' % of distance', flag: 'Measured', digits: 0, source: `${N01}, D: dead reckoning with visual odometry and a star tracker, Earth field tests [MAIM07]` },
  dr_wheel: { value: 10, unit: ' % of distance', flag: 'Measured', digits: 0, source: `${N01}, D: wheel odometry and gyro on loose soil or slopes, Earth tests [HELM06]` },
  lrv_lo: { value: 0.3, unit: '', flag: 'Measured', digits: 1, source: `${N01}, A3: Apollo rover end-of-traverse errors [LRV73]` },
  lrv_hi: { value: 4, unit: ' %', flag: 'Measured', digits: 0, source: `${N01}, A3: Apollo rover end-of-traverse errors [LRV73]` },
  fix_terrain: { value: 1.7, unit: ' m', flag: 'Spec', digits: 1, source: `${N01}, D: terrain-matching fix, 1 sigma (5 m at 3 sigma) [DAF23]` },
  fix_every: { value: 100, unit: ' m', flag: 'Assumed', digits: 0, source: `${N01}, D: distance between terrain-fix chances in sunlit highlands` },
  uwb: { value: 0.3, unit: ' m', flag: 'Measured', digits: 1, source: `${N01}, D: radio (UWB) two-way range error, line of sight, Earth tests [PLANS18, NUCH24]` },
  uwb_range: { value: 100, unit: ' m', flag: 'Assumed', digits: 0, source: `${N01}, D: UWB maximum range (no lunar value is public)` },
  lans: { value: 10, unit: ' m', flag: 'Spec', digits: 0, source: `${N01}, D: LunaNet navigation service with a map height, 95 % [INTEROP25, LDN25, ML24]` },
  lans_2030: { value: 60, unit: ' % of the time', flag: 'Assumed', digits: 0, source: `${N01}, D: share of time a LunaNet fix is available in 2030 (Moonlight: 15 of 24 hours) [ML24, ESA24]` },
  gyro: { value: 3, unit: '°/h', flag: 'Measured', digits: 0, source: `${N01}, D: heading drift with gyros alone, measured on Mars [MAIM07]` },
  star_hdg: { value: 0.1, unit: '°', flag: 'Assumed', digits: 1, source: `${N01}, D: heading error with a star tracker, bounded ("a small fraction of a degree" [DAF23])` },
  sun_hdg: { value: 1, unit: '°', flag: 'Measured', digits: 0, source: `${N01}, D: heading error with a sun sensor, sunlit only, Earth tests [DEANS05]` },
  vo_fail: { value: 4, unit: ' %', flag: 'Measured', digits: 0, source: `${N01}, D: share of visual-odometry updates that fail, on Mars [MAIM07]` },
  sigma_nav: { value: 2, unit: ' m', flag: 'Assumed', digits: 0, source: `${N03}, D: navigation error the rules of the road assume (project rule R9)` },
  // 2. map
  tiles: { value: 3906, unit: ' tiles', flag: 'Modelled', digits: 0, source: `${N02}, E4: a 16 km site in 256 m tiles, (16,000 / 256) squared` },
  changed: { value: 42, unit: ' tiles', flag: 'Assumed', digits: 0, source: `${N02}, E4: half of the 84 tiles the haul legs cross change in a day` },
  digest: { value: 8072, unit: ' B', flag: 'Modelled', digits: 0, source: `${N02}, E4: hash-tree walk to 42 changed tiles, 8 (1 + 4 x 42 x 6) bytes` },
  hazard_kb: { value: 86, unit: ' kB', flag: 'Modelled', digits: 0, source: `${N02}, E4: 42 hazard tiles of 2,048 B` },
  trav_kb: { value: 495, unit: ' kB', flag: 'Modelled', digits: 0, source: `${N02}, E4: 42 traversability tiles of 11,796 B` },
  elev_kb: { value: 1376, unit: ' kB', flag: 'Modelled', digits: 0, source: `${N02}, E4: 42 rover-elevation tiles of 32,768 B` },
  full_kb: { value: 2875, unit: ' kB', flag: 'Measured', digits: 0, source: `${N02}, E4: the 5 m elevation layer of the whole site, 2,874,671 B (file size)` },
  frame_m: { value: 660, unit: ' m', flag: 'Modelled', digits: 0, source: `${N02}, A1: the same numbers read in the wrong lunar frame (ME against PA) at the south pole [NAIF-FK, E1]` },
  // 3. time
  tcxo: { value: 35, unit: ' ms a day', flag: 'Measured', digits: 0, source: `${N01}, D: crystal oscillator, 4 x 10^-7, measured on the Moon by LuGRE [LUGRE26]` },
  csac: { value: 26, unit: ' µs a day', flag: 'Spec', digits: 0, source: `${N01}, D: chip-scale atomic clock, 3 x 10^-10, data sheet [CSAC]` },
  rel: { value: 56.02, unit: ' µs a day', flag: 'Measured', digits: 2, source: `${N01}, A6: a clock on the Moon runs fast against one on Earth [ASH24, KK24, TUR25]` },
  need_stamp: { value: 10, unit: ' ms', flag: 'Modelled', digits: 0, source: `${N01}, D and E6: time-stamp error allowed on a position report` },
  need_resv: { value: 0.1, unit: ' s', flag: 'Modelled', digits: 1, source: `${N01}, A7: road reservations with seconds of margin` },
  ns_m: { value: 0.3, unit: ' m', flag: 'Modelled', digits: 1, source: `${N01}, A7: 1 ns of clock error is 0.3 m of one-way range (speed of light)` },
  // 4. communication (the engine's link budget, lunarsim/atc/radio.py, values from N03 D)
  tx_w: { value: 1, unit: ' W', flag: 'Assumed', digits: 0, source: `${N03}, D: transmit power of a cargo rover (project E48)` },
  gain: { value: 3, unit: ' dBi', flag: 'Assumed', digits: 0, source: `${N03}, D: antenna gain each end (project E48)` },
  nf: { value: 5, unit: ' dB', flag: 'Assumed', digits: 0, source: `${N03}, D: receiver noise figure (project E48)` },
  margin: { value: 10, unit: ' dB', flag: 'Assumed', digits: 0, source: `${N03}, D: link margin (project E48)` },
  rate: { value: 16, unit: ' kbit/s', flag: 'Assumed', digits: 0, source: `${N03}, D: coordination channel rate the link must carry (project target)` },
  ridge_lo: { value: 6, unit: '', flag: 'Modelled', digits: 0, source: `${N03}, D: knife-edge loss of a ridge in the path, ITU-R P.526` },
  ridge_hi: { value: 20, unit: ' dB', flag: 'Modelled', digits: 0, source: `${N03}, D: knife-edge loss of a ridge in the path, ITU-R P.526` },
  bp_bytes: { value: 48, unit: ' B', flag: 'Modelled', digits: 0, source: `${N03}, A3 and E2: Bundle Protocol overhead per message [RFC9171]` },
  // 5. protocol
  pos_payload: { value: 13, unit: ' B', flag: 'Modelled', digits: 0, source: `${N03}, C2: POSITION payload, 104 bits` },
  pos_air: { value: 41, unit: ' B', flag: 'Modelled', digits: 0, source: `${N03}, C2: POSITION on the air with headers and an 8-byte authentication code` },
  load_1hz: { value: 6.6, unit: ' kbit/s', flag: 'Modelled', digits: 1, source: `${N03}, A9: 20 rovers sending POSITION once a second` },
  load_10hz: { value: 66, unit: ' kbit/s', flag: 'Modelled', digits: 0, source: `${N03}, A9: 20 rovers sending POSITION ten times a second` },
  manifest: { value: 250, unit: ' B', flag: 'Modelled', digits: 0, source: `${N03}, A7 and C3: a capability manifest in compact binary` },
  // 6. coordination
  t_suspect: { value: 5, unit: ' s', flag: 'Assumed', digits: 0, source: `${N03}, D: silence before a neighbour is suspect (lost-link rule T1)` },
  t_isolate: { value: 30, unit: ' s', flag: 'Assumed', digits: 0, source: `${N03}, D: silence before a neighbour is treated as lost (T2)` },
  t_claim: { value: 60, unit: ' s', flag: 'Assumed', digits: 0, source: `${N03}, D: time a winner has to claim an awarded job` },
  cadre_leader: { value: 10, unit: ' s', flag: 'Measured', digits: 0, source: `${N04}, A4: CADRE elects a new leader within 10 s (Earth tests) [CADRE25]` },
  earth_wait: { value: 54, unit: ' h', flag: 'Modelled', digits: 0, source: `${N04}, A4 and E.5: expected extra delay at our base if a failure decision waits for Earth` },
  wait_planner: { value: 14.9, unit: ' h', flag: 'Modelled', digits: 1, source: `${N04}, A2: urgent wait with a planner on the Moon, the same as a full-information marketplace (paper P1)` },
  wait_earth: { value: 89.9, unit: ' h', flag: 'Modelled', digits: 1, source: `${N04}, A2: extra wait when the dispatcher on Earth stops as Earth sets (paper P1)` },
  // 7. integrity
  gamma1: { value: 10.83, unit: '', flag: 'Modelled', digits: 2, source: `${N03}, C8: chi-square threshold for one range, false alarm 10^-3 per test` },
  min_err: { value: 13, unit: ' m', flag: 'Modelled', digits: 0, source: `${N03}, D: smallest position error caught 90 % of the time with a 2 m navigation error` },
};
