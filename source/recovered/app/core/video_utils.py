import subprocess
import re
import imageio_ffmpeg

def get_video_duration(video_path: str) -> float:
    '''
    Reads the video file and calculates its duration in seconds using FFmpeg.
    Returns 0.0 if the file cannot be read or is invalid.
    '''

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, '-i', video_path]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        _, stderr = process.communicate()
        match = re.search('Duration:\\s*(\\d{2}):(\\d{2}):(\\d{2}\\.\\d+)', stderr.decode('utf-8', errors='ignore'))
        if match:
            h, m, s = match.groups()
            return float(h) * 3600 + float(m) * 60 + float(s)
        return 0.0
    except Exception:
        return 0.0

