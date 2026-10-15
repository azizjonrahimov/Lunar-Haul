"""Learned lander: lunar/Descent-v0 environment, numpy policy runtime, PPO training, export, evaluation.

    physics.py   3-DoF descent dynamics (pure numpy, ported to JS)
    classes.py   CLPS / MK1 / LARGE constants with flags and sources
    env.py       Gymnasium env (needs the [ml] extra)
    policy.py    MlpPolicy.from_json(path).act(obs): numpy forward pass of an exported policy
    export.py    SB3 PPO model -> lunarsim-policy v1 JSON + <id>.check.json
    train.py     PPO training (python -m lunarsim.lander.train --cls CLPS --variant baseline --steps 300000)
    evaluate.py  Monte Carlo outcome tables, classical ZEM/ZEV baseline

Importing this package registers "lunar/Descent-v0" when gymnasium is installed.
"""
from .classes import CLASSES, LanderClass  # noqa: F401

try:
    import gymnasium as _gym
    from .env import ENV_ID as _ENV_ID
    if _ENV_ID not in _gym.registry:
        _gym.register(id=_ENV_ID, entry_point="lunarsim.lander.env:DescentEnv")
except ImportError:  # [ml] extra not installed
    pass
