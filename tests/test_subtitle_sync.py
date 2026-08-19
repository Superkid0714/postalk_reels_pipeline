import unittest
from pathlib import Path

from src.quote_video import config
from src.quote_video.subtitle_sync import (
    build_srt,
    compute_timings,
    parse_caption_script,
    total_video_duration,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_caption.md"


class TestParseCaptionScript(unittest.TestCase):
    def test_parses_all_16_cuts_in_order(self):
        lines = parse_caption_script(FIXTURE)
        self.assertEqual(len(lines), 16)
        self.assertEqual([line.cut_number for line in lines], list(range(1, 17)))
        self.assertEqual(lines[0].text, "포항중앙수산시장에 오시면")
        self.assertEqual(lines[-1].text, "지금 바로 입안 가득 바다를 즐겨보세요!")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            parse_caption_script(Path("does/not/exist.md"))


class TestComputeTimings(unittest.TestCase):
    def test_each_line_gets_a_one_second_window(self):
        lines = parse_caption_script(FIXTURE)
        timings = compute_timings(lines, caption_duration=1.0)

        self.assertEqual(timings[0].start, 0.0)
        self.assertEqual(timings[0].end, 1.0)
        self.assertEqual(timings[1].start, 1.0)
        self.assertEqual(timings[1].end, 2.0)
        self.assertEqual(timings[-1].start, 15.0)
        self.assertEqual(timings[-1].end, 16.0)

    def test_two_lines_per_cut_share_the_same_two_second_cut_window(self):
        lines = parse_caption_script(FIXTURE)
        timings = compute_timings(lines, caption_duration=config.CAPTION_DURATION)

        # cut 1 (video [0s, 2s)) should hold caption lines 1 and 2.
        first_cut_lines = [t for t in timings if t.start < config.CUT_DURATION]
        self.assertEqual(len(first_cut_lines), config.CAPTIONS_PER_CUT)


class TestTotalVideoDuration(unittest.TestCase):
    def test_16_lines_implies_16_second_video(self):
        lines = parse_caption_script(FIXTURE)
        self.assertEqual(total_video_duration(lines), 16.0)

    def test_odd_number_of_lines_raises(self):
        lines = parse_caption_script(FIXTURE)[:-1]  # drop to 15, odd
        with self.assertRaises(ValueError):
            total_video_duration(lines)


class TestBuildSrt(unittest.TestCase):
    def test_srt_format_and_timestamps(self):
        lines = parse_caption_script(FIXTURE)
        timings = compute_timings(lines)
        srt = build_srt(timings)

        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:01,000\n"))
        self.assertIn("2\n00:00:01,000 --> 00:00:02,000\n", srt)
        self.assertIn("16\n00:00:15,000 --> 00:00:16,000\n", srt)
        self.assertEqual(srt.count("-->"), 16)


if __name__ == "__main__":
    unittest.main()
