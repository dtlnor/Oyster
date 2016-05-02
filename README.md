# Oyster
©2016 IFeelBloated, Oyster Python Module for VapourSynth
## License
LGPL v2.1
## Description
Oyster is a top class de-noising filter against compression artifacts in terms of quality, it is outrageously slow and deadly expensive at computational costs.

Each pixel will be restored by the weighted average of its neighbors, weights generated by Block-Matching and Pixel-Matching algorithms, spatially and temporally.

It is designed for photographic videos, but works on CGI like cartoons and anime also.
## Requirements
- NNEDI3
- KNLMeansCL
- BM3D
- FMTConv
- MVTools (floating point ver)

## Function List
- Basic
- Final

## Formats
- Bitdepth: 32bits floating point
- Color Space: Gray, RGB, YUV 4:4:4 (subsampled YUV formats are not supported)
- Scan Type: Progressive

## Notes
- DO NOT upsample your video to YUV 4:4:4 or RGB before processing if it's not natively full-sampled, just pass the luminance plane as a gray clip and merge the processed luma with the source chroma, fake 4:4:4 is toxic as the low-res chroma will jeopardize the correctness of weight calculation (especially on Pixel-Matching), and then the quality degradation on luma sets in.
- You might wanna try waifu2x instead if your video is of CGI-like content, Oyster is times slower than waifu2x and designed specifically for photographic videos.

## Details
### Basic
The basic estimating features 3 stages:

- Cleansing<br />
  an NLMeans filtering with aggressive parameters will be applied to wipe all the artifacts away
- Motion Compensation<br />
  subpixel Block-Matching based motion compensation will be applied to recover significant structure loss.
- Refining (optional) <br />
  Pixel-Matching looped refining will be performed to recover fine and delicate details, disabled at level=2

it serves as a reference to the later final estimating
```python
Basic (src, level=1, \
       radius=6, h=6.4, pel=4, pel_precise=True, thscd1=10000, thscd2=255, \
       deblock=True, deblock_thr=0.03125, deblock_elast=0.015625, \
       lowpass=8)
```
- src<br />
  clip to be processed
- level<br />
  could be 1 or 2, default 1. de-noise level, level1 works on typical compression artifacts, level2 works on severe compression artifacts
