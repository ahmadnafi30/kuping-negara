"""Regression checks for publication lock contention."""

import os

import pytest

from kuping_negara.preprocessing.history import preprocessing_lock


@pytest.mark.skipif(os.name != "nt", reason="Windows byte-range lock regression")
def test_empty_lock_contention_times_out_without_writing(tmp_path):
    import msvcrt

    lock_path = tmp_path / ".preprocessing.lock"
    with lock_path.open("x+b") as holder:
        msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with pytest.raises(TimeoutError, match="publication lock"):
                with preprocessing_lock(tmp_path, timeout=0.05):
                    pytest.fail("A second handle acquired the held publication lock")
        finally:
            holder.seek(0)
            msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)

    with preprocessing_lock(tmp_path, timeout=0.05):
        pass
