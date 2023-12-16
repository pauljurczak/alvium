import numpy as np, vmbpy, time, psutil, platform, os, threading, subprocess, argparse, datetime, pathlib

np.set_printoptions(precision=3, suppress=True, linewidth=130)


def frameHandler(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)

  if iFrame[0] < nFrames:
    frameID[iFrame] = frame.get_id()
    frameT[iFrame] = frame.get_timestamp()
    frameErr[0] += (frame.get_status() != vmbpy.FrameStatus.Complete)
    handlerT[iFrame] = time.perf_counter()-t0
    iFrame[0] += 1


if __name__ == '__main__':
  H, W = 240, 816
  X0, Y0 = 0, 192

  parser = argparse.ArgumentParser(description='Single camera capture test.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-n', '--n_frames', type=int, default=10_000, help='number of frames')
  parser.add_argument('-e', '--exposure', type=int, default=500, help='exposure [us]')
  parser.add_argument('-f', '--fps', type=int, default=1200, help='fps')
  args = parser.parse_args()
  nFrames = args.n_frames
  exp = args.exposure
  reqFPS = args.fps
  reqThroughput = int(1*H*W*reqFPS)

  print(
    f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, {pathlib.Path(__file__).name}, '
    f'requested {nFrames:,} frames at {reqFPS:,} fps and {reqThroughput/10**6:6.2f} MB/s')

  try:
    iFrame = np.zeros((1,), dtype='i4')
    handlerT = np.ones((nFrames,), dtype='f4')
    frameID = np.ones((nFrames,), dtype='i4')
    frameErr = np.zeros((1,), dtype='i4')
    frameT = np.ones((nFrames,), dtype='i8')
    scan = np.ones((nFrames,), dtype='u1')
    pid = psutil.Process(os.getpid())
    # os.system('sudo renice -n -20 -p ' + str(os.getpid()))
    pid.nice(-20)

    with vmbpy.VmbSystem.get_instance() as vmb, vmb.get_all_cameras()[0] as cam:
      cam.DeviceLinkThroughputLimit.set(390_000_000)
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
      cam.AcquisitionFrameRate.set(reqFPS)
      # cam.DeviceLinkThroughputLimit.set(390_000_000)
      cam.start_streaming(handler=frameHandler, buffer_count=64)

      while iFrame[0] < nFrames-1:
        time.sleep(0.5)

      cam.stop_streaming()
      p = platform.uname()
      print(f'{p.system} {p.release} {p.machine}  {vmb.get_version()}')
      actFPS = cam.AcquisitionFrameRate.get()
      print(f'Memory available: {psutil.virtual_memory().available/10**9:5.2f} GB  '
            f'Nice: {psutil.Process(os.getpid()).nice()}  USB buffer: '
            f'{subprocess.check_output("cat /sys/module/usbcore/parameters/usbfs_memory_mb", shell=True).decode()[:-1]} MB'
            f'  {actFPS:6.3f} fps  {reqThroughput/10**6:6.2f} MB/s')
    
    handlerT = np.sort(handlerT)*10**3
    dFrameID = np.ediff1d(frameID)
    dsFrameID = np.ediff1d(np.sort(frameID))
    dFrameT = np.ediff1d(frameT)/10**6
    uFrameID, cFrameID = np.unique(dFrameID, return_counts=True)
    uFrameT, cFrameT = np.unique(dFrameT, return_counts=True)

    print(f'Gaps in consecutive Frame IDs: {np.amin(dsFrameID)}, {np.amax(dsFrameID)}.   Bad frames: {frameErr}')
    print(f'Handler times: {np.amin(handlerT):6.3f}  {np.median(handlerT):6.3f}  {handlerT[-10:]} [ms]')
    print(f'\nFrame ID delta:')

    for u, c in zip(uFrameID, cFrameID):
      print(f'{u}: {c}')

    print(f'\nFrame time stamp delta:')

    for u, c in zip(uFrameT, cFrameT):
      print(f'{u}ms: {c}')
  except Exception as e:
    print(f'EXCEPTION: {e} !!!')
