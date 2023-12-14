#include "iostream"
#include "VmbCPP/VmbCPP.h"

using namespace VmbCPP;
using namespace std;

class FrameObserver : public IFrameObserver {
public:
  FrameObserver(CameraPtr camera) : IFrameObserver(camera) {};

  void FrameReceived(const FramePtr frame)
  {
    VmbUint64_t id;

    frame->GetFrameID(id);
    cout << id << "\n";
    m_pCamera->QueueFrame(frame);
  };
};


int main() {
  constexpr int H = 240, W = 816;
  constexpr int X0 = 0, Y0 = 192;
  constexpr double EXP = 500;
  constexpr auto OK = VmbErrorSuccess;

  auto& vmb = VmbSystem::GetInstance();  
  CameraPtr camL, camR;
  FeaturePtr fp;
  int nFrames = 100;
  int nBuffers = 64;

  try {
    if (vmb.Startup() != OK)
      throw runtime_error("vmb.Startup() failed!!!");
    
    if (vmb.OpenCameraByID("DEV_1AB22C039748", VmbAccessModeFull, camL) != OK)
      throw runtime_error("Can't open the left camera!!!");

    if (vmb.OpenCameraByID("DEV_1AB22C038A31", VmbAccessModeFull, camR) != OK)
      throw runtime_error("Can't open the right camera!!!");

    for (auto cam: {camL, camR}) 
      if (cam->GetFeatureByName("DeviceLinkThroughputLimit", fp) != OK  ||  fp->SetValue(450'000'000) != OK  ||
          // cam->GetFeatureByName("AcquisitionFrameRateEnable", fp) != OK ||  fp->SetValue("On") != OK  ||
          // cam->GetFeatureByName("AcquisitionFrameRate", fp) != OK       ||  fp->SetValue(10) != OK  ||
          cam->GetFeatureByName("ExposureAuto", fp) != OK               ||  fp->SetValue("Off") != OK  ||
          cam->GetFeatureByName("ExposureTime", fp) != OK               ||  fp->SetValue(EXP) != OK  ||
          cam->GetFeatureByName("GainAuto", fp) != OK                   ||  fp->SetValue("Off") != OK  ||
          cam->GetFeatureByName("SensorBitDepth", fp) != OK             ||  fp->SetValue("Bpp8") != OK  ||
          cam->GetFeatureByName("PixelFormat", fp) != OK                ||  fp->SetValue("Mono8") != OK  ||
          cam->GetFeatureByName("Width", fp) != OK                      ||  fp->SetValue(W) != OK  ||
          cam->GetFeatureByName("Height", fp) != OK                     ||  fp->SetValue(H) != OK  ||
          cam->GetFeatureByName("OffsetX", fp) != OK                    ||  fp->SetValue(X0) != OK  ||
          cam->GetFeatureByName("OffsetY", fp) != OK                    ||  fp->SetValue(Y0) != OK)
        throw runtime_error("Set identical values for both cameras failed!!!");

    if (camL->StartContinuousImageAcquisition(nBuffers, IFrameObserverPtr(new FrameObserver(camL))) != OK)
      throw runtime_error("StartContinuousImageAcquisition failed!!!");
  }
  catch (exception& e)
  {
    cout << e.what() << "\n";
    return 1;
  }

  vmb.Shutdown();
  cout << "\nDone.\n";
}
