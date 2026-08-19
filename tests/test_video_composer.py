import math
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.quote_video import config
from src.quote_video.video_composer import (
    PipelineTimeoutError,
    _remaining_seconds,
    _run,
    build_concat_command,
    build_ffmpeg_command,
    compose_video,
    compute_bgm_gain_db,
)


class TestBuildFfmpegCommand(unittest.TestCase):
    def setUp(self):
        self.video = Path("video.mp4")
        self.subtitle = Path("out.ass")
        self.bgm = Path("bgm.mp3")
        self.output = Path("final.mp4")

    def test_maps_video_and_bgm_inputs_in_order(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        self.assertEqual(cmd[0], "ffmpeg")
        i0 = cmd.index(str(self.video))
        i1 = cmd.index(str(self.bgm))
        self.assertLess(i0, i1)

    def test_explicit_bgm_gain_db_is_used_verbatim(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, bgm_gain_db=-7.5
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("volume=-7.5dB", filter_complex)

    def test_bgm_gain_falls_back_to_flat_ratio_of_bgm_volume(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, bgm_volume=0.20
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        expected_db = 20 * math.log10(0.20)
        self.assertIn(f"volume={expected_db}dB", filter_complex)

    def test_amix_normalize_disabled_and_limiter_applied(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("normalize=0", filter_complex)
        self.assertIn("alimiter", filter_complex)

    def test_original_audio_volume_is_applied(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, orig_volume=0.7
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        a_orig_segment = filter_complex.split(";")[0]
        self.assertEqual(a_orig_segment, "[0:a]volume=0.7[a_orig]")

    def test_default_original_volume_matches_config(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn(f"volume={config.ORIGINAL_VOLUME}[a_orig]", filter_complex)

    def test_subtitle_margin_v_applied(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, margin_v=220
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("MarginV=220", filter_complex)

    def test_default_margin_v_matches_config(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn(f"MarginV={config.SUBTITLE_MARGIN_V}", filter_complex)

    def test_fade_out_starts_duration_minus_fade(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, fade_duration=0.5
        )
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("fade=t=in:st=0:d=0.5", filter_complex)
        self.assertIn("fade=t=out:st=15.5:d=0.5", filter_complex)

    def test_output_resolution_and_fps(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        self.assertIn(f"{config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}", cmd)
        self.assertIn(str(config.FPS), cmd)

    def test_output_path_is_last_argument(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        self.assertEqual(cmd[-1], str(self.output))

    def test_preset_applied_and_defaults_to_config(self):
        cmd = build_ffmpeg_command(self.video, self.subtitle, self.bgm, self.output, duration=16.0)
        self.assertIn("-preset", cmd)
        self.assertEqual(cmd[cmd.index("-preset") + 1], config.FFMPEG_PRESET)

    def test_preset_override(self):
        cmd = build_ffmpeg_command(
            self.video, self.subtitle, self.bgm, self.output, duration=16.0, preset="ultrafast"
        )
        self.assertEqual(cmd[cmd.index("-preset") + 1], "ultrafast")


class TestBuildConcatCommand(unittest.TestCase):
    def setUp(self):
        self.clips = [Path("1.mp4"), Path("2.mp4"), Path("3.mp4")]
        self.output = Path("assembled.mp4")

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            build_concat_command(self.clips, [2.0, 2.0], self.output)

    def test_rejects_empty_clip_list(self):
        with self.assertRaises(ValueError):
            build_concat_command([], [], self.output)

    def test_longer_clip_is_trimmed_not_padded(self):
        cmd = build_concat_command(self.clips, [3.0, 2.0, 2.0], self.output, cut_duration=2.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("trim=start=0:duration=2.0", filter_complex)
        self.assertNotIn("tpad", filter_complex.split(";")[0])

    def test_shorter_clip_is_padded_with_tpad(self):
        cmd = build_concat_command(self.clips, [1.2, 2.0, 2.0], self.output, cut_duration=2.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("tpad=stop_mode=clone:stop_duration=0.8", filter_complex)

    def test_concat_filter_references_every_clip(self):
        cmd = build_concat_command(self.clips, [2.0, 2.0, 2.0], self.output, cut_duration=2.0)
        filter_complex = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("concat=n=3:v=1:a=1[vout][aout]", filter_complex)
        for clip in self.clips:
            self.assertIn(str(clip), cmd)

    def test_preset_applied_and_defaults_to_config(self):
        cmd = build_concat_command(self.clips, [2.0, 2.0, 2.0], self.output, cut_duration=2.0)
        self.assertEqual(cmd[cmd.index("-preset") + 1], config.FFMPEG_PRESET)


class TestComposeVideoMutedOriginal(unittest.TestCase):
    """orig_volume=0 (on-site audio fully muted) used to crash compose_video()
    with `math domain error` from `math.log10(0)` in the BGM-relative-to-
    original calibration. There's nothing left to be relative to once the
    original is silent, so that calibration should be skipped entirely."""

    def setUp(self):
        patcher_probe_dur = patch("src.quote_video.video_composer.probe_duration", return_value=16.0)
        patcher_probe_vol = patch("src.quote_video.video_composer.probe_mean_volume_db", return_value=-20.0)
        patcher_run = patch("src.quote_video.video_composer._run")
        self.mock_probe_dur = patcher_probe_dur.start()
        self.mock_probe_vol = patcher_probe_vol.start()
        self.mock_run = patcher_run.start()
        self.addCleanup(patcher_probe_dur.stop)
        self.addCleanup(patcher_probe_vol.stop)
        self.addCleanup(patcher_run.stop)

    def test_does_not_raise_and_skips_relative_bgm_probing(self):
        compose_video(
            video_path=Path("video.mp4"),
            subtitle_path=Path("out.ass"),
            bgm_path=Path("bgm.mp3"),
            output_path=Path("final.mp4"),
            orig_volume=0,
            bgm_volume=0.70,
        )
        # with orig_volume<=0 there's no "relative to original" reference,
        # so probe_mean_volume_db shouldn't even be called
        self.mock_probe_vol.assert_not_called()

    def test_falls_back_to_flat_bgm_ratio_in_the_filter(self):
        compose_video(
            video_path=Path("video.mp4"),
            subtitle_path=Path("out.ass"),
            bgm_path=Path("bgm.mp3"),
            output_path=Path("final.mp4"),
            orig_volume=0,
            bgm_volume=0.70,
        )
        command = self.mock_run.call_args.args[0]
        filter_complex = command[command.index("-filter_complex") + 1]
        expected_db = 20 * math.log10(0.70)
        self.assertIn(f"volume={expected_db}dB", filter_complex)
        self.assertIn("[0:a]volume=0[a_orig]", filter_complex)

    def test_positive_orig_volume_still_uses_relative_calibration(self):
        compose_video(
            video_path=Path("video.mp4"),
            subtitle_path=Path("out.ass"),
            bgm_path=Path("bgm.mp3"),
            output_path=Path("final.mp4"),
            orig_volume=0.7,
            bgm_volume=0.20,
        )
        self.mock_probe_vol.assert_called()


class TestRemainingSeconds(unittest.TestCase):
    def test_none_deadline_means_no_limit(self):
        self.assertIsNone(_remaining_seconds(None))

    def test_future_deadline_returns_positive_remaining(self):
        remaining = _remaining_seconds(time.monotonic() + 10)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 10)

    def test_past_deadline_raises_immediately(self):
        with self.assertRaises(PipelineTimeoutError):
            _remaining_seconds(time.monotonic() - 1)


class TestRun(unittest.TestCase):
    def test_timeout_expired_becomes_pipeline_timeout_error(self):
        with patch(
            "src.quote_video.video_composer.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5),
        ):
            with self.assertRaises(PipelineTimeoutError):
                _run(["ffmpeg", "-y", "-i", "in.mp4", "out.mp4"], deadline=time.monotonic() + 5)

    def test_no_deadline_passes_none_as_subprocess_timeout(self):
        with patch("src.quote_video.video_composer.subprocess.run") as mock_run:
            _run(["ffmpeg", "-version"], deadline=None)
            self.assertIsNone(mock_run.call_args.kwargs["timeout"])


class TestComputeBgmGainDb(unittest.TestCase):
    def test_matches_original_level_when_ratio_is_1(self):
        gain = compute_bgm_gain_db(orig_mean_db=-20.3, bgm_mean_db=-20.3, bgm_volume=1.0)
        self.assertAlmostEqual(gain, 0.0)

    def test_targets_20_percent_relative_to_louder_original(self):
        # original is loud (-20.3dB), bgm's raw level happens to match it;
        # a 0.2 ratio should land bgm ~13.98dB below the original's level,
        # i.e. a negative gain cutting the raw bgm level down further.
        gain = compute_bgm_gain_db(orig_mean_db=-20.3, bgm_mean_db=-20.3, bgm_volume=0.20)
        self.assertAlmostEqual(gain, 20 * math.log10(0.20), places=4)

    def test_boosts_a_quiet_bgm_file_up_to_the_target(self):
        # bgm file is much quieter than the original on its own; reaching a
        # 20%-relative target requires a positive (boosting) gain.
        gain = compute_bgm_gain_db(orig_mean_db=-10.0, bgm_mean_db=-40.0, bgm_volume=0.20)
        self.assertGreater(gain, 0.0)


if __name__ == "__main__":
    unittest.main()
