"""Real POSIX readFile checks with explicit I/O boundary injection.

Fixtures live in an owned temporary directory, never in a user's workspace.
"""

from __future__ import annotations

import codecs
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
import uuid

from qzx.commands.file import _read_file_page as page_io
from qzx.commands.file.read_file import ReadFileCommand


def _command_with_page_boundaries(*, validator=None, opener=None):
    def page_reader(file_path, options, format_bytes):
        kwargs = {}
        if validator is not None:
            kwargs["validator"] = validator
        if opener is not None:
            kwargs["opener"] = opener
        return page_io.read_file_page(
            file_path, options, format_bytes, **kwargs
        )

    return ReadFileCommand(page_reader=page_reader)


if os.name == "posix":
    class ReadFilePosixTests(unittest.TestCase):
        def setUp(self):
            self.root = (
                Path(tempfile.gettempdir())
                / f"qzx-readfile-posix-{uuid.uuid4().hex}"
            )
            self.root.mkdir(mode=0o777)
            self.addCleanup(shutil.rmtree, self.root, True)
            self.command = ReadFileCommand()

        def file(self, name="source.txt", data=b"first\nsecond\n"):
            path = self.root / name
            path.write_bytes(data)
            return path

        def assert_failure(self, result, code):
            self.assertIs(result["success"], False, result)
            self.assertEqual(result["error_code"], code, result)
            self.assertNotIn("content", result)

        def test_fifo_is_rejected_without_opening_or_waiting(self):
            fifo = self.root / "named-pipe"
            os.mkfifo(fifo)

            def forbidden_open(_target):
                raise AssertionError("FIFO opened")

            command = _command_with_page_boundaries(opener=forbidden_open)
            result = command.execute(fifo)
            self.assert_failure(result, "not_a_regular_file")
            self.assertEqual(result["details"]["entry_type"], "fifo")

        def test_unix_socket_is_rejected(self):
            # AF_UNIX has a small sockaddr path limit on macOS. GitHub-hosted
            # macOS runners expose a long TMPDIR, so keep this fixture under
            # the conventional short POSIX /tmp path instead of self.root.
            socket_root = (
                Path("/tmp") / f"qzx-rf-{uuid.uuid4().hex[:12]}"
            )
            socket_root.mkdir(mode=0o777)
            self.addCleanup(shutil.rmtree, socket_root, True)
            path = socket_root / "s"
            with socket.socket(
                socket.AF_UNIX, socket.SOCK_STREAM
            ) as endpoint:
                endpoint.bind(str(path))
                result = self.command.execute(path)
            self.assert_failure(result, "not_a_regular_file")
            self.assertEqual(result["details"]["entry_type"], "socket")

        def test_symlink_to_regular_file_is_read_and_disclosed(self):
            target = self.file()
            link = self.root / "alias.txt"
            link.symlink_to(target)
            result = self.command.execute(link, max_lines=1)
            self.assertIs(result["success"], True, result)
            self.assertTrue(result["details"]["followed_symlink"])
            following = self.command.execute(**result["details"]["next_read"])
            self.assertEqual(
                result["content"] + following["content"],
                "first\nsecond\n",
            )
            self.assertTrue(following["details"]["read_complete"])

        def test_parent_directory_symlink_remains_usable(self):
            directory = self.root / "real-directory"
            directory.mkdir()
            (directory / "text.txt").write_text(
                "Diseño\n", encoding="utf-8"
            )
            alias = self.root / "directory-alias"
            alias.symlink_to(directory, target_is_directory=True)
            result = self.command.execute(alias / "text.txt")
            self.assertEqual(result["content"], "Diseño\n", result)
            self.assertTrue(result["details"]["followed_symlink"])

        def test_symlink_retargeting_invalidates_continuation(self):
            first = self.file("first.txt")
            second = self.file("second.txt")
            link = self.root / "alias.txt"
            link.symlink_to(first)
            page = self.command.execute(link, max_lines=1)
            link.unlink()
            link.symlink_to(second)
            result = self.command.execute(**page["details"]["next_read"])
            self.assert_failure(
                result, "file_changed_since_previous_read"
            )

        def test_atomic_replacement_invalidates_same_size_and_mtime(self):
            path = self.file()
            original_stat = path.stat()
            page = self.command.execute(path, max_lines=1)
            replacement = self.file("replacement.txt")
            os.utime(
                replacement,
                ns=(
                    original_stat.st_atime_ns,
                    original_stat.st_mtime_ns,
                ),
            )
            os.replace(replacement, path)
            self.assertNotEqual(path.stat().st_ino, original_stat.st_ino)
            result = self.command.execute(**page["details"]["next_read"])
            self.assert_failure(
                result, "file_changed_since_previous_read"
            )

        def test_fifo_substitution_after_validation_cannot_block_the_reader(self):
            path = self.file()
            original = page_io.validate_regular_file

            def substitute(requested, **options):
                target, error = original(requested, **options)
                path.unlink()
                os.mkfifo(path)
                return target, error

            command = _command_with_page_boundaries(validator=substitute)
            result = command.execute(path)
            self.assert_failure(result, "file_changed_during_read")

        if getattr(os, "O_NOFOLLOW", 0):
            def test_symlink_substitution_after_validation_is_not_followed(self):
                path = self.file()
                other = self.file(
                    "other.txt", b"must-not-be-returned"
                )
                original = page_io.validate_regular_file

                def substitute(requested, **options):
                    target, error = original(requested, **options)
                    path.unlink()
                    path.symlink_to(other)
                    return target, error

                command = _command_with_page_boundaries(
                    validator=substitute
                )
                result = command.execute(path)
                self.assert_failure(result, "read_failed")

        def test_unicode_round_trips_across_page_and_line_budgets(self):
            text = (
                "Alejandro Sánchez\r\n日本語 😀\rDiseño\n\n"
                "Sin pérdida.\r\n"
            )
            encodings = [
                ("utf-8", b""),
                ("utf-8", codecs.BOM_UTF8),
                ("utf-16-le", codecs.BOM_UTF16_LE),
                ("utf-16-be", codecs.BOM_UTF16_BE),
                ("utf-32-le", codecs.BOM_UTF32_LE),
                ("utf-32-be", codecs.BOM_UTF32_BE),
            ]
            for codec, bom in encodings:
                path = self.file(data=bom + text.encode(codec))
                for budget in range(8, 33):
                    for line_limit in (None, 1, 3):
                        with self.subTest(
                            codec=codec,
                            bom=bool(bom),
                            budget=budget,
                            lines=line_limit,
                        ):
                            self.assert_round_trip(
                                path, text, budget, line_limit
                            )

        def assert_round_trip(
            self, path, text, budget, line_limit
        ):
            options = {
                "file_path": str(path),
                "max_bytes": budget,
                "max_lines": line_limit,
            }
            chunks = []
            for _ in range(100):
                result = self.command.execute(**options)
                self.assertIs(result["success"], True, result)
                chunks.append(result["content"])
                self.assertLessEqual(
                    result["details"]["source_bytes_read"],
                    budget + 4,
                )
                options = result["details"]["next_read"]
                if options is None:
                    self.assertTrue(
                        result["details"]["read_complete"]
                    )
                    self.assertEqual("".join(chunks), text)
                    return
            self.fail(
                "Traversal did not reach EOF within the fixture's "
                "known maximum pages"
            )
else:
    class ReadFilePosixScopeTests(unittest.TestCase):
        def test_posix_fixture_suite_is_platform_scoped(self):
            self.assertNotEqual(os.name, "posix")


if __name__ == "__main__":
    unittest.main(verbosity=2)
