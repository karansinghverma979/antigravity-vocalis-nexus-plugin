param(
    [Parameter(Position=0)]
    [float]$Level = -1.0
)

$TypeDefinition = @"
using System;
using System.Runtime.InteropServices;

[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
    int f(); int g(); int h(); int j();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int f1();
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int SetMute(bool bMute, System.Guid pguidEventContext);
    int GetMute(out bool pbMute);
}

[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {
    int Activate(ref System.Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev);
}

[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {
    int f();
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }

public class AudioMaster {
    public static void SetVolume(float level) {
        var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
        IMMDevice dev = null;
        enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = typeof(IAudioEndpointVolume).GUID;
        IAudioEndpointVolume vol = null;
        dev.Activate(ref iid, 23, 0, out vol);
        vol.SetMute(false, System.Guid.Empty);
        vol.SetMasterVolumeLevelScalar(level, System.Guid.Empty);
    }
    public static float GetVolume() {
        var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
        IMMDevice dev = null;
        enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = typeof(IAudioEndpointVolume).GUID;
        IAudioEndpointVolume vol = null;
        dev.Activate(ref iid, 23, 0, out vol);
        float level = 0f;
        vol.GetMasterVolumeLevelScalar(out level);
        return level;
    }
}
"@

if (-not ([System.Management.Automation.PSTypeName]'AudioMaster').Type) {
    Add-Type -TypeDefinition $TypeDefinition
}

if ($Level -ge 0.0) {
    [AudioMaster]::SetVolume($Level)
}

[AudioMaster]::GetVolume()
