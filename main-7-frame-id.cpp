#include "common.hpp"
#include "VmbC/VmbC.h"
#include <sys/resource.h>

constexpr int N_FRAMES = 600;

vector<float> handlerTL, handlerTR;
array<vector<uint64_t>, 2> frameID;


void VMB_CALL leftFrameCallback(const VmbHandle_t hCamera, const VmbHandle_t hStream, VmbFrame_t *pFrame) {
  if (frameID[0].size() < N_FRAMES) 
    frameID[0].push_back(pFrame->receiveStatus == VmbFrameStatusComplete ? pFrame->frameID : -1);

  VmbCaptureFrameQueue(hCamera, pFrame, leftFrameCallback);
}


void VMB_CALL rightFrameCallback(const VmbHandle_t hCamera, const VmbHandle_t hStream, VmbFrame_t *pFrame) {
  if (frameID[1].size() < N_FRAMES) 
    frameID[1].push_back(pFrame->receiveStatus == VmbFrameStatusComplete ? pFrame->frameID : -1);

  VmbCaptureFrameQueue(hCamera, pFrame, rightFrameCallback);
}


int main() {
  // vector<int> v{1, 2, 3, 4};
  // ranges::transform(v, v.begin(), [](auto e){return 2*e;});
  // print("{}\n", v);
  // exit(0);

  constexpr int H = 240, W = 816;
  constexpr int X0 = 0, Y0 = 192;
  constexpr int USB_LIMIT = 450'000'000;
  constexpr double EXP = 500;
  constexpr double FPS = 1200;
  constexpr int N_BATCHES = 5;
  constexpr int N_BUFFERS = 500;
  constexpr auto OK = VmbErrorSuccess;
  constexpr array<array<int, 5>, 5> KERNEL{{
    {{0, 0, 0, 0, 0}}, 
    {{0, 1, 1, 1, 0}}, 
    {{0, 1, 1, 1, 0}}, 
    {{0, 1, 1, 1, 0}}, 
    {{0, 0, 0, 0, 0}}}};
  VmbVersionInfo_t vi;
  vector<int> errors;

  printVersion();
  setpriority(PRIO_PROCESS, 0, -20);
  print("Process priority: {}\n", getpriority(PRIO_PROCESS, 0));

  if (VmbVersionQuery(&vi, sizeof(vi)) != OK)
    throw runtime_error("VmbVersionQuery() failed!!!");

  print("Vimba version: {}.{}.{}\n", vi.major, vi.minor, vi.patch);

  VmbHandle_t camL, camR;
  int err = 0;

  if (VmbStartup(NULL) != VmbErrorSuccess)
    throw runtime_error("vmb.Startup() failed!!!");
  
  if (VmbCameraOpen("DEV_1AB22C039748", VmbAccessModeFull, &camL) != VmbErrorSuccess)
    throw runtime_error("Can't open the left camera!!!");

  if (VmbCameraOpen("DEV_1AB22C038A31", VmbAccessModeFull, &camR) != VmbErrorSuccess)
    throw runtime_error("Can't open the right camera!!!");

  array<VmbHandle_t, 2> cameras{camL, camR};

  for (auto cam: cameras) {
    errors.push_back(VmbFeatureIntSet(cam, "DeviceLinkThroughputLimit", USB_LIMIT));
    errors.push_back(VmbFeatureEnumSet(cam, "ExposureAuto", "Off"));
    errors.push_back(VmbFeatureFloatSet(cam, "ExposureTime", EXP));
    errors.push_back(VmbFeatureEnumSet(cam, "GainAuto", "Off"));
    errors.push_back(VmbFeatureEnumSet(cam, "SensorBitDepth", "Bpp8"));
    errors.push_back(VmbFeatureEnumSet(cam, "PixelFormat", "Mono8"));
    errors.push_back(VmbFeatureIntSet(cam, "Width", W));
    errors.push_back(VmbFeatureIntSet(cam, "Height", H));
    errors.push_back(VmbFeatureIntSet(cam, "OffsetX", X0));
    errors.push_back(VmbFeatureIntSet(cam, "OffsetY", Y0));
    errors.push_back(VmbFeatureEnumSet(cam, "AcquisitionMode", "MultiFrame"));
    errors.push_back(VmbFeatureIntSet(cam, "AcquisitionFrameCount", N_FRAMES));
    errors.push_back(VmbFeatureEnumSet(cam, "ConvolutionMode", "CustomConvolution"));

    for (int i = 0; i < KERNEL.size(); i++) 
      for (int j = 0; j < KERNEL.size(); j++) {
        errors.push_back(VmbFeatureEnumSet(cam, "CustomConvolutionValueSelector", fmt::format("Coefficient{}{}", i, j).c_str()));
        errors.push_back(VmbFeatureIntSet(cam, "CustomConvolutionValue", KERNEL[i][j]));
    }
  }

  errors.push_back(VmbFeatureBoolSet(camL, "AcquisitionFrameRateEnable", true));
  errors.push_back(VmbFeatureFloatSet(camL, "AcquisitionFrameRate", FPS));
  errors.push_back(VmbFeatureEnumSet(camL, "LineSelector", "Line0"));
  errors.push_back(VmbFeatureEnumSet(camL, "LineMode", "Output"));
  errors.push_back(VmbFeatureEnumSet(camL, "LineSource", "ExposureActive"));
  errors.push_back(VmbFeatureEnumSet(camR, "LineSelector", "Line0"));
  errors.push_back(VmbFeatureEnumSet(camR, "LineMode", "Input"));
  errors.push_back(VmbFeatureEnumSet(camR, "TriggerSelector", "FrameStart"));
  errors.push_back(VmbFeatureEnumSet(camR, "TriggerActivation", "RisingEdge"));
  errors.push_back(VmbFeatureEnumSet(camR, "TriggerSource", "Line0"));
  errors.push_back(VmbFeatureEnumSet(camR, "TriggerMode", "On"));

  if (ranges::any_of(errors, [](int e){return e != VmbErrorSuccess;}))
    throw runtime_error("Setting camera features failed!!!");

  array<array<VmbFrame_t, 2>, N_BUFFERS> frames;
  VmbUint32_t payloadSize;
  array<VmbFrameCallback, 2> callbacks{leftFrameCallback, rightFrameCallback};

  errors.push_back(VmbPayloadSizeGet(camL, &payloadSize));

  for (int iCamera: {0, 1}) 
    for (int iFrame = 0; iFrame < N_BUFFERS; iFrame++) {
      frames[iFrame][iCamera] = VmbFrame_t{.buffer=NULL, .bufferSize=payloadSize};
      errors.push_back(VmbFrameAnnounce(cameras[iCamera], &frames[iFrame][iCamera], sizeof(VmbFrame_t)));
    }

  auto t0 = high_resolution_clock::now();

  for (int iCamera: {0, 1}) {
    errors.push_back(VmbCaptureStart(cameras[iCamera]));

    for (int iFrame = 0; iFrame < N_BUFFERS; iFrame++) 
      errors.push_back(VmbCaptureFrameQueue(cameras[iCamera], &frames[iFrame][iCamera], callbacks[iCamera]));
  }

  auto t1 = high_resolution_clock::now();

  if (ranges::any_of(errors, [](int e){return e != VmbErrorSuccess;}))
    throw runtime_error("Setting frame buffers failed!!!");

  array<bool, N_BATCHES> isBadBatch;
  array<int, 2> nLostFrames = {0, 0}, nBadFrames = {0, 0};

  ranges::fill(isBadBatch, false);

  for (int iBatch = 0; iBatch < N_BATCHES; iBatch++) {
    for (int iCamera: {1, 0})  // start the slave camera first
      errors.push_back(VmbFeatureCommandRun(cameras[iCamera], "AcquisitionStart"));  

    while (frameID[0].size() < N_FRAMES  ||  frameID[1].size() < N_FRAMES)
      this_thread::sleep_for(100ms);

    for (int iCamera: {0, 1}) {
      errors.push_back(VmbFeatureCommandRun(cameras[iCamera], "AcquisitionStop"));
      // errors.push_back(VmbCaptureEnd(cameras[iCamera]));
    }

    int iStart = min(frameID[0][0], frameID[1][0]);

    print("{}\n", iStart);

    if (iStart == -1)
      isBadBatch[iBatch] = true;
    else     
      for (int iCamera: {0, 1}) {
        ranges::transform(frameID[iCamera], frameID[iCamera].begin(), [iStart](auto e){return e-iStart;});
        ranges::sort(frameID[iCamera]);
        int badFrames = ranges::count_if(frameID[iCamera], [](auto e){return e < 0;});
        int lostFrames = ranges::count_if(frameID[iCamera], [](auto e){return e >= N_FRAMES;});

        frameID[iCamera].clear();

        if (badFrames+lostFrames > 0) {
          isBadBatch[iBatch] = true;
          nBadFrames[iCamera] += badFrames;
          nLostFrames[iCamera] += lostFrames;
        }
      }
  }

  if (ranges::any_of(errors, [](int e){return e != VmbErrorSuccess;}))
    throw runtime_error("Capture failed!!!");

  for (int iCamera: {0, 1}) {
    errors.push_back(VmbCaptureEnd(cameras[iCamera]));
    errors.push_back(VmbCaptureQueueFlush(cameras[iCamera]));
    errors.push_back(VmbFrameRevokeAll(cameras[iCamera]));
    errors.push_back(VmbCameraClose(cameras[iCamera]));
  }

  if (ranges::any_of(errors, [](int e){return e != VmbErrorSuccess;}))
    throw runtime_error("Closing failed!!!");

  VmbShutdown();
  print("Bad batches: {}  Lost frames: {}/{}  Bad frames: {}/{}\n", ranges::count(isBadBatch, true), nBadFrames[0], nBadFrames[1],
    nLostFrames[0], nLostFrames[1]);
}
