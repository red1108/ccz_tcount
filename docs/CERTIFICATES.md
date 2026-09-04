# What a certificate proves

The target is a fixed alternating trilinear form over GF(2), representing the non-Clifford part of a pure-cubic phase block. Its phase count is the minimum number of odd parity phases, with Clifford corrections free. It is not an unrestricted Clifford+T circuit optimum.

## Lower bounds

The active dimension `d` is the rank of the contraction map `x -> Theta(x,.,.)`. It is computed from the target, not inferred from the number or span of the supplied factors.

For a nonzero target:

$$p(\Theta)\ge2d+1,\qquad c(\Theta)\ge\lceil d/3\rceil.$$

Briefly, the parity matrix of a phase presentation has independent rows on the active space. Alternation implies that its row space is self-orthogonal, so a `q`-term presentation satisfies `q >= 2d`. A minimum nonzero presentation is odd: an even one can be translated by one of its own labels to create a deletable zero. This gives `2d+1`. A CCZ atom involves at most three active directions, giving the other lower bound.

The zero target is handled separately, with both minima equal to zero.

## Constructed upper bounds

Every nonzero CCZ atom has a seven-term phase presentation. Odd presentations can be merged while saving one term, giving `6m+1` for a displayed `m`-atom description.

When the factor matrix has a dependence, the converter groups it by interaction and uses the resulting directions as merge pivots. One tracked label reaches zero. Zero deletion, pair cancellation, and even-length shortening produce a shorter presentation. Zero partial targets are handled explicitly; the algorithm does not need to assume that the supplied CCZ description is minimal.

The certifier can also use a supplied phase witness or a circuit's existing T/TDG phases. It selects the shortest candidate it constructed and **checks the resulting full symmetric signature against the target** before reporting the upper bound. The CCZ upper bound uses a valid supplied decomposition or the coordinate cubic expansion.

For full-rank and rank-defect-one minimum descriptions, these constructions meet the lower bound. Other inputs may retain a gap. A bounded verdict is a result, not an error: it states what the current witnesses prove and does not claim that either endpoint is attainable as the optimum.

## Interpreting exactness

An exact phase verdict means that a checked witness meets `2d+1` (or zero for the zero target). CCZ exactness is checked separately against `ceil(d/3)`.

If your current witness is longer than the certified value, the target's optimum has been certified but your witness is not minimal. Optional-witness metadata reports this distinction. A generated phase witness may require a Clifford correction to implement the original unitary exactly.

The benchmark-record classifications C0/C1/L/U are retained for the historical Polytof runs. The custom API uses the simpler `exact`/`bounded` phase verdict and reports CCZ exactness independently.
