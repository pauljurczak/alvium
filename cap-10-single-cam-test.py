import numpy as np, vmbpy, time, psutil, platform

np.set_printoptions(precision=3, suppress=True, linewidth=130)


def frameHandler(cam, stream, frame):
  global iFrame, t0, t1

  handlerT0 = time.perf_counter()

  if iFrame == 0: 
    t0 = time.perf_counter()
  elif iFrame == nFrames:
    t1 = time.perf_counter()

  cam.queue_frame(frame)

  if iFrame < nFrames:
    frameID[iFrame] = frame.get_id()
    frameT[iFrame] = frame.get_timestamp()
    handlerT[iFrame] = time.perf_counter()-handlerT0
    iFrame += 1


if __name__ == '__main__':
  H, W = 270, 816
  X0, Y0 = 0, 176

  try:
    iFrame = 0
    nFrames = 10**5
    exp = 500
    fps = 1200
    handlerT = np.ones((nFrames,), dtype='f4')
    frameID = np.ones((nFrames,), dtype='i4')
    frameT = np.ones((nFrames,), dtype='i8')
    scan = np.ones((nFrames,), dtype='u1')

    with (vmbpy.VmbSystem.get_instance() as vmb, 
          vmb.get_camera_by_id('DEV_1AB22C039748') as cam):
      cam.DeviceLinkThroughputLimit.set(450_000_000)
      cam.ExposureAuto.set(False)
      cam.ExposureTime.set(exp)
      cam.GainAuto.set(False)
      cam.SensorBitDepth.set('Bpp8')
      cam.set_pixel_format(vmbpy.PixelFormat.Mono8)
      cam.Height.set(H)
      cam.Width.set(W)
      cam.OffsetX.set(X0)
      cam.OffsetY.set(Y0)
      cam.AcquisitionFrameRateEnable.set(True)
      cam.AcquisitionFrameRate.set(fps)
      cam.start_streaming(handler=frameHandler, buffer_count=64)

      while iFrame < nFrames-1:
        time.sleep(0.5)

      cam.stop_streaming()
      p = platform.uname()
      print(f'{p.system} {p.release} {p.machine}')
      print(f'{vmb.get_version()}  Memory available: {psutil.virtual_memory().available:,}')
      print(f'Requested/delivered {cam.AcquisitionFrameRate.get():6.3f}/{nFrames/(t1-t0):6.3f} fps  {H*W*8*fps:,} bps  {nFrames} frames')
    
    handlerT = np.sort(handlerT)*10**3
    dFrameID = np.ediff1d(frameID)
    dsFrameID = np.ediff1d(np.sort(frameID))
    dFrameT = np.ediff1d(frameT)/10**6
    uFrameID, cFrameID = np.unique(dFrameID, return_counts=True)
    uFrameT, cFrameT = np.unique(dFrameT, return_counts=True)

    print(f'Gaps in consecutive Frame IDs: {np.amin(dsFrameID)}, {np.amax(dsFrameID)}')
    print(f'Handler times: {np.amin(handlerT):6.3f}  {np.median(handlerT):6.3f}  {handlerT[-10:]} [ms]')
    print(f'\nFrame ID delta:')

    for u, c in zip(uFrameID, cFrameID):
      print(f'{u}: {c}')

    print(f'\nFrame time stamp delta:')

    for u, c in zip(uFrameT, cFrameT):
      print(f'{u}ms: {c}')
  except Exception as e:
    print(f'EXCEPTION: {e} !!!')
