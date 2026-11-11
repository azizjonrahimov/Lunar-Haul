"""B-96 (E56): a small neural network that tells when another rover's position reports are wrong.

Modules: tracks (1 Hz motion from the ATC traces), faults (named fault definitions and the honest disturbances),
dataset (deterministic builder and splits), baselines (chi-square, windowed chi-square, CUSUM, logistic regression),
model (the causal 1D convolutional network and its JSON codec), train, evaluate, landscape (Li et al. 2018).
Everything here is simulated; see results/E56_README.md for the limits.
"""
