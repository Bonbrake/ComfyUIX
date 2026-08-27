# Bolt Performance Journal

## 2026-08-27 - Fallback to NumPy `np.gradient` when `scipy` is not installed
**Learning:** `scipy` is not included in `requirements.txt`. Code importing `scipy.ndimage.sobel` failed silently, causing PBR map generation to skip generating normal, roughness, height, and AO texture maps. Using `np.gradient` as a fallback allows computing image gradients cleanly without extra dependencies.
**Action:** When computing spatial gradients or filters, check for `scipy` optional imports and provide a native `numpy` fallback like `np.gradient` to maintain high performance and prevent missing outputs.
