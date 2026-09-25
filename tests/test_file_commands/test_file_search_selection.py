"""Bounded metadata selection has the same evidence and ordering as a complete sort."""

import gc
import os
import random
import weakref

import pytest

from qzx.commands.file._file_search_scan import select_records


def _records():
    rows = [
        {
            "path": f"/fixture/folder-{number % 5}/file-{number:03d}.bin",
            "name": f"file-{number % 9:03d}.bin",
            "size_bytes": number % 7,
            "modified_timestamp": 1700000000 + number % 11,
        }
        for number in range(80)
    ]
    random.Random(20260913).shuffle(rows)
    return rows


@pytest.mark.parametrize("sort_by", ["path", "name", "size", "modified"])
@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("limit", [1, 7, 80, 120, None])
def test_bounded_selection_matches_full_reference_sort(sort_by, descending, limit):
    rows = _records()
    field = {"path": "path", "name": "name", "size": "size_bytes", "modified": "modified_timestamp"}[sort_by]

    def reference_key(item):
        primary = os.path.normcase(item[field]) if sort_by in {"path", "name"} else item[field]
        return primary, os.path.normcase(item["path"]), item["path"]

    consumed = []

    def stream():
        for index, row in enumerate(rows):
            consumed.append(index)
            yield row

    expected = sorted(rows, key=reference_key, reverse=descending)
    if limit is not None:
        expected = expected[:limit]
    actual = select_records(stream(), sort_by, descending, limit)

    assert actual == expected
    assert consumed == list(range(len(rows)))


def test_limited_selection_does_not_retain_all_examined_records():
    class ObservedRecord(dict):
        __slots__ = ("__weakref__",)

    live = weakref.WeakValueDictionary()
    observed_peaks = []

    def stream():
        for index in range(2000):
            row = ObservedRecord(path=f"/fixture/{index:04d}.bin", size_bytes=index)
            live[index] = row
            observed_peaks.append(len(live))
            yield row

    selected = select_records(stream(), "size", True, 20)
    gc.collect()

    assert len(selected) == 20
    assert max(observed_peaks) <= 22
    assert len(live) == 20
    assert [row["size_bytes"] for row in selected] == list(range(1999, 1979, -1))
