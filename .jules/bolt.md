# Bolt Performance Journal

## 2026-08-31 - Decoupled NumPy & SciPy in PBR Map Generation
**Learning:** `scipy` is not listed in `requirements.txt`, which caused `generate_pbr_maps` to hit an `ImportError` on systems without `scipy`, completely skipping the generation of normal, roughness, height, and ambient occlusion maps. Using `np.gradient` as a fallback spatial derivative calculation allows fast (~30ms) generation of all PBR texture maps using standard `numpy`.
**Action:** Decouple `numpy` from optional sub-packages like `scipy.ndimage` and provide vectorized NumPy fallbacks for image filter computations.
