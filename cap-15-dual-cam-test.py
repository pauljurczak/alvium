import numpy as np, vmbpy, time, psutil, platform, os, threading, subprocess, datetime, argparse, pathlib

np.set_printoptions(precision=3, suppress=True, linewidth=130)


def frameHandlerL(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)

  if iFrame[0] < nFrames:
    frameID[iFrame[0], 0] = frame.get_id()
    threadID[0].add(threading.get_native_id())
    handlerT[iFrame[0], 0] = time.perf_counter()-t0
    iFrame[0] += 1


def frameHandlerR(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)

  if iFrame[1] < nFrames:
    frameID[iFrame[1], 1] = frame.get_id()
    handlerT[iFrame[1], 1] = time.perf_counter()-t0
    threadID[1].add(threading.get_native_id())
    iFrame[1] += 1


if __name__ == '__main__':
  H, W = 240, 816
  X0, Y0 = 0, 192

  parser = argparse.ArgumentParser(description='Dual camera capture test.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-n', '--n_frames', type=int, default=10_000, help='number of frames')
  parser.add_argument('-e', '--exposure', type=int, default=500, help='exposure [us]')
  parser.add_argument('-f', '--fps', type=int, default=1200, help='fps')
  args = parser.parse_args()
  nFrames = args.n_frames
  exp = args.exposure
  reqFPS = args.fps
  print(
    f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}, {pathlib.Path(__file__).name}, '
    f'requested {nFrames:,} frames at {reqFPS:,}fps, exposure {exp}us')

  try:
    iFrame = np.zeros((2,), dtype='i4')
    handlerT = np.ones((nFrames, 2), dtype='f4')
    frameID = np.ones((nFrames, 2), dtype='i8')
    threadID = [set(), set()]
    pid = psutil.Process(os.getpid())
    # os.system('sudo renice -n -20 -p ' + str(os.getpid()))
    pid.nice(-20)

    with (vmbpy.VmbSystem.get_instance() as vmb, 
          vmb.get_camera_by_id('DEV_1AB22C039748') as camL,
          vmb.get_camera_by_id('DEV_1AB22C038A31') as camR):
      for cam in [camL, camR]:
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

      camL.AcquisitionFrameRateEnable.set(True)
      camL.AcquisitionFrameRate.set(reqFPS)
      camL.LineSelector.set('Line0')
      camL.LineMode.set('Output')
      camL.LineSource.set('ExposureActive')
      camR.LineSelector.set('Line0')
      camR.LineMode.set('Input')
      camR.TriggerSelector.set('FrameStart')
      camR.TriggerActivation.set('RisingEdge')
      camR.TriggerSource.set('Line0')
      camR.TriggerMode.set(True)
      camR.start_streaming(handler=frameHandlerR)  # start the slave camera first
      camL.start_streaming(handler=frameHandlerL)

      while iFrame[0] < nFrames-1:
        time.sleep(0.5)

      camL.stop_streaming()
      camR.stop_streaming()
      actFPS = camL.AcquisitionFrameRate.get()
      actExp = camL.ExposureTime.get()

    p = platform.uname()
    handlerT = np.sort(handlerT, axis=0)*10**3
    dFrameID = frameID[1:, :]-frameID[:-1, :]
    uFrameID2 = np.unique(frameID[frameID < nFrames])
    print(
      f'{p.processor} {p.version[:38]}  {vmb.get_version()}\n'
      f'Memory available: {psutil.virtual_memory().available/10**9:5.2f}GB  '
      f'Nice: {psutil.Process(os.getpid()).nice()}  USB buffer: '
      f'{subprocess.check_output("cat /sys/module/usbcore/parameters/usbfs_memory_mb", shell=True).decode()[:-1]}MB'
      f'  {actFPS:5.1f}fps  {actExp:5.1f}us  {H*W*actFPS/10**6:5.1f}MB/s\n'    
      f'Left handler times [ms]: {np.amin(handlerT[:, 0]):6.3f} {np.median(handlerT[:, 0]):6.3f} {handlerT[-10:, 0]}\n'
      f'Right handler times [ms]: {np.amin(handlerT[:, 1]):6.3f} {np.median(handlerT[:, 1]):6.3f} {handlerT[-10:, 1]}\n'
      f'\nLeft camera {frameID[-1, 0]-nFrames+1} frames lost, ID delta:')

    for u, c in zip(*np.unique(dFrameID[:, 0], return_counts=True)):
      print(f'{u}: {c:,}')

    print(f'\nRight camera {frameID[-1, 1]-nFrames+1} frames lost, ID delta:')

    for u, c in zip(*np.unique(dFrameID[:, 1], return_counts=True)):
      print(f'{u}: {c:,}')

    print(f'\nBoth cameras {nFrames-uFrameID2.size} frames lost, ID delta:')

    for u, c in zip(*np.unique(uFrameID2[1:]-uFrameID2[:-1], return_counts=True)):
      print(f'{u}: {c:,}')

    print(f'Thread IDs: {threadID}')
  except Exception as e:
    print(f'EXCEPTION: {e} !!!')
