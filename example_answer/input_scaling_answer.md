# Input Scaling in ESNs — Literature Overview

---

## damicelli_2022_braina · Damicelli et al. (2022)

Most explicit treatment, with grid search.

> "Optionally, the input can be scaled by a factor ξ ∈ ℝ (input scaling) before been fed into the network." (p. 11)

> "spectral radius of the reservoir connectivity matrix ρ = {0.91, 0.93, ..., 0.99}, input scaling ξ = {10⁻⁹, 10⁻⁸, ..., 10⁰}, leakage rate α = {0.6, 0.8, 1} and bias b = {0, 1}." (p. 12)

**Best found value:**
> "Spectral radius ρ = 0.99, Input scaling ξ = 10⁻⁵, Leakage rate α = 1, Bias b = 1." (p. 12)

---

## fakhar_2025_human · Fakhar et al. (2025)

> "W_in were drawn from a uniform distribution in [−1, 1] and scaled by a factor of 10⁻⁹." (p. 27 — note: PDF likely OCR artefact for 10⁻⁹)

**Personal note:** `w_in: uniform dist in [-1,1] scaled by 1e-5` → ξ = 10⁻⁵

---

## lukosevicius_2012_practical · Lükosevicius (2012)

> "often all the columns of W_in are scaled together using a single scaling value." (p. 666)

> "for very linear tasks W_in should be small, letting units operate around the 0 point where their activation tanh(·) is virtually linear." (p. 667)

No specific value given — treated as a task-dependent hyperparameter.

---

## farkas_2016_computationala · Farkaš & Benušková (2016)

> "We choose elements of the input weight vector w_in randomly from uniform distribution U(−τ, τ)." (p. 4)

> "Designing an ESN involves scaling the input weights (parameter τ) or reservoir weights." (p. 3)

Parameter: τ (half-width of uniform distribution). No single value given; swept as part of the criticality analysis.

---

## jaeger_2007_optimization · Jaeger et al. (2007)

> "Input weights were randomly sampled from a uniform distribution over [−1, 1]. There were no output feedbacks." (p. 35)

> "The input scaling was kept at a value of s_in = 1.5 from the preliminary experiments." (p. 29)

Two different values across experiments: s_in = 1.5 (one task); U(−1, 1) unscaled (another).

---

## milisav_2025_neuromorphic · Milisav et al. (2025)

> "W_in is the binary input matrix mapping the input signal to the input nodes." (p. 13)

Binary input matrix — no continuous scaling applied; input fed directly.

---

## morra_2022_imposing · Morra et al. (2022)

> "W_in is a weight vector between the input and reservoir layers (W_in ∈ ℝ^{N×(1+Nu)})." (p. 2)

Follows Suárez convention: drawn from a uniform distribution on [−1, 1] (p. 3 of morra_2023_using).

---

## morra_2025_connectomes · Morra et al. (2025)

> "the input strength parameter r ... ẋ(t) = c·x(t) + tanh[W·x(t) + r·W_in·u(t)]." (p. 6)

Explicit `r` as input strength parameter — separate from W_in initialization.

---

## nguyen_2025_accessing · Nguyen et al. (2025)

> "W_ij = C if i = j mod n, else 0, where C is a predetermined input factoring constant, identical for all input features and read-in nodes." (p. 2)

Diagonal/structured input matrix with scalar C — different architecture from standard ESN.

---

## flynn_2021_multifunctionalitya · Flynn et al. (2021)

> "ṙ(t) = γ[−r(t) + tanh(M·r(t) + σ·W_in·u(t))]." (p. 3)

> "The input signal u(t) is projected by σW_in to drive a response from the reservoir." (p. 4)

Parameter: σ as input scaling prefactor.

---

## dambre_2012_information · Dambre et al. (2012)

> "three values of the input scaling parameter i. For very small input scaling, the capacity C_TOT remains close to N up to the bifurcation point of the undriven system and then drops off rapidly. As the input scaling increases..." (p. 5)

Theoretical treatment — input scaling as `i`, with explicit analysis of its effect on total capacity.

---

## suarez_2021_learning / suarez_2020_learning · Suárez et al.

> "u(t) = (u₁(t), ..., u_K(t)) is a K-dimensional input signal weighted by the input matrix W_in (usually a constant, unless stated otherwise)." (p. 13)

No explicit scaling value annotated — W_in treated as fixed constant.

---

## Summary

| BibTeX key                     | Symbol            | Value / range                                  |
|-------------------------------|-------------------|------------------------------------------------|
| damicelli_2022_braina          | ξ (grid-searched) | **10⁻⁵** (optimal); swept 10⁻⁹–10⁰            |
| fakhar_2025_human              | ξ × U(−1,1)       | **10⁻⁵** (personal note) / 10⁻⁹ (PDF)         |
| jaeger_2007_optimization       | s_in              | **1.5** (one task); U(−1,1) unscaled (another) |
| farkas_2016_computationala     | τ in U(−τ,τ)      | swept; no fixed value                          |
| morra_2025_connectomes         | r (strength param)| separate from W_in                             |
| flynn_2021_multifunctionalitya | σ × W_in          | σ as free parameter                            |
| dambre_2012_information        | i                 | theoretical analysis only                      |
| nguyen_2025_accessing          | C (diagonal)      | fixed constant                                 |
| milisav_2025_neuromorphic      | binary W_in       | none                                           |
| lukosevicius_2012_practical    | task-dependent    | no specific value                              |
| suarez_2021_learning           | W_in = constant   | no specific value annotated                    |