import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.quote_video import config
from src.quote_video.pipeline import run_pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_caption.md"


class TestRunPipelineDeadline(unittest.TestCase):
    """run_pipeline() shouldn't touch ffmpeg/ffprobe in these tests — every
    boundary call is mocked so we can check *what* gets passed to
    video_composer without needing real media files or ffmpeg installed."""

    def setUp(self):
        patcher_assemble = patch("src.quote_video.pipeline.assemble_cuts_video")
        patcher_compose = patch("src.quote_video.pipeline.compose_video")
        patcher_ass = patch("src.quote_video.pipeline.generate_ass")
        self.mock_assemble = patcher_assemble.start()
        self.mock_compose = patcher_compose.start()
        self.mock_ass = patcher_ass.start()
        self.addCleanup(patcher_assemble.stop)
        self.addCleanup(patcher_compose.stop)
        self.addCleanup(patcher_ass.stop)

        self.mock_assemble.return_value = Path("output/_build/assembled_source.mp4")
        self.mock_compose.return_value = Path("output/final.mp4")

    def test_default_timeout_produces_a_near_future_deadline(self):
        run_pipeline(
            video_path=Path("assets/videos"),
            caption_script_path=FIXTURE,
            bgm_path=Path("bgm.mp3"),
            output_path=Path("output/final.mp4"),
        )
        assemble_deadline = self.mock_assemble.call_args.kwargs["deadline"]
        compose_deadline = self.mock_compose.call_args.kwargs["deadline"]

        now = time.monotonic()
        self.assertLessEqual(assemble_deadline, now + config.PIPELINE_TIMEOUT_SECONDS)
        self.assertGreater(assemble_deadline, now)
        # both stages share one deadline, not a fresh budget each
        self.assertEqual(assemble_deadline, compose_deadline)

    def test_timeout_seconds_none_disables_the_deadline(self):
        run_pipeline(
            video_path=Path("assets/videos"),
            caption_script_path=FIXTURE,
            bgm_path=Path("bgm.mp3"),
            output_path=Path("output/final.mp4"),
            timeout_seconds=None,
        )
        self.assertIsNone(self.mock_assemble.call_args.kwargs["deadline"])
        self.assertIsNone(self.mock_compose.call_args.kwargs["deadline"])

    def test_single_video_file_skips_assemble_but_still_gets_a_deadline(self):
        run_pipeline(
            video_path=Path("already_edited.mp4"),
            caption_script_path=FIXTURE,
            bgm_path=Path("bgm.mp3"),
            output_path=Path("output/final.mp4"),
        )
        self.mock_assemble.assert_not_called()
        self.assertIsNotNone(self.mock_compose.call_args.kwargs["deadline"])


if __name__ == "__main__":
    unittest.main()
