# Alvium
Debugging lost frames on AVT Alvium 1800 U-052m camera with VmbPy.

# Tests
Results of running `cap-10-single-cam-test.py` showing gaps in consecutive captured frames.

## Desktop PC 
The largest gap misses 7 frames:
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

## Jetson Orin
No problems after increasing frame buffer count to 64.
```
Linux 5.10.104-tegra aarch64
vmbpy: 1.0.3 (using VmbC: 1.0.3, VmbImageTransform: 2.0)  Memory available: 28.05 GB
Requested/delivered 1200.000/1197.265 fps  2,115,072,000 bps  100000 frames
Gaps in consecutive Frame IDs: 1, 1
Handler times:  0.229   0.347  [1.139 1.143 1.144 1.169 1.2   1.202 1.251 1.411 2.843 3.66 ] [ms]

Frame ID delta:
1: 99999

Frame time stamp delta:
0.8334ms: 99325
0.8335ms: 674
```

## Raspberry Pi 4
C interface problems, huge gaps, including frame ID ordering:
```
Exception ignored on calling ctypes callback function: <bound method Stream.__frame_cb_wrapper of <vmbpy.stream.Stream object at 0x7f9b178690>>
Traceback (most recent call last):
  File "/home/paul/.local/lib/python3.11/site-packages/vmbpy/stream.py", line 554, in __frame_cb_wrapper
    raise e
  File "/home/paul/.local/lib/python3.11/site-packages/vmbpy/stream.py", line 546, in __frame_cb_wrapper
    context.frames_handler(self._parent_cam, self, frame)
  File "/home/paul/profiler/cap-10-single-cam-test.py", line 20, in frameHandler
    frameT[iFrame] = frame.get_timestamp()
    ~~~~~~^^^^^^^^
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
Linux 6.1.21-v8+ aarch64
vmbpy: 1.0.3 (using VmbC: 1.0.3, VmbImageTransform: 2.0)  Memory available:  7.37 GB
Requested/delivered 1200.000/846.758 fps  2,115,072,000 bps  100000 frames
Gaps in consecutive Frame IDs: 0, 8
Handler times:  0.733   0.988  [3.24  3.261 3.583 3.62  3.862 3.902 4.997 5.005 5.162 5.775] [ms]

Frame ID delta:
-136: 1
-135: 1
-129: 1
-120: 1
-111: 1
-108: 1
-106: 1
```
Full report in `cap-10-on-RPi4.txt` file.
