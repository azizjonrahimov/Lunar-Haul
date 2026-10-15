# ML tooling for an RL lander-descent policy and a behavioural-cloning rover driver (Windows 11, RTX 3050 4 GB, Python 3.12), with browser (JS) and Python inference

Research date: 2026-10-15. Versions below were checked against PyPI / npm / GitHub on that date unless marked otherwise. Items marked **[unverified]** or **[inference]** were not confirmed from a primary source.

Quick version table (all verified on PyPI/npm JSON APIs on 2026-10-15; "win cp312" = a `cp312-cp312-win_amd64` wheel exists):

| Package | Version | Released | Requires-Python | win cp312 wheel | Source |
|---|---|---|---|---|---|
| gymnasium | 1.4.0 | 2026-10-05 | >=3.10 | pure Python | [PyPI](https://pypi.org/project/gymnasium/) |
| Box2D (pybox2d, import name `Box2D`) | 2.3.10 | first upload 2020-04-11 | not declared | yes (cp36–cp313) | [PyPI](https://pypi.org/project/Box2D/) |
| box2d-py | 2.3.8 | 2018-11-17 | not declared | **no** (sdist + old Linux/macOS wheels only) | [PyPI](https://pypi.org/project/box2d-py/) |
| swig | 4.5.1 | 2026-10-08 | – | yes (`py3-none-win_amd64`) | [PyPI](https://pypi.org/project/swig/) |
| pygame-ce | 2.5.8 | 2026-08-09 | >=3.10 | yes | [PyPI](https://pypi.org/project/pygame-ce/) |
| stable-baselines3 | 2.9.0 | 2026-06-15 | >=3.10 (classifiers 3.10–3.13) | pure Python | [PyPI](https://pypi.org/project/stable-baselines3/) |
| rl_zoo3 | 2.9.1 | 2026-06-15 | >=3.10 | pure Python | [PyPI](https://pypi.org/project/rl_zoo3/) |
| sb3-contrib | 2.9.0 | 2026-06-15 | >=3.10 | pure Python | [PyPI](https://pypi.org/project/sb3-contrib/) |
| torch | 2.14.1 | 2026-09-30 | >=3.10 | yes (PyPI wheel 124 MB; CUDA builds on download.pytorch.org) | [PyPI](https://pypi.org/project/torch/) |
| onnx | 1.23.2 | 2026-10-06 | >=3.10 | yes (`cp312-abi3`) | [PyPI](https://pypi.org/project/onnx/) |
| onnxruntime | 1.31.0 | 2026-10-09 | **>=3.11** | yes (cp311–cp314) | [PyPI](https://pypi.org/project/onnxruntime/) |
| onnxscript | 0.7.2 | 2026-09-09 | >=3.9 | pure Python | [PyPI](https://pypi.org/project/onnxscript/) |
| keras | 3.15.1 | 2026-07-29 | **>=3.11** | pure Python | [PyPI](https://pypi.org/project/keras/) |
| tensorflow | 2.21.0 | 2026-03-06 | >=3.10 | yes (cp310–cp313) | [PyPI](https://pypi.org/project/tensorflow/) |
| tensorflowjs (pip converter) | 4.22.0 | 2024-10-21 | – | – | [PyPI](https://pypi.org/project/tensorflowjs/) |
| @tensorflow/tfjs (npm) | 4.22.0 | 2024-10-21 (last modified 2025-01-08) | – | – | [npm](https://www.npmjs.com/package/@tensorflow/tfjs) |
| onnxruntime-web (npm) | 1.30.0 | 2026-09-14 | – | – | [npm](https://www.npmjs.com/package/onnxruntime-web) |
| gym-donkeycar (PyPI) | 1.0.13 | 2019-08-04 (stale; install from git) | setup.py: >=3.7 | pure Python | [PyPI](https://pypi.org/project/gym-donkeycar/) |
| python-socketio | 5.17.0 | 2026-09-14 | >=3.8 | pure Python | [PyPI](https://pypi.org/project/python-socketio/) |

---

## Key question 1 — Exact pip commands that work on Windows / Python 3.12 for gymnasium[box2d], stable-baselines3, torch (CUDA), onnxruntime, and their October-2026 versions

### Takeaway
On Python 3.12 the current Gymnasium (1.4.0) box2d extra no longer needs SWIG or a compiler: it pins the wheel-shipping `box2d==2.3.10` package (which has `cp312-cp312-win_amd64` wheels) plus `pygame-ce`, and only falls back to `box2d-py` + `swig` on Python >= 3.14. SB3 2.9.0 requires Python >= 3.10 and `torch>=2.8,<3.0`, so SB3 2.9.0 + torch 2.14.1 + gymnasium 1.4.0 + onnxruntime 1.31.0 is a consistent Python 3.12 stack; for CUDA on the RTX 3050 use the `cu126` or `cu130` index of download.pytorch.org (there are no `cu128` wheels for torch 2.14.x), although for MLP PPO the CPU build is what SB3 recommends.

### Cited Findings
- Gymnasium v1.4.0 `pyproject.toml` defines the box2d extra as: `pygame-ce >=2.1.3`, `box2d ==2.3.10; python_version < '3.14'`, `box2d-py ==2.3.8; python_version >= '3.14'`, `swig ==4.*; python_version >= '3.14'`, with the comment "box2d - provides wheel for <=3.13, but no source distribution; box2d-py - build from source"; `requires-python = ">= 3.10"` — [Gymnasium pyproject.toml @ v1.4.0](https://github.com/Farama-Foundation/Gymnasium/blob/v1.4.0/pyproject.toml) (same text on `main`).
- Gymnasium 1.4.0 was uploaded to PyPI on 2026-10-05, Requires-Python >=3.10; extras listed: atari, box2d, classic-control, mujoco, toy-text, jax, torch, array-api, other, all, testing — [PyPI gymnasium](https://pypi.org/project/gymnasium/).
- The `Box2D` 2.3.10 release on PyPI includes `Box2D-2.3.10-cp312-cp312-win_amd64.whl` and `Box2D-2.3.10-cp313-cp313-win_amd64.whl` (and cp36–cp311, win32, manylinux, musllinux, macOS, PyPy wheels; 91 files total) — [PyPI Box2D JSON](https://pypi.org/pypi/Box2D/json).
- `box2d-py` 2.3.8 (2018-11-17) publishes only a source tarball plus manylinux1/macOS wheels for CPython 3.5–3.7; no Windows wheels — [PyPI box2d-py](https://pypi.org/project/box2d-py/). Building it from source requires SWIG and a C++ compiler; the historical failure mode is pip trying to build `box2d-py` before `swig` is available because of extras ordering — [Gymnasium issue #245](https://github.com/Farama-Foundation/Gymnasium/issues/245); workaround used by the community: `pip install swig` first, then `pip install "gymnasium[box2d]"` — [Hugging Face forum](https://discuss.huggingface.co/t/rl-course-unit-1-python-setup-py-egg-info-did-not-run-successfully/167429), [Medium](https://medium.com/@heo2341/resolve-for-the-installation-problem-of-gym-box2d-4241dca0aa92); or install the newer `box2d` wheel package plus pygame instead of `box2d-py` — [openai/gym issue #2795](https://github.com/openai/gym/issues/2795).
- `swig` 4.5.1 on PyPI (2026-10-08) ships `swig-4.5.1-py3-none-win_amd64.whl` (2.6 MB) containing a compiled SWIG binary, so `pip install swig` works on Windows without a separate download — [PyPI swig](https://pypi.org/project/swig/).
- Stable-Baselines3 2.9.0 released 2026-06-15; Requires-Python >=3.10; classifiers 3.10, 3.11, 3.12, 3.13 — [PyPI stable-baselines3](https://pypi.org/project/stable-baselines3/). SB3 2.8.0 (2026-04-01) dropped Python 3.9 and added official 3.13 support; 2.9.0 relaxed the Gymnasium cap to `<2.0` (adding gymnasium 1.3.0 support) and raised minimum torch to 2.8; pandas/matplotlib became optional extras — [SB3 changelog](https://stable-baselines3.readthedocs.io/en/master/misc/changelog.html).
- SB3 `setup.py` on master (version 2.9.2a0) pins `gymnasium>=0.29.1,<2.0`, `numpy>=1.20,<3.0`, `torch>=2.8,<3.0`, `cloudpickle`, `python_requires=">=3.10"` — [SB3 setup.py](https://github.com/DLR-RM/stable-baselines3/blob/master/setup.py).
- SB3 install docs: "Stable-Baselines3 requires python 3.10+ and PyTorch >= 2.8"; `pip install 'stable-baselines3[extra]'` adds TensorBoard, OpenCV and ale-py; Windows users are pointed to Miniforge; use `opencv-python-headless` on headless machines — [SB3 install guide](https://stable-baselines3.readthedocs.io/en/master/guide/install.html).
- PyTorch release compatibility matrix (RELEASE.md): 2.14 → Python >=3.10, <=3.15; stable CUDA 12.6, 13.0, 13.2. 2.11 → CUDA 12.6, 12.8, 13.0. 2.15 (upcoming) → Python >=3.11; CUDA 13.2 stable, 13.4 experimental — [pytorch RELEASE.md](https://github.com/pytorch/pytorch/blob/main/RELEASE.md).
- For release 2.14 the supported architectures for Linux x86 and Windows builds are: CUDA 12.6.3 → Maxwell(5.0), Pascal(6.0), Volta(7.0), Turing(7.5), Ampere(8.0, 8.6), Hopper(9.0); CUDA 13.0.3 → Turing(7.5), Ampere(8.0, 8.6), Hopper(9.0), Blackwell(10.0, 12.0+PTX) — [pytorch RELEASE.md](https://github.com/pytorch/pytorch/blob/main/RELEASE.md). (The RTX 3050 is Ampere GA107, compute capability 8.6 — covered by both builds.)
- Verified wheel files present on the PyTorch index on 2026-10-15: `torch-2.14.1+cu126-cp312-cp312-win_amd64.whl` at [download.pytorch.org/whl/cu126/torch/](https://download.pytorch.org/whl/cu126/torch/); `torch-2.14.1+cu130-cp312-cp312-win_amd64.whl` at [/whl/cu130/torch/](https://download.pytorch.org/whl/cu130/torch/); `torch-2.14.1+cu132-cp312-cp312-win_amd64.whl` at [/whl/cu132/torch/](https://download.pytorch.org/whl/cu132/torch/); `torch-2.14.1+cpu-cp312-cp312-win_amd64.whl` at [/whl/cpu/torch/](https://download.pytorch.org/whl/cpu/torch/). The `cu128` index's newest Windows cp312 wheel is `torch-2.11.0+cu128` (no 2.12–2.14 cu128 builds) — [/whl/cu128/torch/](https://download.pytorch.org/whl/cu128/torch/).
- torch 2.14.1 on PyPI: uploaded 2026-09-30; `torch-2.14.1-cp312-cp312-win_amd64.whl` is 124,113,906 bytes — [PyPI torch JSON](https://pypi.org/pypi/torch/2.14.1/json).
- onnxruntime 1.31.0 (2026-10-09) requires Python >=3.11, ships `onnxruntime-1.31.0-cp312-cp312-win_amd64.whl` (and cp311/cp313/cp314, plus win_arm64) — [PyPI onnxruntime](https://pypi.org/project/onnxruntime/).
- Hugging Face Deep RL course unit 1 installs with `apt install swig cmake` then a requirements file covering `gymnasium[box2d]` and `stable-baselines3[extra]` (Linux/Colab recipe) — [HF Deep RL course unit 1](https://huggingface.co/learn/deep-rl-course/unit1/hands-on).

### Inferences
- Recommended Windows / Python 3.12 install sequence (derived from the pins above):
  ```powershell
  py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  # CPU-only PyTorch (what SB3 recommends for MLP PPO):
  pip install torch --index-url https://download.pytorch.org/whl/cpu
  # ...or CUDA build for the RTX 3050 (Ampere 8.6 is in both the cu126 and cu130 arch lists):
  pip install torch --index-url https://download.pytorch.org/whl/cu126
  pip install "gymnasium[box2d]==1.4.0" "stable-baselines3[extra]==2.9.0" rl_zoo3==2.9.1
  pip install onnx onnxruntime onnxscript
  ```
  `gymnasium[box2d]` on 3.12 resolves to `box2d==2.3.10` (binary wheel) + `pygame-ce`; SWIG is not pulled in. If an older Gymnasium or a stale lockfile still pins `box2d-py`, the fix is `pip install swig` before the extra, or `pip install box2d==2.3.10` explicitly.
- The 124 MB size of the PyPI Windows torch wheel indicates it is a CPU-only build (CUDA-enabled wheels are multi-gigabyte), so a plain `pip install torch` on Windows gives no GPU; the `--index-url` form is required for CUDA. **[inference from wheel size; the pytorch.org selector page is JavaScript-rendered and its commands could not be extracted]**
- Note the Python floor creep: onnxruntime 1.31 and keras 3.15 now require Python >= 3.11, torch 2.15 will require >= 3.11. Python 3.12 is safely inside every range; Python 3.14 would force the `box2d-py` + swig source build path.
- The import name for both `box2d` and `box2d-py` is `Box2D`, which is what `gymnasium/envs/box2d/lunar_lander.py` imports, so the two packages are interchangeable at runtime (do not install both in one environment).

### Gaps
- The exact pip error text for a failed `box2d-py` build on Windows/3.12 was not captured from a primary source (search results confirmed the SWIG-ordering cause and the "swig.exe not on PATH" cause, but not Python-3.12-specific reports).
- The upload date of the Box2D 2.3.10 cp312/cp313 wheel files specifically (as opposed to the 2020 release date) was not extracted.
- The minimum NVIDIA driver version required by the cu126/cu130 Windows wheels was not verified.
- Which CUDA build the pytorch.org "Get Started" selector currently labels as default for Windows could not be read (page is JS-rendered).

---

## Key question 2 — Exact LunarLander-v3 reward constants and observation definitions, and the standard PPO configuration that solves it (with reported training time)

### Takeaway
LunarLander-v3's observation is 8 floats (pad-centred position normalised by half the viewport, velocities scaled by half-viewport/FPS, angle in radians, 20×angular velocity/FPS, two leg-contact flags) and its reward is the step-to-step difference of a shaping term (−100·distance −100·speed −100·|angle| +10 per leg) minus 0.30·main-throttle and 0.03·side-throttle, with −100 on crash/out-of-bounds and +100 when the body comes to rest; episodes are capped at 1000 steps and the solved threshold is 200. RL Zoo's PPO recipe (16 envs, n_steps 1024, batch 64, 4 epochs, gamma 0.999, GAE 0.98, ent_coef 0.01, 1e6 steps, identical for discrete and continuous) reaches ~240–270 mean reward; the Hugging Face course quotes ~20 minutes for 1e6 steps on Colab.

### Cited Findings (environment code; all quotes verbatim from the `main` branch file [gymnasium/envs/box2d/lunar_lander.py](https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/box2d/lunar_lander.py), fetched 2026-10-15)
- Constants:
  ```python
  FPS = 50
  SCALE = 30.0  # affects how fast-paced the game is, forces should be adjusted as well
  MAIN_ENGINE_POWER = 13.0
  SIDE_ENGINE_POWER = 0.6
  INITIAL_RANDOM = 1000.0  # Set 1500 to make game harder
  LANDER_POLY = [(-14, +17), (-17, 0), (-17, -10), (+17, -10), (+17, 0), (+14, +17)]
  LEG_AWAY = 20
  LEG_DOWN = 18
  LEG_W, LEG_H = 2, 8
  LEG_SPRING_TORQUE = 40
  SIDE_ENGINE_HEIGHT = 14
  SIDE_ENGINE_AWAY = 12
  MAIN_ENGINE_Y_LOCATION = (4)  # The Y location of the main engine on the body of the Lander.
  VIEWPORT_W = 600
  VIEWPORT_H = 400
  ```
- Constructor: `def __init__(self, render_mode: str | None = None, continuous: bool = False, gravity: float = -10.0, enable_wind: bool = False, wind_power: float = 15.0, turbulence_power: float = 1.5)`; gravity must be strictly between −12 and 0; wind_power outside 0–20 and turbulence_power outside 0–2 trigger warnings — same file; argument semantics also in [Gymnasium LunarLander docs](https://gymnasium.farama.org/environments/box2d/lunar_lander/).
- Observation space bounds (`low`/`high`): x, y ∈ [−2.5, 2.5]; vx, vy ∈ [−10, 10] ("velocity bounds is 5x rated speed"); angle ∈ [−2π, 2π]; angular velocity ∈ [−10, 10]; leg flags ∈ [0, 1] — same file.
- Observation construction in `step()`:
  ```python
  pos = self.lander.position
  vel = self.lander.linearVelocity
  state = [
      (pos.x - VIEWPORT_W / SCALE / 2) / (VIEWPORT_W / SCALE / 2),
      (pos.y - (self.helipad_y + LEG_DOWN / SCALE)) / (VIEWPORT_H / SCALE / 2),
      vel.x * (VIEWPORT_W / SCALE / 2) / FPS,
      vel.y * (VIEWPORT_H / SCALE / 2) / FPS,
      self.lander.angle,
      20.0 * self.lander.angularVelocity / FPS,
      1.0 if self.legs[0].ground_contact else 0.0,
      1.0 if self.legs[1].ground_contact else 0.0,
  ]
  ```
  (With VIEWPORT_W/SCALE/2 = 10 and VIEWPORT_H/SCALE/2 = 6.667 world units, x is in units of half-screen-widths from the pad centre, vx is in half-screen-widths per frame.)
- Reward computation in `step()`:
  ```python
  reward = 0
  shaping = (
      -100 * np.sqrt(state[0] * state[0] + state[1] * state[1])
      - 100 * np.sqrt(state[2] * state[2] + state[3] * state[3])
      - 100 * abs(state[4])
      + 10 * state[6]
      + 10 * state[7]
  )  # And ten points for legs contact, the idea is if you
  # lose contact again after landing, you get negative reward
  if self.prev_shaping is not None:
      reward = shaping - self.prev_shaping
  self.prev_shaping = shaping
  reward -= (m_power * 0.30)  # less fuel spent is better, about -30 for heuristic landing
  reward -= s_power * 0.03
  terminated = False
  if self.game_over or abs(state[0]) >= 1.0:
      terminated = True
      reward = -100
  if not self.lander.awake:
      terminated = True
      reward = +100
  # truncation=False as the time limit is handled by the `TimeLimit` wrapper added during `make`
  return np.array(state, dtype=np.float32), reward, terminated, False, {}
  ```
  `game_over` is set by the Box2D contact listener when the lander body (not a leg) touches anything.
- Continuous action mapping: `action = np.clip(action, -1, +1)`; main engine fires if `action[0] > 0.0` with `m_power = (np.clip(action[0], 0.0, 1.0) + 1.0) * 0.5  # 0.5..1.0`; side engines fire if `np.abs(action[1]) > 0.5` with `direction = np.sign(action[1])` and `s_power = np.clip(np.abs(action[1]), 0.5, 1.0)`. Discrete: action 2 → `m_power = 1.0`; actions 1/3 → `direction = action - 2`, `s_power = 1.0`; 0 = no-op. Impulses applied: `(-ox * MAIN_ENGINE_POWER * m_power, -oy * MAIN_ENGINE_POWER * m_power)` and `(-ox * SIDE_ENGINE_POWER * s_power, ...)`. Physics step: `self.world.Step(1.0 / FPS, 6 * 30, 2 * 30)` — same file.
- Engine dispersion noise: `dispersion = [self.np_random.uniform(-1.0, +1.0) / SCALE for _ in range(2)]` is added to the thrust application point every step (so the dynamics are stochastic even without wind) — same file.
- Wind model: `wind_mag = tanh(sin(0.02*wind_idx) + sin(pi*0.01*wind_idx)) * wind_power` applied as a force to the centre, and an analogous torque with `turbulence_power`, only while no leg is in contact — same file.
- Registration: `register(id="LunarLander-v3", entry_point="gymnasium.envs.box2d.lunar_lander:LunarLander", max_episode_steps=1000, reward_threshold=200)` and `register(id="LunarLanderContinuous-v3", ..., kwargs={"continuous": True}, max_episode_steps=1000, reward_threshold=200)` — [gymnasium/envs/__init__.py](https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/__init__.py). (The docs page does not display these; it only notes the env is wrapped in `TimeLimit` — [docs](https://gymnasium.farama.org/environments/box2d/lunar_lander/).)
- Docs: discrete `Discrete(4)` = {0 nothing, 1 left orientation engine, 2 main engine, 3 right orientation engine}; continuous `Box(-1, +1, (2,), float32)`; termination when the lander crashes, |x| ≥ 1, or the body "is not awake" (Box2D sleep); "An episode is considered a solution if it scores at least 200 points"; version history: v3 resets the wind offset each reset, fixes non-determinism from incomplete world destruction, and widened bounds (x,y ±1.5→±2.5; velocities ±5→±10; angle ±π→±2π) — [Gymnasium LunarLander docs](https://gymnasium.farama.org/environments/box2d/lunar_lander/).

### Cited Findings (PPO configuration and results)
- RL Zoo `hyperparams/ppo.yml` (v3 ids, both blocks identical):
  ```yaml
  LunarLander-v3:
    n_envs: 16
    n_timesteps: !!float 1e6
    policy: 'MlpPolicy'
    n_steps: 1024
    batch_size: 64
    gae_lambda: 0.98
    gamma: 0.999
    n_epochs: 4
    ent_coef: 0.01
  LunarLanderContinuous-v3:   # same values
  ```
  No `normalize`, `learning_rate`, `clip_range` or `policy_kwargs` keys, so SB3 defaults apply to those — [rl-baselines3-zoo ppo.yml](https://github.com/DLR-RM/rl-baselines3-zoo/blob/master/hyperparams/ppo.yml).
- SB3 PPO defaults: `learning_rate=0.0003, n_steps=2048, batch_size=64, n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2, clip_range_vf=None, normalize_advantage=True, ent_coef=0.0, vf_coef=0.5, max_grad_norm=0.5, target_kl=None, device='auto'`; rollout buffer = `n_steps * n_envs`; supports Discrete and Box actions — [SB3 PPO docs](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html).
- RL Zoo benchmark (single run each, deterministic eval): PPO LunarLander-v2, 1M steps → 242.119 ± 31.823 (369 eval episodes); PPO LunarLanderContinuous-v2, 1M → 270.863 ± 32.072; also SAC 500k → 260.39, TQC 500k → 277.96, TD3 300k → 207.45, DQN 100k → 154.38, A2C 200k → 155.75. The table has no wall-clock column and no v3 rows yet — [rl-baselines3-zoo benchmark.md](https://github.com/DLR-RM/rl-baselines3-zoo/blob/master/benchmark.md).
- Hugging Face Deep RL course unit 1 (LunarLander-v2) uses exactly the Zoo hyperparameters with `make_vec_env(..., n_envs=16)` and `model.learn(total_timesteps=1000000)`, states training takes "approximately ~20min" (recommending the Colab GPU runtime), evaluates with `evaluate_policy(model, Monitor(gym.make(...)), n_eval_episodes=10, deterministic=True)`, and requires mean − std ≥ 200 — [HF course unit 1](https://huggingface.co/learn/deep-rl-course/unit1/hands-on).
- Community v3 model cards: a 1M-step checkpoint (16 envs, Zoo hyperparameters) scored 260.59 ± 18.91 and a 2M-step checkpoint 278.80 ± 19.13 over 50 deterministic episodes — [asiful2/ppo-LunarLander-v3](https://huggingface.co/asiful2/ppo-LunarLander-v3); a 200k-step run scored only 82.17 ± 101.84 — [Aadit-032/ppo-LunarLander-v3](https://huggingface.co/Aadit-032/ppo-LunarLander-v3).
- SB3 warns at model setup when a non-CNN policy is placed on GPU: "You are trying to run {algo} on the GPU, but it is primarily intended to run on the CPU when not using a CNN policy ... You can pass `device='cpu'` or `export CUDA_VISIBLE_DEVICES=` to force using the CPU. Note: The model will train, but the GPU utilization will be poor and the training might take longer than on CPU." — [on_policy_algorithm.py](https://github.com/DLR-RM/stable-baselines3/blob/master/stable_baselines3/common/on_policy_algorithm.py); background in [SB3 issue #1245](https://github.com/DLR-RM/stable-baselines3/issues/1245), where the maintainer's edited recommendation is "best is to use CPU (and tune the number of threads) as long as you are not using CNN", and a user reported A2C CartPole at ~1000 it/s (1 env) → ~4330 it/s (4 envs).
- Vectorised envs: `DummyVecEnv` runs envs sequentially in-process (recommended for cheap envs like CartPole); `SubprocVecEnv` uses one process per env and on Windows the default start method is `spawn`, so the training script must be guarded by `if __name__ == "__main__":`; "the number of environments should not exceed the number of logical cores on your CPU"; `make_vec_env(env_id, n_envs=..., wrapper_class=..., wrapper_kwargs=...)` — [SB3 vec_envs guide](https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html).
- TensorBoard: pass `tensorboard_log="./ppo_lander_tb/"` to the constructor, optionally `tb_log_name=` and `reset_num_timesteps=False` in `learn()`; view with `tensorboard --logdir ./ppo_lander_tb/`; log custom scalars from a callback via `self.logger.record("key", value)` — [SB3 TensorBoard guide](https://stable-baselines3.readthedocs.io/en/master/guide/tensorboard.html). TensorBoard itself is part of the `[extra]` install — [SB3 install guide](https://stable-baselines3.readthedocs.io/en/master/guide/install.html).
- Saving/loading: `model.save("ppo_lander")` then `model = PPO.load("ppo_lander")`; `model.predict(obs)` returns `(action, state)` — [SB3 PPO docs](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html).
- Evaluation protocol: `evaluate_policy(model, env, n_eval_episodes=10, deterministic=True, render=False, callback=None, reward_threshold=None, return_episode_rewards=False, warn=True)` returns `(mean_reward, std_reward)`; wrap the eval env in `Monitor` first so reward-modifying wrappers do not distort results — [SB3 evaluation API](https://stable-baselines3.readthedocs.io/en/master/common/evaluation.html). RL tips: evaluate on a separate test env over 5–20 episodes, use `deterministic=True` for PPO, run several seeds, and use `EvalCallback` for periodic evaluation — [SB3 RL tips](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html).

### Inferences
- A minimal Windows training script consistent with the above:
  ```python
  # train_lander.py
  import gymnasium as gym
  from stable_baselines3 import PPO
  from stable_baselines3.common.env_util import make_vec_env
  from stable_baselines3.common.vec_env import SubprocVecEnv
  from stable_baselines3.common.evaluation import evaluate_policy
  from stable_baselines3.common.monitor import Monitor

  if __name__ == "__main__":                       # required on Windows (spawn)
      env = make_vec_env("LunarLander-v3", n_envs=16, vec_env_cls=SubprocVecEnv)
      model = PPO("MlpPolicy", env, n_steps=1024, batch_size=64, n_epochs=4,
                  gamma=0.999, gae_lambda=0.98, ent_coef=0.01,
                  device="cpu", tensorboard_log="./tb", verbose=1)
      model.learn(total_timesteps=1_000_000)
      model.save("ppo_lander_v3")
      m, s = evaluate_policy(model, Monitor(gym.make("LunarLander-v3")),
                             n_eval_episodes=20, deterministic=True)
      print(m, s)
  ```
  For a laptop, 8–16 envs with `DummyVecEnv` (Box2D steps are cheap) is a reasonable first choice; measure the `time/fps` printed by SB3 and switch to `SubprocVecEnv` only if the environment, not the network, is the bottleneck.
- Expected wall-clock: the only timing statement found is the HF course's "~20 min" for 1e6 steps on Colab; on a modern laptop CPU with 16 envs this is of the same order (tens of minutes), with GPU offering no benefit for the 2×64 MLP per SB3's own warning. **[inference]**
- Because v3 only changed wind reset, determinism, and bounds, v2 benchmark numbers (242/271 at 1M) are a reasonable expectation for v3 as the HF v3 model cards (260 at 1M) confirm. **[inference]**

### Gaps
- No primary source gives a CPU wall-clock time or steps-per-second for PPO LunarLander on a specific laptop; it must be measured.
- The RL Zoo benchmark table has not yet been regenerated for the v3 ids.

---

## Key question 3 — Simplest reliable way to run an SB3 policy in JavaScript (and in Python without SB3), with a forward-pass sketch; ONNX Runtime Web alternative; model size

### Takeaway
An SB3 `MlpPolicy` for LunarLander is a two-hidden-layer (64, 64) Tanh MLP whose actor path is `Flatten → policy_net (Linear-Tanh-Linear-Tanh) → action_net`; for Discrete actions the deterministic action is `argmax(logits)`, for Box actions it is the Gaussian mean clipped to the action bounds (the learned `log_std` is only needed for stochastic sampling). Dumping `model.policy.state_dict()` to JSON (~10k parameters, tens of KB) and writing ~30 lines of plain JS/NumPy is the simplest path; ONNX (opset 17, via the SB3 `OnnxableSB3Policy` recipe) plus onnxruntime-web 1.30.0 is the officially documented alternative, at the cost of a 368 KB script plus a ~14 MB WASM download.

### Cited Findings
- `ActorCriticPolicy.__init__` defaults: `net_arch=None` → `dict(pi=[64, 64], vf=[64, 64])` for non-CNN extractors; `activation_fn: type[nn.Module] = nn.Tanh`; `ortho_init: bool = True`; `log_std_init: float = 0.0`; `squash_output: bool = False`. `_build` creates `self.mlp_extractor = MlpExtractor(features_dim, net_arch, activation_fn)`, `self.action_net, self.log_std = self.action_dist.proba_distribution_net(latent_dim_pi, log_std_init)` for Gaussian, and `self.value_net = nn.Linear(self.mlp_extractor.latent_dim_vf, 1)`. Forward: `features = self.extract_features(obs)` → `latent_pi, latent_vf = self.mlp_extractor(features)` → `mean_actions = self.action_net(latent_pi)` → `self.action_dist.proba_distribution(mean_actions, self.log_std)` — [SB3 policies.py](https://github.com/DLR-RM/stable-baselines3/blob/master/stable_baselines3/common/policies.py).
- `BasePolicy.predict` post-processing for Box spaces: if `squash_output` → `actions = self.unscale_action(actions)`, else `actions = np.clip(actions, self.action_space.low, self.action_space.high)` — same file.
- Custom-policy guide: for 1-D observations "a 2 layers fully connected net is used with: 64 units (per layer) for PPO/A2C/DQN"; the features extractor for vector observations "is just a Flatten layer"; change sizes with `policy_kwargs=dict(net_arch=dict(pi=[...], vf=[...]))` — [SB3 custom policy guide](https://stable-baselines3.readthedocs.io/en/master/guide/custom_policy.html).
- Distributions: `DiagGaussianDistribution.proba_distribution_net` → `mean_actions = nn.Linear(latent_dim, self.action_dim)` and `log_std = nn.Parameter(th.ones(self.action_dim) * log_std_init, requires_grad=True)`; `action_std = th.ones_like(mean_actions) * log_std.exp()`; `mode()` returns `self.distribution.mean`; `sample()` uses `rsample()`. `CategoricalDistribution`: `action_logits = nn.Linear(latent_dim, self.action_dim)`, `Categorical(logits=action_logits)`, `mode()` = `th.argmax(self.distribution.probs, dim=1)`; default `log_std_init = 0.0` — [SB3 distributions.py](https://github.com/DLR-RM/stable-baselines3/blob/master/stable_baselines3/common/distributions.py).
- Official ONNX export recipe: wrap `model.policy` in an `OnnxableSB3Policy(th.nn.Module)` whose `forward(observation)` returns `self.policy(observation, deterministic=True)` ("policy() returns actions, values, log_prob for PPO"), load the model with `device="cpu"`, call `th.onnx.export(onnxable_model, dummy_input, "my_ppo_model.onnx", opset_version=17, input_names=["input"])`, then verify with `onnx.checker.check_model` and `ort.InferenceSession(...).run(None, {"input": observation})`. Caveats: the export "returns normalized actions and doesn't include the" clipping/unscaling post-processing; observation preprocessing is included (image /255 for CNN policies); `deterministic=False` exports a stochastic policy; MultiInputPolicy → GH#1873 — [SB3 export guide](https://stable-baselines3.readthedocs.io/en/master/guide/export.html).
- Manual export: parameters via `model.get_parameters()` or `model.policy.state_dict()` (policies are PyTorch modules); architectures live in each algorithm's `policies.py`; TorchScript via `th.jit.trace`/`freeze`/`optimize_for_inference`; "ONNX-JS / ONNX Runtime Web: export to ONNX, then run inference in the browser"; TensorFlow.js path is SB3 → ONNX → TF → TF.js with `opset_version=14` and the warning that tfjs-converter is "not currently maintained" — same guide.
- ONNX Runtime Web execution providers: GPU `webgl`, `webgpu`, `webnn` (deviceType gpu); CPU `wasm` (alias `cpu`) or `webnn` (deviceType cpu); WASM supports all ONNX operators while WebGL/WebGPU/WebNN support a subset — [ORT Web tutorials](https://onnxruntime.ai/docs/tutorials/web/); install with `npm install onnxruntime-web` — [Build a web app with ORT](https://onnxruntime.ai/docs/tutorials/web/build-web-app.html).
- Official script-tag quick start: `<script src="https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js"></script>`, `const session = await ort.InferenceSession.create('./model.onnx');`, `const tensorA = new ort.Tensor('float32', dataA, [3, 4]);`, `const results = await session.run({ a: tensorA, b: tensorB });`, `results.c.data` — [onnxruntime-inference-examples quick-start index.html](https://github.com/microsoft/onnxruntime-inference-examples/blob/main/js/quick-start_onnxruntime-web-script-tag/index.html).
- onnxruntime-web 1.30.0 (published 2026-09-14) file sizes on jsDelivr: `dist/ort.min.js` 368,025 B; `dist/ort.wasm.min.js` 50,196 B; `dist/ort.webgpu.min.js` 66,417 B; `dist/ort.all.min.js` 819,608 B; `dist/ort-wasm-simd-threaded.wasm` 14,239,897 B; `dist/ort-wasm-simd-threaded.jsep.wasm` (WebGPU) 28,312,028 B; `dist/ort-wasm-simd-threaded.asyncify.wasm` 26,781,914 B; npm unpacked size 144.6 MB — [jsDelivr package listing](https://data.jsdelivr.com/v1/packages/npm/onnxruntime-web@1.30.0?structure=flat), [npm](https://www.npmjs.com/package/onnxruntime-web).
- onnxruntime (Python) 1.31.0 runs the same `.onnx` file on CPU in a Python simulation (see version table) — [PyPI onnxruntime](https://pypi.org/project/onnxruntime/).

### Inferences
- Parameter count for the default LunarLander actor (8 → 64 → 64 → 4): 8·64+64 + 64·64+64 + 64·4+4 = 4,996 weights; critic adds 4,801; continuous actor has 2 outputs + 2 `log_std` values. Stored as float32 that is ~20 KB for the actor alone; as JSON text roughly 60–120 KB; the ONNX file for actor+critic is well under 100 KB. **[arithmetic from the cited architecture]**
- Python-side export of the actor to JSON (key names follow `nn.Sequential` indexing inside `MlpExtractor`: Linear at 0 and 2, Tanh at 1 and 3 — confirm by printing `model.policy.state_dict().keys()`):
  ```python
  import json, numpy as np
  from stable_baselines3 import PPO
  model = PPO.load("ppo_lander_v3", device="cpu")
  sd = model.policy.state_dict()
  keep = ("mlp_extractor.policy_net.", "action_net.", "log_std")
  out = {k: v.cpu().numpy().tolist() for k, v in sd.items() if k.startswith(keep)}
  out["_meta"] = {"activation": "tanh", "action_space": str(model.action_space),
                  "low": getattr(model.action_space, "low", None).tolist() if hasattr(model.action_space, "low") else None,
                  "high": getattr(model.action_space, "high", None).tolist() if hasattr(model.action_space, "high") else None}
  json.dump(out, open("lander_policy.json", "w"))
  ```
- NumPy forward pass (for the Python discrete-event sim; identical maths to the JS):
  ```python
  def act(obs, w, continuous):
      h = np.tanh(np.asarray(w["mlp_extractor.policy_net.0.weight"]) @ obs + w["mlp_extractor.policy_net.0.bias"])
      h = np.tanh(np.asarray(w["mlp_extractor.policy_net.2.weight"]) @ h + w["mlp_extractor.policy_net.2.bias"])
      out = np.asarray(w["action_net.weight"]) @ h + w["action_net.bias"]
      if not continuous:
          return int(np.argmax(out))                      # argmax(softmax) == argmax(logits)
      return np.clip(out, -1.0, 1.0)                      # deterministic = Gaussian mean, clipped like BasePolicy.predict
      # stochastic: out + np.exp(w["log_std"]) * np.random.randn(len(out)), then clip
  ```
- JavaScript forward pass (no dependencies; weights are `[out][in]` nested arrays as produced by `.tolist()`):
  ```js
  function linear(x, W, b) {
    const y = new Float32Array(b.length);
    for (let o = 0; o < b.length; o++) {
      let s = b[o]; const row = W[o];
      for (let i = 0; i < x.length; i++) s += row[i] * x[i];
      y[o] = s;
    }
    return y;
  }
  const tanhV = v => v.map(Math.tanh);
  function policyOut(obs, w) {
    let h = tanhV(linear(obs, w["mlp_extractor.policy_net.0.weight"], w["mlp_extractor.policy_net.0.bias"]));
    h = tanhV(linear(h, w["mlp_extractor.policy_net.2.weight"], w["mlp_extractor.policy_net.2.bias"]));
    return linear(h, w["action_net.weight"], w["action_net.bias"]);
  }
  function actDiscrete(obs, w) {                 // LunarLander-v3: 0 noop, 1 left, 2 main, 3 right
    const l = policyOut(obs, w); let best = 0;
    for (let i = 1; i < l.length; i++) if (l[i] > l[best]) best = i;
    return best;
  }
  function actContinuous(obs, w, low = -1, high = 1) {   // LunarLanderContinuous-v3: [main, lateral]
    return policyOut(obs, w).map(v => Math.min(high, Math.max(low, v)));
  }
  ```
  The observation fed in must be built with exactly the `state = [...]` scaling quoted in Key question 2 (pad-relative x,y over 10 and 6.667 world units, velocities ×(10/50) and ×(6.667/50), raw angle, 20·ω/50, leg flags), and the JS lander physics must reproduce the continuous throttle mapping (`m_power = (clip(a0,0,1)+1)/2` when `a0 > 0`; side engine when `|a1| > 0.5`).
- Default SB3 `MlpPolicy` applies no observation normalisation for Box observations unless `VecNormalize` was used in training (the RL Zoo LunarLander config has no `normalize` key), so the raw environment observation is the network input. If `VecNormalize` is added later, its running mean/var must also be exported and applied before the MLP. **[inference from the absence of a `normalize` key and the export guide's preprocessing note]**
- ONNX Runtime Web is the better choice for the BC CNN (Key question 5) rather than for this 10k-parameter MLP: the hand-written forward pass avoids the 14 MB WASM download and runs in microseconds per step; the ONNX route is still worth keeping as a cross-check that the JSON forward pass reproduces `model.predict(deterministic=True)` bit-for-bit (compare `session.run` outputs with `model.policy(obs, deterministic=True)` as the SB3 guide does). **[inference]**

### Gaps
- The exact `state_dict` key names (`mlp_extractor.policy_net.0.*`, `.2.*`, `action_net.*`, `log_std`) were not read from a fetched source in this session; they follow SB3's `MlpExtractor` construction and should be confirmed by printing the keys.
- No published latency numbers were found for onnxruntime-web running a tiny MLP; the cost will be dominated by runtime load, not inference.

---

## Key question 4 — Writing and registering a custom Gymnasium terminal-descent environment; reward-shaping wrappers; curriculum and domain randomisation

### Takeaway
Gymnasium's custom-env contract is a `gym.Env` subclass with `observation_space`, `action_space`, `reset(seed, options) → (obs, info)` (calling `super().reset(seed=seed)` first) and `step(action) → (obs, reward, terminated, truncated, info)`, registered with `gym.register(id="ns/Name-v0", entry_point=..., max_episode_steps=N)`; `check_env` validates it. Reward shaping belongs either in `step()` (LunarLander's potential-difference pattern) or in a `RewardWrapper`/`TransformReward` wrapper; curriculum and domain randomisation are done by exposing setter methods on the env and calling them through the SB3 VecEnv `env_method(...)` from a callback, or by sampling physical parameters from `self.np_random` in `reset()` (LunarLander's `gravity`/`enable_wind` kwargs are the built-in example).

### Cited Findings
- Custom env skeleton: subclass `gym.Env`; define `self.observation_space` (e.g. `gym.spaces.Dict`/`Box`) and `self.action_space` in `__init__`; `reset(self, seed=None, options=None)` must call `super().reset(seed=seed)` and return `(observation, info)`; `step(action)` returns `(observation, reward, terminated, truncated, info)`. Register with `gym.register(id="gymnasium_env/GridWorld-v0", entry_point=GridWorldEnv, max_episode_steps=300)` (entry point may be a `"module:Class"` string), then `gym.make("gymnasium_env/GridWorld-v0", size=10)` forwards kwargs to the constructor; `gym.make_vec(..., num_envs=...)` vectorises. `gym.make` wraps the env as `OrderEnforcing<PassiveEnvChecker<...>>`; `gymnasium.utils.env_checker.check_env` catches common mistakes — [Gymnasium: Create a Custom Environment](https://gymnasium.farama.org/introduction/create_custom_env/).
- Gymnasium 1.4.0 made `check_env` and the passive checker verify that `reset`/`step` return distinct observation and info objects each step (buffer reuse now fails the check), and fixed `make`/`make_vec` for entry points that are `Wrapper` subclasses — [Gymnasium v1.4.0 release](https://github.com/Farama-Foundation/Gymnasium/releases/tag/v1.4.0).
- Reward wrappers: subclass `gym.RewardWrapper` and override `reward(self, reward)`; `TransformReward(env, func)` applies `func` to each step reward; `NormalizeReward(env, gamma=0.99, epsilon=1e-8)` scales rewards to roughly fixed variance of the discounted return (freeze with `update_running_mean` during evaluation); `ClipReward(env, min_reward, max_reward)` — [Gymnasium reward wrappers](https://gymnasium.farama.org/api/wrappers/reward_wrappers/).
- LunarLander's own shaping is a potential-difference: `reward = shaping - self.prev_shaping` with `shaping = -100*dist - 100*speed - 100*|angle| + 10*leg0 + 10*leg1`, plus per-step fuel penalties and ±100 terminal bonuses — [lunar_lander.py](https://github.com/Farama-Foundation/Gymnasium/blob/main/gymnasium/envs/box2d/lunar_lander.py). SB3's tips: begin with a shaped, informative reward and a simplified problem ("reward engineering"), normalise observations (`VecNormalize`) and rescale continuous actions to a symmetric `[-1, 1]` because Gaussian policies are centred at 0 with std 1 — [SB3 RL tips](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html).
- Built-in domain parameters: `LunarLander(gravity=..., enable_wind=..., wind_power=..., turbulence_power=...)`; gravity bounded in (−12, 0), wind 0–20, turbulence 0–2 — [Gymnasium LunarLander docs](https://gymnasium.farama.org/environments/box2d/lunar_lander/).
- Runtime modification of vectorised envs (curriculum hook): `VecEnv.set_attr(attr_name, value, indices=None)`, `get_attr(attr_name, indices=None)`, `env_method(method_name, *args, indices=None, **kwargs)`; the docs warn against setting attributes directly from a callback because of wrapper layers and recommend exposing a setter (their example `set_mu`) and calling `training_env.env_method("set_mu", value)`, with the change taking effect at the next reset; Gymnasium 1.0-style access is `env_method("get_wrapper_attr", "mu")` / `env_method("set_wrapper_attr", "mu", 0.1)` — [SB3 vec_envs guide](https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html).
- `make_vec_env(..., wrapper_class=..., wrapper_kwargs=...)` applies a per-env Gymnasium wrapper (example: `RescaleAction` on Pendulum) — same guide.

### Inferences
- Skeleton for a physics-based lunar terminal-descent env consistent with the Gymnasium contract (constants are placeholders to be set from the project's lander model):
  ```python
  import numpy as np, gymnasium as gym
  from gymnasium import spaces

  class LunarDescentEnv(gym.Env):
      metadata = {"render_modes": []}
      def __init__(self, dt=0.1, g=1.62, dry_mass=1500.0, prop_mass=600.0,
                   isp=311.0, max_thrust=6000.0, min_throttle=0.3, max_steps=600):
          self.dt, self.g0 = dt, 9.80665
          self.g, self.dry_mass, self.prop0 = g, dry_mass, prop_mass
          self.isp, self.max_thrust, self.min_throttle = isp, max_thrust, min_throttle
          self.max_steps = max_steps
          # obs: [x, z, vx, vz, pitch, pitch_rate, prop_frac]   (normalise to ~[-1,1] before returning)
          self.observation_space = spaces.Box(-np.inf, np.inf, shape=(7,), dtype=np.float32)
          # act: [throttle_cmd in -1..1 -> off / min_throttle..1, pitch_rate_cmd in -1..1]
          self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
      def reset(self, seed=None, options=None):
          super().reset(seed=seed)
          rnd = self.np_random
          self.g = rnd.uniform(1.55, 1.70) if (options or {}).get("randomize", True) else 1.62   # domain randomisation
          self.state = np.array([rnd.uniform(-200, 200), rnd.uniform(400, 600),
                                 rnd.uniform(-10, 10), rnd.uniform(-30, -10), 0.0, 0.0], float)
          self.prop, self.t = self.prop0, 0
          return self._obs(), {}
      def step(self, a):
          a = np.clip(a, -1, 1)
          thr = 0.0 if a[0] <= 0 else self.min_throttle + (1 - self.min_throttle) * a[0]   # LunarLander-style dead band
          m = self.dry_mass + self.prop
          T = thr * self.max_thrust if self.prop > 0 else 0.0
          x, z, vx, vz, th, w = self.state
          ax, az = T * np.sin(th) / m, T * np.cos(th) / m - self.g
          vx, vz = vx + ax * self.dt, vz + az * self.dt
          x, z = x + vx * self.dt, z + vz * self.dt
          w = float(a[1]) * 0.2; th = th + w * self.dt
          self.prop = max(0.0, self.prop - T / (self.isp * self.g0) * self.dt)       # variable mass
          self.state = np.array([x, z, vx, vz, th, w]); self.t += 1
          shaping = -np.hypot(x, z) - 2 * np.hypot(vx, vz) - 20 * abs(th)        # potential-difference shaping
          reward = (shaping - self.prev) if hasattr(self, "prev") else 0.0
          self.prev = shaping
          reward -= 0.01 * thr                                                     # propellant penalty
          terminated = z <= 0.0
          if terminated:
              soft = abs(vz) < 2.0 and abs(vx) < 1.0 and abs(th) < 0.1 and abs(x) < 10.0
              reward += 100.0 if soft else -100.0
          truncated = self.t >= self.max_steps
          return self._obs(), float(reward), bool(terminated), bool(truncated), {}
      def set_difficulty(self, level):            # curriculum hook called via VecEnv.env_method
          self.level = level
      def _obs(self):
          x, z, vx, vz, th, w = self.state
          return np.array([x/500, z/600, vx/50, vz/50, th, w, self.prop/self.prop0], np.float32)

  gym.register(id="lunar/Descent-v0", entry_point=LunarDescentEnv, max_episode_steps=600)
  ```
  Then `from gymnasium.utils.env_checker import check_env; check_env(LunarDescentEnv())` before training with `make_vec_env("lunar/Descent-v0", n_envs=16)`. Keeping the action space symmetric in [−1, 1] and the observation scaled to O(1) follows the SB3 tips; the −100/+100 terminal and potential-difference shaping copy the LunarLander pattern that PPO is known to solve.
- Curriculum: a `BaseCallback` whose `_on_step` checks `self.model.ep_info_buffer` mean reward and calls `self.training_env.env_method("set_difficulty", next_level)` (e.g., widen the initial-state distribution, raise initial speed, enable wind/turbulence) is the pattern the SB3 docs describe for their `set_mu` example. Domain randomisation of gravity, mass, thrust and sensor noise should be sampled from `self.np_random` inside `reset()` so it is seed-reproducible. **[inference from the cited docs]**
- Separate shaping from the task reward by keeping the sparse terminal reward in `step()` and adding the dense term in a `RewardWrapper` subclass; this lets evaluation (with `Monitor` placed inside the wrapper, per the `evaluate_policy` note) report the unshaped return. **[inference]**

### Gaps
- No peer-reviewed or official source was found that documents a Gymnasium lunar terminal-descent environment with variable mass and throttle limits; the skeleton above is a synthesis, not a cited implementation.
- The Gymnasium custom-env page does not discuss `TimeLimit` explicitly (it only exposes `max_episode_steps`), nor curriculum tooling; curriculum guidance comes from SB3's VecEnv docs.

---

## Key question 5 — Behavioural cloning for driving: PilotNet in Keras 3 / PyTorch, augmentation, training on a 4 GB GPU, heightmap input alternative, and browser export (ONNX Runtime Web vs TensorFlow.js) with size/speed numbers

### Takeaway
The reference PilotNet (NVIDIA DAVE-2) is a 9-layer network — normalisation, five convolutions (5×5 stride 2 ×3, then 3×3 ×2) and three fully connected layers — with about 250k parameters, and the widely used Udacity-simulator implementation (naokishibuya) realises it as 24/36/48/64/64 filters + Dense 100/50/10/1 with ELU, 66×200 YUV input, dropout 0.5, Adam 1e-4, batch 40, 252,219 parameters. Keras 3.15 can `model.export(path, format="onnx")` directly, which pairs with onnxruntime-web 1.30 in the browser; the TensorFlow.js toolchain (tfjs 4.22.0, last published Oct 2024) does not convert Keras 3 `.keras` models and is effectively unmaintained, so ONNX Runtime Web is the safer browser route.

### Cited Findings
- NVIDIA PilotNet (DAVE-2): camera frames split into YUV planes; first layer is a hard-coded normaliser not trained; five convolutional layers — first three 5×5 kernels with 2×2 stride, last two 3×3 non-strided — followed by three fully connected layers ending in a single output (inverse turning radius); nine layers total, "about 27 million connections and 250 thousand parameters"; trained on ~72 h of driving; augmentation by artificial shifts and rotations with magnitudes drawn from a zero-mean normal with std twice the human-driving std, labels adjusted to return to lane centre within two seconds; inference at 30 FPS on DRIVE PX — [NVIDIA Developer Blog](https://developer.nvidia.com/blog/deep-learning-self-driving-cars/); paper: Bojarski et al., "End to End Learning for Self-Driving Cars", arXiv:1604.07316, April 2016 (trained with Torch 7) — [arXiv 1604.07316](https://arxiv.org/abs/1604.07316).
- naokishibuya/car-behavioral-cloning (Keras implementation for the Udacity simulator): Lambda normalisation (`x/127.5 - 1.0`), Conv 24@5×5 s2, 36@5×5 s2, 48@5×5 s2, 64@3×3 s1, 64@3×3 s1 (ELU), Dropout 0.5, Dense 100, 50, 10 (ELU), Dense 1; total 252,219 parameters; preprocessing: crop sky and bonnet, resize to 66×200, RGB→YUV; augmentation: random choice of left/centre/right camera with ±0.2 steering correction, random horizontal flip, random translation (0.002 steering per pixel of x-shift), random vertical translation, random shadow, random brightness; training: MSE loss, Adam lr 1e-4, batch 40, 20,000 samples/epoch, 5–10 epochs (lake track) or 50 (jungle), `ModelCheckpoint` on val loss; run with `python drive.py model.h5` after starting the simulator in Autonomous Mode — [GitHub repo](https://github.com/naokishibuya/car-behavioral-cloning). Its `environment.yml` pins `python==3.5.2`, `tensorflow==1.1`, `keras==1.2`, `eventlet`, `flask-socketio` (2017-era stack) — [environment.yml](https://github.com/naokishibuya/car-behavioral-cloning/blob/master/environment.yml).
- A PyTorch PilotNet port for the Udacity simulator (66×200 YUV input, flips and random panning) exists as a Hugging Face Space demo but without a linked code repository — [HF Space](https://eyad222-self-driving-web.static.hf.space/index.html). No Keras-3-specific PilotNet repository was found by search.
- Keras 3 `Model.export(filepath, format="tf_saved_model", verbose=None, input_signature=None, **kwargs)` supports `format` in {`"tf_saved_model"`, `"onnx"`, `"openvino"`, `"litert"`, `"torch"`}; `opset_version` kwarg for ONNX; "currently supported only with TensorFlow, JAX and Torch backends"; ONNX example: `model.export("path", format="onnx")` then `onnxruntime.InferenceSession("path")` — [Keras export API](https://keras.io/api/models/model_saving_apis/export/). keras 3.15.1 requires Python >=3.11; tensorflow 2.21.0 has cp312 Windows wheels (see version table).
- TensorFlow.js: `@tensorflow/tfjs` latest is 4.22.0, published 2024-10-21 (registry last modified 2025-01-08); the pip converter `tensorflowjs` is also 4.22.0 from 2024-10-21 — [npm](https://www.npmjs.com/package/@tensorflow/tfjs), [PyPI](https://pypi.org/project/tensorflowjs/). The converter README documents `tensorflowjs_converter --input_format=keras model.h5 out_dir` and `--input_format=keras_saved_model`, with no Keras 3 format — [tfjs-converter README](https://github.com/tensorflow/tfjs/blob/master/tfjs-converter/README.md). A tfjs maintainer stated the converter "does not support converting Keras models saved in the new format" (`.keras`), with silently wrong weights reported — [tfjs issue #8266](https://github.com/tensorflow/tfjs/issues/8266); `TF_USE_LEGACY_KERAS=1` is the workaround for `save_format` errors — [tfjs issue #8229](https://github.com/tensorflow/tfjs/issues/8229); a Google forum reply says the converter "currently doesn't support Keras 3 models" and suggests downgrading to Keras 2 — [Google AI forum](https://discuss.ai.google.dev/t/how-to-convert-a-python-tensorflow-model-to-tensorflow-js-json-model-in-colab/94139). SB3's export guide likewise warns tfjs-converter "is not currently maintained" — [SB3 export guide](https://stable-baselines3.readthedocs.io/en/master/guide/export.html).
- ONNX Runtime Web supports `webgpu`/`webgl`/`webnn` GPU providers and `wasm` CPU; WebGPU bundle `ort.webgpu.min.js` is 66 KB plus the 28.3 MB `ort-wasm-simd-threaded.jsep.wasm`; the CPU path is `ort.wasm.min.js` 50 KB + 14.2 MB `ort-wasm-simd-threaded.wasm` — [ORT Web tutorials](https://onnxruntime.ai/docs/tutorials/web/), [jsDelivr listing](https://data.jsdelivr.com/v1/packages/npm/onnxruntime-web@1.30.0?structure=flat).

### Inferences
- Keras 3 PilotNet (same layer list as the Udacity implementation; Keras 3 `Rescaling`/`Cropping2D` replace the Lambda layer so the graph exports cleanly to ONNX):
  ```python
  import keras
  from keras import layers
  def pilotnet(input_shape=(66, 200, 3)):
      return keras.Sequential([
          layers.Input(input_shape),
          layers.Rescaling(1/127.5, offset=-1.0),
          layers.Conv2D(24, 5, strides=2, activation="elu"),
          layers.Conv2D(36, 5, strides=2, activation="elu"),
          layers.Conv2D(48, 5, strides=2, activation="elu"),
          layers.Conv2D(64, 3, activation="elu"),
          layers.Conv2D(64, 3, activation="elu"),
          layers.Dropout(0.5), layers.Flatten(),
          layers.Dense(100, activation="elu"), layers.Dense(50, activation="elu"),
          layers.Dense(10, activation="elu"), layers.Dense(1),          # steering; use Dense(2) for steering+throttle
      ])
  model = pilotnet(); model.compile(optimizer=keras.optimizers.Adam(1e-4), loss="mse")
  # ... model.fit(ds_train, validation_data=ds_val, epochs=10)
  model.export("pilotnet_onnx", format="onnx", opset_version=17)   # -> load in onnxruntime / onnxruntime-web
  ```
  PyTorch equivalent: `nn.Sequential(nn.Conv2d(3,24,5,2), nn.ELU(), nn.Conv2d(24,36,5,2), nn.ELU(), nn.Conv2d(36,48,5,2), nn.ELU(), nn.Conv2d(48,64,3), nn.ELU(), nn.Conv2d(64,64,3), nn.ELU(), nn.Flatten(), nn.Dropout(0.5), nn.Linear(64*1*18, 100), nn.ELU(), nn.Linear(100,50), nn.ELU(), nn.Linear(50,10), nn.ELU(), nn.Linear(10,1))` with NCHW input (3, 66, 200) and `torch.onnx.export(..., opset_version=17)`; the 64×1×18 flatten size follows from the 66×200 input through the strided convolutions. **[inference; standard layer arithmetic]**
- Size and speed: 252k float32 parameters ≈ 1.0 MB of weights, so the ONNX file is ~1 MB and dominated by the fully connected 1152→100 layer; forward cost is on the order of 25–30 M multiply-adds (NVIDIA's "27 million connections"), which WASM SIMD inference handles at well above the 10–30 Hz a browser rover sim needs, and WebGPU is unnecessary for this size. **[inference; no measured browser benchmark for PilotNet was found]**
- Training on a 4 GB RTX 3050: with 252k parameters and 66×200×3 inputs at batch 40, activations and weights occupy a few tens of MB of VRAM, so the 4 GB limit is not binding; throughput will be limited by JPEG decoding and augmentation on the CPU, which argues for `tf.data`/`torch.utils.data.DataLoader` with workers and, if needed, pre-resized caches. With 20,000 samples/epoch and 10 epochs (the repo's lake-track recipe) training is tens of minutes on this class of GPU. **[inference; no published timing on a 4 GB GPU was found]**
- Heightmap/terrain-patch input instead of pixels: because the rover lives in a simulation where terrain is known, a local height/slope patch (e.g., 32×32 or 64×64 floats, body-aligned, plus speed/heading-error scalars) can replace the camera image; the same conv stack with the first layer taking 1–3 channels (height, slope, roughness) and smaller strides works, is far lighter to train, and makes the JS inference trivial since the browser sim already holds the heightmap. The expert labels then come from a scripted planner (pure-pursuit/A* path follower) rather than human driving, so the dataset is unlimited and DAgger-style relabelling is cheap. **[inference; no source implements this specific variant]**
- Browser route recommendation: Keras 3 → ONNX → onnxruntime-web (wasm EP), or PyTorch → ONNX → onnxruntime-web; avoid TF.js because the converter does not accept Keras 3 artefacts and the ecosystem has had no release since October 2024. Hosting cost is ~14 MB of WASM once (cacheable) plus ~1 MB model. **[inference from cited status]**

### Gaps
- The original paper's fully connected layer widths (the 1164/100/50/10 sequence) could not be read from the PDF in this session (PDF rendering tool unavailable); the NVIDIA blog confirms "three fully connected layers" and "250 thousand parameters" but not the widths. The Udacity-style 100/50/10 variant is cited from the naokishibuya repo.
- No measured browser inference latency for PilotNet-size CNNs in onnxruntime-web was found.
- No source was found reporting PilotNet training time on a 4 GB GPU.
- Whether Keras 3's `format="onnx"` export needs extra packages (e.g., `onnxscript`, `tf2onnx`) per backend was not verified; the Keras page only states backend support (TF/JAX/Torch).
- No public repository implementing PilotNet in Keras 3 (as opposed to Keras 2 / tf.keras) was found.

---

## Key question 6 — Udacity simulator status in 2026, gym-donkeycar as the alternative, and open-source lunar-terrain driving simulators (LunarSim, OmniLRS, Lunar Autonomy Challenge) with requirements; what is usable on this laptop

### Takeaway
The Udacity self-driving-car simulator repository was archived (read-only) on 24 Feb 2022 with 2017-era binaries and a Python 3.5/TensorFlow 1.1-era toolchain, whereas gym-donkeycar is maintained (simulator "Race Edition v25.10.06", Gymnasium API, Windows binary `donkey_sim.exe`, 120×160×3 observations, [steer, throttle] actions). None of the lunar simulators is practical on a 4 GB RTX 3050: OmniLRS needs Isaac Sim (minimum 16 GB VRAM, RTX 4080-class), the NASA/APL Lunar Autonomy Challenge simulator (Unreal Engine + CARLA) is distributed only to selected US student teams and specifies Ubuntu 20.04/22.04, RTX 3000-series with 16 GB VRAM and Python 3.8–3.10, and PUTvision's LunarSim is a Unity/ROS 2 Humble Linux Docker binary with unstated hardware needs. The lightweight path is gym-donkeycar for a camera-based BC baseline or a self-built heightmap rover environment in Gymnasium + JS.

### Cited Findings
- Udacity `self-driving-car-sim`: "archived by the owner on Feb 24, 2022. It is now read-only"; master branch deprecated in favour of `Unity_2020_3` and `Unity_2019_4` branches; binaries: Term 1 v2 (2017-02-07; Linux/Mac/Windows), Term 1 v1 (2016-12-09; Windows 32/64), Term 2 v1.45 (2017-06-14), Term 3 v1.2 (2017-07-11), Capstone v1.3 (2017-12-07); the README does not document the socket protocol — [udacity/self-driving-car-sim](https://github.com/udacity/self-driving-car-sim). The matching Python side (naokishibuya `drive.py`) was built on `eventlet` + `flask-socketio` with Python 3.5.2 — [environment.yml](https://github.com/naokishibuya/car-behavioral-cloning/blob/master/environment.yml); a later Udacity-sim project (UDS) still specifies Python 3.7.4 and reports the server starting as "wsgi starting up on http://0.0.0.0:4567" — [agajansahatov/uds README](https://github.com/agajansahatov/uds/blob/main/README.md).
- Donkey simulator: Unity-based, derived from the `sdsandbox` project's `donkey` branch, wrapped as a Gym env by gym-donkeycar; prebuilt binaries for Linux, Windows (`DonkeySimWin/donkey_sim.exe`) and macOS on the gym-donkeycar releases page; install with `git clone https://github.com/tawnkramer/gym-donkeycar; pip install -e .[gym-donkeycar]`; control message fields `steering` (−1..1, about 16° at full lock), `throttle` (−1..1), `brake` (0..1); camera width/height configurable 16–512; donkeycar workflow `python manage.py drive` (web UI at http://localhost:8887/drive), `donkey train --tub ./data --model models/mypilot.h5`, `python manage.py drive --model models/mypilot.h5` — [Donkey Car docs: Simulator](https://docs.donkeycar.com/guide/deep_learning/simulator/).
- gym-donkeycar README: `pip install git+https://github.com/tawnkramer/gym-donkeycar`; "Gymnasium" environments ("formerly OpenAI Gym"), `import gymnasium as gym`; env ids `donkey-warehouse-v0`, `donkey-generated-roads-v0`, `donkey-avc-sparkfun-v0`, `donkey-generated-track-v0`, `donkey-roboracingleague-track-v0`, `donkey-waveshare-v0`, `donkey-minimonaco-track-v0`, `donkey-warren-track-v0`, `donkey-thunderhill-track-v0`, `donkey-circuit-launch-track-v0`; observation shape `(120, 160, 3)`; action `Box(2,)` named `['steer', 'throttle']`; usage `gym.make("donkey-generated-track-v0", conf={"exe_path": ".../donkey_sim.exe", "port": 9091})`, `obs, info = env.reset()`, `obs, reward, terminated, truncated, info = env.step(np.array([0.0, 0.5]))` — [tawnkramer/gym-donkeycar](https://github.com/tawnkramer/gym-donkeycar). `setup.py`: `requirements = ["gymnasium>=0.29.0", "numpy", "pillow"]` ("Migrated from OpenAI gym to gymnasium"), `python_requires=">=3.7"` — [setup.py](https://github.com/tawnkramer/gym-donkeycar/blob/master/setup.py). Releases: "Race Edition v25.10.06 (Latest)", 06 Oct — improved reward function, CI fixes, `host` argument in `examples/ddqn.py`; previous: v22.11.06 (rotating-platform obstacle, bonus/penalty gates, ice area), v22.05.30, v22.03.24, v21.12.11 (new car physics, time scaling), v21.07.24 (Circuit Launch), v21.04.15 (Thunderhill), v21.02.20 (Warren, Mini Monaco), v20.11.17 (waveshare); each release lists 5 assets — [gym-donkeycar releases](https://github.com/tawnkramer/gym-donkeycar/releases). The PyPI package is stale (1.0.13, 2019-08-04) — [PyPI gym-donkeycar](https://pypi.org/project/gym-donkeycar/).
- LunarSim (PUTvision, Poznań University of Technology): "Lunar Rover Simulator Focused on High Visual Fidelity and ROS 2 Integration for Advanced Computer Vision Algorithm Development", Applied Sciences 13(22):12401, Nov 2023, built with the Unity game engine on ROS 2 — [MDPI paper](https://www.mdpi.com/2076-3417/13/22/12401); README: build with `docker build -t lunarsim:latest .`, run `./run.sh` then `./LunarSim.x86_64` (Linux binary), ROS 2 Humble inside the container, topics `/lunarsim/imu`, left/right cameras (raw/compressed), `/lunarsim/camera_depth/depth`, `/lunarsim/gt/pose`, `/cmd_vel`; no hardware/OS requirements or license stated on the page — [PUTvision/LunarSim](https://github.com/PUTvision/LunarSim).
- OmniLRS (Omniverse Lunar Robotics Simulator): built on NVIDIA Isaac Sim/Omniverse; V2.5 migrated to Isaac Sim 5.0; BSD-3-Clause; GPU ray-traced lighting and vision sensors, wheel–soil interaction and terrain deformation (Lunalab, Lunaryard), LRO-DEM-based LargeScale terrain with procedural rocks/craters, ROS 2 control, power/radio/thermal models, Yamcs/Grafana mission control; Docker install recommended; Windows not mentioned — [AntoineRichard/OmniLRS](https://github.com/AntoineRichard/OmniLRS). Isaac Sim system requirements: minimum GeForce RTX 4080 with 16 GB VRAM, 32 GB RAM, 4 cores, Ubuntu 22.04/24.04 or Windows 11 (Windows 10 not supported); "GPUs with less than 16GB VRAM may be insufficient"; driver Windows 595.97 / Linux 595.58.03 — [Isaac Sim requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html).
- NASA Lunar Autonomy Challenge (NASA, JHU APL, Caterpillar, Embodied AI): simulator "built with Unreal Engine and CARLA"; digital twin of NASA's IPEx (ISRU Pilot Excavator), four-wheel differential steering, IMU plus eight monochrome cameras (front/back stereo pairs, left/right side, front/back arm) with configurable LEDs; 20 Hz simulation, 10 Hz images up to 2448×2048, 40 m × 40 m terrain with lander, charging station and fiducials; the 2025 edition is mapping-only (no excavation) — [arXiv 2603.17232 (Mar 2026)](https://arxiv.org/abs/2603.17232). Requirements (2024–2025 guidebook/documentation): Intel i7/i9 6+ cores, NVIDIA RTX 3000-series or better, 32 GB RAM, 16 GB VRAM, 50 GB disk; Ubuntu 20.04 or 22.04 only ("will not work on older or newer versions of Ubuntu"); Python 3.8–3.10, pip >= 20.3; machine must support 16 concurrent threads; the simulator package "will be made available to selected teams upon acceptance" (not a public download); eligibility: at least four students plus a faculty adviser at a U.S. institution — [LAC documentation](https://lunar-autonomy-challenge.jhuapl.edu/Challenge-Documentation/index.php), [2024–2025 guidebook PDF](https://lac.jhuapl.edu/Challenge-Information/2024_Lunar-Autonomy-Challenge-Guidebook.pdf), [NASA announcement](https://www.nasa.gov/directorates/stmd/student-lunar-autonomy-challenge/). First-edition timeline: qualifying round through 28 Feb 2025, winners May 2025 — [NASA selected teams](https://www.nasa.gov/directorates/stmd/lunar-autonomy-challenge-selected-teams).

### Inferences
- Usability on the target laptop (RTX 3050 4 GB, Windows 11): OmniLRS/Isaac Sim is excluded by the 16 GB VRAM minimum; the LAC simulator is excluded by access (selected teams only), OS (Ubuntu only) and VRAM; LunarSim is a Linux x86_64 Unity binary inside Docker with ROS 2 Humble, so on Windows it would need WSL2 with GPU passthrough and its VRAM demand is unknown — feasible only as an experiment, not a dependable pipeline. **[inference from the cited requirements]**
- The Donkey simulator is the one maintained, Windows-native, Gymnasium-compatible driving simulator found: a Unity executable that runs on modest GPUs, with a BC/RL-ready `(120,160,3)` camera observation and `[steer, throttle]` action, so it is the recommended stand-in for a pixel-based PilotNet baseline on this laptop (even though its tracks are roads, not regolith). Version tags follow a `vYY.MM.DD` scheme, so v25.10.06 is 6 Oct 2025. **[inference]**
- For lunar-specific driving, the pragmatic route on this hardware is a self-authored 2.5-D heightmap rover environment (Gymnasium for training, mirrored in JS for the browser) with a scripted expert for labels, as outlined in Key question 5; this also keeps train/test physics identical between Python and the browser, which no external simulator offers. **[inference]**
- If the old Udacity binaries are used anyway, the Python side must be rebuilt against current `python-socketio` (5.17.0) / `eventlet`/`flask` rather than the 2017 pins, and the original `drive.py` telemetry handler is the only protocol documentation; the socketio 4→5 protocol change is a known breakage class but could not be verified against a primary source here. **[unverified]**

### Gaps
- No evidence was found of a 2025–2026 or 2026–2027 Lunar Autonomy Challenge edition or of a public release of its simulator; the official site timed out twice during this session, so current status is unconfirmed.
- LunarSim's hardware requirements, license and Unity version are not stated on its README; the MDPI paper would need to be read for details.
- OmniLRS hardware requirements are only inferable from Isaac Sim's generic requirements; the OmniLRS wiki install page was not fetched.
- The exact python-socketio/python-engineio version pair that works with the Udacity simulator on Python 3.12 was not found in a primary source.
- gym-donkeycar's release page shows day/month only; the year of v25.10.06 is inferred from the version scheme.
