import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.core.media_parser import parse_media
from src.sync.sync_controller import SyncWorker


class MediaParserTests(unittest.TestCase):
    def test_parse_media_strips_quality_from_movie_title(self):
        media = parse_media("The Matrix 360p WEBRip x265", ".mp4")

        self.assertEqual(media.type, "movie")
        self.assertEqual(media.title, "The Matrix")
        self.assertEqual(media.destination_base, "The Matrix")

    def test_parse_media_keeps_movie_year_while_ignoring_quality(self):
        media = parse_media("Avatar.2009.360p.BluRay", ".mkv")

        self.assertEqual(media.type, "movie")
        self.assertEqual(media.title, "Avatar")
        self.assertEqual(media.year, 2009)
        self.assertEqual(media.destination_base, "Avatar (2009)")


class SyncWorkerTests(unittest.TestCase):
    def test_abort_during_last_item_emits_cancelled_instead_of_finished(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            destination = root / "Movies" / "Sample" / "Sample.mp4"
            item = {
                "video": {"type": "local", "source_path": str(root / "source.mp4")},
                "subtitles": [],
                "destination": destination,
                "media": SimpleNamespace(
                    type="movie",
                    title="Sample",
                    season=None,
                    episode=None,
                    year=None,
                    destination_base="Sample",
                    extension=".mp4",
                    is_precise=False,
                ),
            }
            worker = SyncWorker([item], {"destinationRoot": str(root), "stagingFolderName": ".incoming"})
            events = []

            worker.finished.connect(lambda: events.append("finished"))
            worker.cancelled.connect(lambda: events.append("cancelled"))

            def fake_copy_entry(entry, stage_dir):
                stage_dir.mkdir(parents=True, exist_ok=True)
                staged = stage_dir / "Sample.mp4"
                staged.write_bytes(b"demo")
                worker.abort()
                return staged

            worker.copy_entry = fake_copy_entry
            worker.run()

            self.assertIn("cancelled", events)
            self.assertNotIn("finished", events)


if __name__ == "__main__":
    unittest.main()
