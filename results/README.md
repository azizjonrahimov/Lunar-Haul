# Raw experiment results

One CSV per experiment suite, one row per simulated year (one seed of one cell). Produced by
`experiments/run_all.py`; summarised into `table_*.csv` by `experiments/make_figures.py`.

| File | Suite | Cell factors (columns) |
|---|---|---|
| `E1_phases.csv` | Main comparison | `phase`, `mechanism` |
| `E2_fleet_size.csv` | Fleet-size sweep at Phase-2 demand | `n_vehicles`, `mechanism` |
| `E3_thickness.csv` | Owners sharing one fleet | `n_companies`, `other_duty`, `mechanism` |
| `E4_heavy_cargo.csv` | Fleet composition and team lift | `phase`, `fleet`, `mechanism` |
| `E5_autonomy_latency.csv` | Autonomy level, latency, operators | `autonomy`, `rtt_s`, `n_operators` |
| `E6_standards.csv` | Interface-standard compatibility | `common_share`, `mechanism` |
| `E7_environment.csv` | Night, reliability, bulk flows | `factor`, `level`, `mechanism` |
| `E8_ablations.csv` | Marketplace components removed; batching window | `phase`, `variant`, `batch_h` |
| `E9_search.csv`, `E9_test.csv`, `E9_best.json` | Auction-weight search and transfer test | `config` / `weights`, `phase` |
| `E10_tornado_sim.csv` | Cost sensitivities | `factor`, `level` |
| `E11_anticipation.csv` | Anticipatory staging on/off | `phase`, `n_vehicles`, `mechanism` |
| `E12_capacity_ladder.csv` | Movable share of landed mass by capacity | `phase`, `capacity_kg` |
| `E13_fragmentation_law.csv` | In-house service vs effective vehicles per owner | `N`, `k`, `other_duty`, `eff_per_owner`, `mechanism` |
| `E14_precision.json`, `E14_precision_long.json`, `E14_precision_*.csv.gz` | Sequential replication of the Phase-2 cells (4,000-cap run and extended run to a 1% 99% CI) | `mechanism` |

## Metric columns

Every row carries the metrics returned by `lunarsim.engine.Metrics.summary()`. The ones used in the paper:

| Column | Meaning |
|---|---|
| `delay_prio1_mean_h`, `delay_prio1_p90_h` | mean and 90th-percentile delay (h) of urgent (priority-1) items from release at the pad to delivery |
| `sl24_prio1` | share of urgent items delivered within 24 h |
| `delay_mean_<class>` | mean delay by cargo class (`consumables`, `science`, `equipment`, `infrastructure`, `element`, `bulk`, `return`) |
| `landed_kg`, `bulk_kg`, `ready_kg`, `delivered_kg`, `stranded_kg`, `backlog_kg` | mass accounting; `stranded_kg / landed_kg` is the immovable share quoted in the paper |
| `jobs`, `bundled_jobs`, `team_lifts`, `repositions`, `backhaul_kg` | trips and their types |
| `night_strandings`, `faults`, `unmet_operator_waits` | disruption counts |
| `utilisation`, `empty_km_share`, `km_total`, `energy_kwh`, `operator_hours` | fleet usage |
| `fleet_cost_musd`, `operator_cost_musd`, `cost_per_kg_usd`, `cost_per_tkm_usd` | system cost; cost per landed kg = 1e6 × (fleet + operator cost) / (delivered_kg − bulk_kg) |
| `revenue_gini` | Gini coefficient of job revenue across vehicle owners |
| `seed` | replication seed (demand stream = seed, operations stream = seed + 100,003) |

## Phase-3 columns (present only when a Phase-3 scenario field is set: `terrain`, `landing_model`, `plume`, `autonomy_model`)

| Column | Meaning |
|---|---|
| `plume_standdowns` | count of keep-out actions (jobs held at the boundary plus vehicles evacuated to a shelter) |
| `standdown_vehicle_h` | vehicle-hours lost to keep-out holds and evacuation drives |
| `landing_miss_m_mean` | mean horizontal miss of the sampled landings (m) |
| `offpad_landings`, `failed_landings` | landings beyond the pad radius / with a failed touchdown |
| `cargo_lost_kg` | cargo destroyed in failed landings (`failure_policy: lose`) |
| `km_offpad_extra` | extra vehicle-km to fetch cargo from off-pad landers |
| `interventions`, `intervention_h` | rover interventions drawn from the driving tables and their time cost (RTT + 300 s each) |
| `prop_residual_kg_mean` | mean propellant left at touchdown (class gate propellant minus used) |

Phase-3 suites: `E15_*` lander Monte Carlo summaries (and `E15_lunarlander_v3_warmup.json`, the tutorial reproduction),
`E16` driving-table validation, `E17` dispersion × standoff, `E18` plume keep-out, `E19` autonomy × fleet, `E20` pad siting and the law fit.
