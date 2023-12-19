import numpy as np, vmbpy, time, psutil, platform, os, threading, subprocess, datetime, argparse, pathlib

np.set_printoptions(precision=2, suppress=True, linewidth=130)


def frameHandlerL(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)
  time.sleep(0.0001)

  if iFrame[0] < nFrames:
    frameID[iFrame[0], 0] = frame.get_id()
    threadID[0].add(threading.get_native_id())
    frameErr[0] += (frame.get_status() != vmbpy.FrameStatus.Complete)
    handlerT[iBatch*nFrames+iFrame[0], 0] = time.perf_counter()-t0
    iFrame[0] += 1


def frameHandlerR(cam, stream, frame):
  t0 = time.perf_counter()
  cam.queue_frame(frame)
  time.sleep(0.0001)

  if iFrame[1] < nFrames:
    frameID[iFrame[1], 1] = frame.get_id()
    threadID[1].add(threading.get_native_id())
    frameErr[1] += (frame.get_status() != vmbpy.FrameStatus.Complete)
    handlerT[iBatch*nFrames+iFrame[1], 1] = time.perf_counter()-t0
    iFrame[1] += 1


if __name__ == '__main__':
  H, W = 240, 816
  X0, Y0 = 0, 192

  parser = argparse.ArgumentParser(description='Dual camera capture test.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-n', '--n_frames', type=int, default=600, help='number of frames')
  parser.add_argument('-b', '--n_batches', type=int, default=10, help='number of frames')
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
    iFrame = np.zeros((2,), dtype='i4')
    handlerT = np.ones((nBatches*nFrames, 2), dtype='f4')
    frameID = np.ones((nFrames, 2), dtype='i8')
    threadID = [set(), set()]
    frameErr = np.zeros((2,), dtype='i4')
    batchT = np.ones((nBatches,), dtype='f4')
    nLostFrames = 0
    kernel = np.zeros((5, 5), dtype='i4')
    kernel[1:4, 1:4] = np.ones((3, 3), dtype='i4')
    pid = psutil.Process(os.getpid())
    pid.nice(-20)
    # os.system('sudo renice -n -20 -p ' + str(os.getpid()))

    with (vmbpy.VmbSystem.get_instance() as vmb, 
          vmb.get_camera_by_id('DEV_1AB22C039748') as camL,
          vmb.get_camera_by_id('DEV_1AB22C038A31') as camR):
      for cam in [camL, camR]:
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
        cam.ConvolutionMode.set('CustomConvolution')

        for i, v in enumerate(kernel.ravel()):
          cam.CustomConvolutionValueSelector.set(i)
          cam.CustomConvolutionValue.set(v)

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

      for iBatch in range(nBatches):
        iFrame = np.zeros((2,), dtype='i4')
        t0 = time.perf_counter()
        camR.start_streaming(handler=frameHandlerR)  # start the slave camera first
        camL.start_streaming(handler=frameHandlerL)

        while iFrame[0] < nFrames-1:
          time.sleep(0.1)

        camL.stop_streaming()
        camR.stop_streaming()
        batchT[iBatch] = time.perf_counter()-t0
        nLostFrames += np.count_nonzero(frameID >= nFrames)

      actFPS = camL.AcquisitionFrameRate.get()
      actExp = camL.ExposureTime.get()

    p = platform.uname()
    handlerT = np.sort(handlerT, axis=0)*10**3
    batchT = np.sort(batchT-nFrames/actFPS)*10**3
    print(
      f'{p.processor} {p.version[:38]}  {vmb.get_version()}\n'
      f'Memory available: {psutil.virtual_memory().available/10**9:5.2f}GB  '
      f'Nice: {psutil.Process(os.getpid()).nice()}  USB buffer: '
      f'{subprocess.check_output("cat /sys/module/usbcore/parameters/usbfs_memory_mb", shell=True).decode()[:-1]}MB'
      f'  {actFPS:5.1f}fps  {actExp:5.1f}us  {H*W*actFPS/10**6:5.1f}MB/s\n'   
      f'Total frames lost: {nLostFrames}, bad frames: {frameErr[0]}\n'
      f'Left callback: {np.amin(handlerT[:, 0]):6.2f}  {np.median(handlerT[:, 0]):6.2f}  {handlerT[-10:, 0]} [ms]\n'
      f'Right callback: {np.amin(handlerT[:, 1]):6.2f}  {np.median(handlerT[:, 1]):6.2f}  {handlerT[-10:, 1]} [ms]\n'
      f'Batch overhead: {np.amin(batchT):6.3f}  {np.median(batchT):6.3f}  {batchT[-10:]} [ms]\n'
      f'Thread IDs: {threadID}\n'
      f'----------------------------------------------------------------------------------\n')
  except Exception as e:
    print(f'EXCEPTION: {e} !!!')
