# Source provenance

The benchmark manifest pins these public source revisions:

| Source | Revision | Role |
| --- | --- | --- |
| [Polytof](https://github.com/ZIB-IOL/polytof/tree/1ab70261c749efe0be1d459ac00b7ffe2beb876e) | `1ab70261c749efe0be1d459ac00b7ffe2beb876e` | Tensors, CP/Waring witnesses, and basis transforms consumed by the verifier |
| [Vandaele circuits](https://github.com/VivienVandaele/quantum-circuit-optimization/tree/231e6fe9f92d5bb1ebf7459c2a9233f5e74d148e) | `231e6fe9f92d5bb1ebf7459c2a9233f5e74d148e` | Original circuit provenance |
| [AlphaTensor-Quantum](https://github.com/google-deepmind/alphatensor_quantum/tree/3def81a2a42666416a4a8041eea6e1bc98bc8e9f) | `3def81a2a42666416a4a8041eea6e1bc98bc8e9f` | Circuit provenance and prior certificate references |
| [VarTODD](https://github.com/DanilkaFish/VarTodd/tree/9c743e0e7440e6444d6f4a9230c51c1bdac6badb) | `9c743e0e7440e6444d6f4a9230c51c1bdac6badb` | Separately reported upper-bound provenance |

Only Polytof is read during the reproducibility run. No other source checkout is needed.

The 25 standard instances use IDs `0800`–`0824`, except that QCLA Com_7 uses `0117` because its released phase witness is shorter. The 35 application instances use IDs `0134`–`0168`. The mixed-degree QFT4 target is excluded. For a CP file with several candidates, the verifier checks its first candidate; the complete input file is hashed.

Related primary sources:

- [Tensor Decomposition for Non-Clifford Gate Minimization](https://arxiv.org/abs/2602.15285).
- [Quantum Circuit Optimization with AlphaTensor](https://doi.org/10.1038/s42256-025-01001-1).
- [LLM-Guided Evolutionary Search for Algebraic T-Count Optimization, v2](https://arxiv.org/abs/2603.29894v2), Table II for the two separately reported VarTODD bounds.

Polytof's pinned repository carries an MIT license, copyright 2026 Kirill Khoruzhii. No Polytof code or data files are copied into this repository; its [license](https://github.com/ZIB-IOL/polytof/blob/1ab70261c749efe0be1d459ac00b7ffe2beb876e/LICENSE) governs the upstream checkout.

The verifier, tests, manifest, and table excerpt were copied byte-for-byte from the accompanying manuscript workspace; [snapshot hashes](source_snapshot.json) identify those files and the associated manuscript version. The record's source hashes identify exactly the code used for that run. This repository's preparation and the earlier verification workflow used OpenAI Codex; the evidence consists of executable checks and their recorded outputs, not model-generated numerical claims.
