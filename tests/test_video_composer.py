import unittest
from pathlib import Path

from src.quote_video import config
from src.quote_video.video_composer import build_ffmpeg_command


class TestBuildFfmpegCommand(unittest.TestCase):
    def setUp(self):
        self.video = Path("video.mp4")
        self.srt = Path("out.srt")
        self.bgm = Path("bgm.mp3")
        self.output = Path("final.mp4")

    def test_maps_video_and_bgm_inputs_in_order(self):
        cmd = build_ffmpeg_command(self.video, self.srt, self.bgm, self.output, duration=16.0)
        self.assertEqual(cmd[0], "ffmpeg")
        i0 = cmd.index(str(self.video))
        i1 = cmd.index(str(self.bgm))
        self.assertLess(i0, i1)

    def test_bgm_volume_applied_in_filter(self):
        cmd = build_ffmpeg_command(
            self.video, self.srt, self.bgm, self.output, duration=16.0, bgm_volume=0.20
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("volume=0.2", filter_complex)

    def test_fade_out_starts_duration_minus_fade(self):
        cmd = build_ffmpeg_command(
            self.video, self.srt, self.bgm, self.output, duration=16.0, fade_duration=0.5
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("fade=t=in:st=0:d=0.5", filter_complex)
        self.assertIn("fade=t=out:st=15.5:d=0.5", filter_complex)

    def test_output_resolution_and_fps(self):
        cmd = build_ffmpeg_command(self.video, self.srt, self.bgm, self.output, duration=16.0)
        self.assertIn(f"{config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}", cmd)
        self.assertIn(str(config.FPS), cmd)

    def test_output_path_is_last_argument(self):
        cmd = build_ffmpeg_command(self.video, self.srt, self.bgm, self.output, duration=16.0)
        self.assertEqual(cmd[-1], str(self.output))


if __name__ == "__main__":
    unittest.main()
