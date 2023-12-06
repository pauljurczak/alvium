# Alvium
Debugging lost frames on AVT Alvium 1800 U-052m camera with VmbPy.

# Test
Results of running `cap-10-single-cam-test.py` showing gaps in consecutive captured frames (the largest one misses 7 frames):
```
Linux 6.2.0-37-generic x86_64
vmbpy: 1.0.3 (using VmbC: 1.0.3, VmbImageTransform: 2.0)  Memory available: 59,839,139,840
Requested/delivered 1200.000/1197.461 fps  2,115,072,000 bps  100000 frames
Gaps in consecutive Frame IDs: 1, 8
Handler times:  0.093   0.102  [ 2.43   2.521  3.031  3.974  4.115  4.125  4.585  5.038  9.774 12.322] [ms]

Frame ID delta:
1: 99991
2: 4
3: 2
7: 1
8: 1

Frame time stamp delta:
0.8334ms: 99317
0.8335ms: 674
1.6668ms: 4
2.5002ms: 2
5.8338ms: 1
6.6672ms: 1
```
