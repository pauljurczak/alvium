import numpy as np, vmbpy, time, psutil, platform, os, threading, subprocess, argparse, datetime, pathlib

np.set_printoptions(precision=2, suppress=True, linewidth=130)


def frameHandler(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)
  time.sleep(0.0001)

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
  parser.add_argument('-n', '--n_frames', type=int, default=600, help='number of frames')
  parser.add_argument('-b', '--n_batches', type=int, default=1000, help='number of frames')
  parser.add_argument('-e', '--exposure', type=int, default=500, help='exposure [us]')
  parser.add_argument('-f', '--fps', type=int, default=1200, help='fps')
  args = parser.parse_args()
  nFrames = args.n_frames
  nBatches = args.n_batches
  exp = args.exposure
  reqFPS = args.fps
  reqThroughput = int(1*H*W*reqFPS)

  print(
    f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, {pathlib.Path(__file__).name}, '
    f'requested {nBatches} batches of {nFrames:,} frames at {reqFPS:,} fps and {reqThroughput/10**6:6.2f} MB/s')

  try:
    iFrame = np.zeros((1,), dtype='i4')
    handlerT = np.ones((nFrames,), dtype='f4')
    frameID = np.ones((nFrames,), dtype='i4')
    frameErr = np.zeros((1,), dtype='i4')
    frameT = np.ones((nFrames,), dtype='i8')
    scan = np.ones((nFrames,), dtype='u1')
    batchT = np.ones((nBatches,), dtype='f4')
    nLostFrames = 0
    kernel = np.zeros((5, 5), dtype='i4')
    kernel[1:4, 1:4] = np.ones((3, 3), dtype='i4')
    pid = psutil.Process(os.getpid())
    pid.nice(-20)

    with vmbpy.VmbSystem.get_instance() as vmb, vmb.get_all_cameras()[0] as cam:
      # cam.DeviceLinkThroughputLimit.set(reqThroughput)
      cam.DeviceLinkThroughputLimit.set(400_000_000)
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
      cam.ConvolutionMode.set('CustomConvolution')

      for i, v in enumerate(kernel.ravel()):
        cam.CustomConvolutionValueSelector.set(i)
        cam.CustomConvolutionValue.set(v)

      for i in range(nBatches):
        iFrame[0] = 0
        t0 = time.perf_counter()
        cam.start_streaming(handler=frameHandler, buffer_count=64)

        while iFrame[0] < nFrames-1:
          time.sleep(0.001)

        cam.stop_streaming()
        batchT[i] = time.perf_counter()-t0
        nLostFrames += np.count_nonzero(frameID >= nFrames)

      p = platform.uname()
      print(f'{p.system} {p.release} {p.machine}  {vmb.get_version()}')
      actFPS = cam.AcquisitionFrameRate.get()
      print(f'Memory available: {psutil.virtual_memory().available/10**9:5.2f} GB  '
            f'Nice: {psutil.Process(os.getpid()).nice()}  USB buffer: '
            f'{subprocess.check_output("cat /sys/module/usbcore/parameters/usbfs_memory_mb", shell=True).decode()[:-1]} MB'
            f'  {actFPS:6.3f} fps  {reqThroughput/10**6:6.2f} MB/s')
    
    print(f'Total frames lost: {nLostFrames}, bad frames: {frameErr[0]}')
    handlerT = np.sort(handlerT)*10**3
    batchT = np.sort(batchT-nFrames/actFPS)*10**3
    dFrameID = np.ediff1d(frameID)
    dsFrameID = np.ediff1d(np.sort(frameID))
    uFrameID, cFrameID = np.unique(dFrameID, return_counts=True)

    print(f'Gaps in consecutive Frame IDs: {np.amin(dsFrameID)}, {np.amax(dsFrameID)}.   Bad frames: {frameErr}')
    print(f'Handler times: {np.amin(handlerT):6.3f}  {np.median(handlerT):6.3f}  {handlerT[-10:]} [ms]')
    print(f'Batch overhead: {np.amin(batchT):6.3f}  {np.median(batchT):6.3f}  {batchT[-10:]} [ms]')
    print(f'\nFrame ID delta:')

    for u, c in zip(uFrameID, cFrameID):
      print(f'{u}: {c}')
  except Exception as e:
    print(f'EXCEPTION: {e} !!!')
