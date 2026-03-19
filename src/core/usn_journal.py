"""
OP(AI)UM — NTFS USN Journal Reader

Reads the NTFS Update Sequence Number (USN) Journal to track
file and folder renames, moves, and deletions at the filesystem level.
This provides enterprise-grade tracking across all drives.

Requires elevated privileges or specific NTFS permissions.
Falls back gracefully if unavailable.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import struct
from datetime import datetime, timedelta
from enum import IntFlag
from typing import NamedTuple

from loguru import logger


class USNReason(IntFlag):
    """USN Journal change reasons."""

    DATA_OVERWRITE = 0x00000001
    DATA_EXTEND = 0x00000002
    DATA_TRUNCATION = 0x00000004
    NAMED_DATA_OVERWRITE = 0x00000010
    NAMED_DATA_EXTEND = 0x00000020
    NAMED_DATA_TRUNCATION = 0x00000040
    FILE_CREATE = 0x00000100
    FILE_DELETE = 0x00000200
    EA_CHANGE = 0x00000400
    SECURITY_CHANGE = 0x00000800
    RENAME_OLD_NAME = 0x00001000
    RENAME_NEW_NAME = 0x00002000
    INDEXABLE_CHANGE = 0x00004000
    BASIC_INFO_CHANGE = 0x00008000
    HARD_LINK_CHANGE = 0x00010000
    COMPRESSION_CHANGE = 0x00020000
    ENCRYPTION_CHANGE = 0x00040000
    OBJECT_ID_CHANGE = 0x00080000
    REPARSE_POINT_CHANGE = 0x00100000
    STREAM_CHANGE = 0x00200000
    CLOSE = 0x80000000


class USNRecord(NamedTuple):
    """A parsed USN Journal record."""

    file_reference_number: int
    parent_file_reference_number: int
    usn: int
    timestamp: datetime
    reason: int
    filename: str
    is_directory: bool

    @property
    def is_rename(self) -> bool:
        return bool(self.reason & (USNReason.RENAME_OLD_NAME | USNReason.RENAME_NEW_NAME))

    @property
    def is_delete(self) -> bool:
        return bool(self.reason & USNReason.FILE_DELETE)

    @property
    def is_create(self) -> bool:
        return bool(self.reason & USNReason.FILE_CREATE)

    @property
    def reason_description(self) -> str:
        reasons = []
        if self.reason & USNReason.FILE_CREATE:
            reasons.append("Created")
        if self.reason & USNReason.FILE_DELETE:
            reasons.append("Deleted")
        if self.reason & USNReason.RENAME_OLD_NAME:
            reasons.append("Renamed (old)")
        if self.reason & USNReason.RENAME_NEW_NAME:
            reasons.append("Renamed (new)")
        if self.reason & USNReason.CLOSE:
            reasons.append("Closed")
        return ", ".join(reasons) if reasons else f"0x{self.reason:08X}"


class USNJournalReader:
    """
    Reads the NTFS USN Journal for a specified drive.

    The USN Journal records every change to files and folders
    on an NTFS volume. We use this to detect:
    - Folder renames
    - Folder moves (within same volume)
    - Folder deletions

    Note: Requires appropriate permissions. Will fall back
    gracefully if unavailable.
    """

    # Windows constants
    FSCTL_QUERY_USN_JOURNAL = 0x000900F4
    FSCTL_READ_USN_JOURNAL = 0x000900BB
    FSCTL_ENUM_USN_DATA = 0x000900B3

    FILE_ATTRIBUTE_DIRECTORY = 0x00000010

    def __init__(self, drive_letter: str = "C") -> None:
        """
        Initialize USN reader for a specific drive.

        Args:
            drive_letter: Drive letter without colon (e.g., 'C').
        """
        self._drive = drive_letter.upper()
        self._volume_path = f"\\\\.\\{self._drive}:"
        self._available: bool | None = None
        self._handle: int | None = None

    @property
    def is_available(self) -> bool:
        """Check if USN Journal reading is available on this drive."""
        if self._available is None:
            self._available = self._test_availability()
        return self._available

    def get_recent_changes(
        self,
        max_age_hours: int = 48,
        directories_only: bool = False,
    ) -> list[USNRecord]:
        """
        Get recent filesystem changes from the USN Journal.

        Args:
            max_age_hours: Maximum age of records to return.
            directories_only: Only return directory changes.

        Returns:
            List of USNRecord sorted by timestamp (newest first).
        """
        if not self.is_available:
            logger.debug(f"USN Journal not available on drive {self._drive}:")
            return []

        records: list[USNRecord] = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        try:
            handle = self._open_volume()
            if handle is None:
                return []

            try:
                # Query journal info
                journal_info = self._query_journal(handle)
                if journal_info is None:
                    return []

                journal_id, first_usn, next_usn = journal_info

                # Read records
                raw_records = self._read_records(handle, journal_id, first_usn)

                for record in raw_records:
                    if record.timestamp < cutoff:
                        continue
                    if directories_only and not record.is_directory:
                        continue
                    records.append(record)

            finally:
                ctypes.windll.kernel32.CloseHandle(handle)

        except Exception as e:
            logger.error(f"Error reading USN Journal on {self._drive}: {e}")

        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records

    def get_renames(self, max_age_hours: int = 48) -> list[tuple[USNRecord, USNRecord]]:
        """
        Get pairs of (old_name, new_name) for renamed items.

        Returns:
            List of (old_record, new_record) tuples.
        """
        changes = self.get_recent_changes(max_age_hours=max_age_hours)

        old_names: dict[int, USNRecord] = {}
        rename_pairs: list[tuple[USNRecord, USNRecord]] = []

        for record in sorted(changes, key=lambda r: r.usn):
            if record.reason & USNReason.RENAME_OLD_NAME:
                old_names[record.file_reference_number] = record
            elif record.reason & USNReason.RENAME_NEW_NAME:
                old = old_names.get(record.file_reference_number)
                if old:
                    rename_pairs.append((old, record))

        return rename_pairs

    def _test_availability(self) -> bool:
        """Test if we can read the USN Journal."""
        try:
            handle = self._open_volume()
            if handle is None:
                return False
            info = self._query_journal(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
            return info is not None
        except Exception:
            return False

    def _open_volume(self) -> int | None:
        """Open a handle to the volume."""
        try:
            GENERIC_READ = 0x80000000
            FILE_SHARE_READ = 0x01
            FILE_SHARE_WRITE = 0x02
            OPEN_EXISTING = 3

            handle = ctypes.windll.kernel32.CreateFileW(
                self._volume_path,
                GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None,
            )

            if handle == -1 or handle == 0xFFFFFFFF:
                logger.debug(f"Cannot open volume {self._volume_path}")
                return None

            return handle
        except Exception as e:
            logger.debug(f"Failed to open volume: {e}")
            return None

    def _query_journal(self, handle: int) -> tuple[int, int, int] | None:
        """Query USN Journal metadata."""
        try:
            output_buffer = ctypes.create_string_buffer(64)
            bytes_returned = ctypes.wintypes.DWORD()

            result = ctypes.windll.kernel32.DeviceIoControl(
                handle,
                self.FSCTL_QUERY_USN_JOURNAL,
                None,
                0,
                output_buffer,
                64,
                ctypes.byref(bytes_returned),
                None,
            )

            if not result:
                return None

            # Parse USN_JOURNAL_DATA_V0
            journal_id = struct.unpack_from("<Q", output_buffer, 0)[0]
            first_usn = struct.unpack_from("<q", output_buffer, 8)[0]
            next_usn = struct.unpack_from("<q", output_buffer, 16)[0]

            return journal_id, first_usn, next_usn

        except Exception as e:
            logger.debug(f"Journal query failed: {e}")
            return None

    def _read_records(
        self,
        handle: int,
        journal_id: int,
        start_usn: int,
    ) -> list[USNRecord]:
        """Read USN records from the journal."""
        records: list[USNRecord] = []
        BUFFER_SIZE = 65536

        try:
            # READ_USN_JOURNAL_DATA_V0 structure
            input_buffer = struct.pack(
                "<qIIIQq",
                start_usn,  # StartUsn
                0xFFFFFFFF,  # ReasonMask (all reasons)
                0,  # ReturnOnlyOnClose
                0,  # Timeout
                journal_id,  # UsnJournalID
                0,  # MinMajorVersion (not used in V0)
            )

            output_buffer = ctypes.create_string_buffer(BUFFER_SIZE)
            bytes_returned = ctypes.wintypes.DWORD()
            max_iterations = 1000  # Safety limit

            current_usn = start_usn

            for _ in range(max_iterations):
                input_buffer = struct.pack(
                    "<qIIIQ",
                    current_usn,
                    0xFFFFFFFF,
                    0,
                    0,
                    journal_id,
                )

                result = ctypes.windll.kernel32.DeviceIoControl(
                    handle,
                    self.FSCTL_READ_USN_JOURNAL,
                    input_buffer,
                    len(input_buffer),
                    output_buffer,
                    BUFFER_SIZE,
                    ctypes.byref(bytes_returned),
                    None,
                )

                if not result or bytes_returned.value <= 8:
                    break

                # First 8 bytes: next USN
                data = output_buffer.raw[: bytes_returned.value]
                next_usn = struct.unpack_from("<q", data, 0)[0]

                # Parse records starting at offset 8
                offset = 8
                while offset < len(data) - 4:
                    try:
                        record = self._parse_record(data, offset)
                        if record is None:
                            break
                        records.append(record)
                        # Move to next record
                        record_len = struct.unpack_from("<I", data, offset)[0]
                        if record_len == 0:
                            break
                        offset += record_len
                    except Exception:
                        break

                if next_usn <= current_usn:
                    break
                current_usn = next_usn

        except Exception as e:
            logger.debug(f"Error reading USN records: {e}")

        return records

    def _parse_record(self, data: bytes, offset: int) -> USNRecord | None:
        """Parse a single USN_RECORD_V2 from buffer."""
        try:
            if offset + 60 > len(data):
                return None

            record_length = struct.unpack_from("<I", data, offset)[0]
            if record_length < 60 or offset + record_length > len(data):
                return None

            major_version = struct.unpack_from("<H", data, offset + 4)[0]
            if major_version != 2:
                return None

            file_ref = struct.unpack_from("<Q", data, offset + 8)[0]
            parent_ref = struct.unpack_from("<Q", data, offset + 16)[0]
            usn = struct.unpack_from("<q", data, offset + 24)[0]

            # Timestamp: Windows FILETIME (100ns since 1601-01-01)
            filetime = struct.unpack_from("<Q", data, offset + 32)[0]
            try:
                # Convert to Python datetime
                EPOCH_DIFF = 116444736000000000  # 100ns intervals between 1601 and 1970
                timestamp = datetime.fromtimestamp((filetime - EPOCH_DIFF) / 10000000)
            except (OSError, ValueError, OverflowError):
                timestamp = datetime.now()

            reason = struct.unpack_from("<I", data, offset + 40)[0]
            struct.unpack_from("<I", data, offset + 44)[0]
            struct.unpack_from("<I", data, offset + 48)[0]
            file_attributes = struct.unpack_from("<I", data, offset + 52)[0]
            filename_length = struct.unpack_from("<H", data, offset + 56)[0]
            filename_offset = struct.unpack_from("<H", data, offset + 58)[0]

            # Extract filename
            fn_start = offset + filename_offset
            fn_end = fn_start + filename_length
            if fn_end <= len(data):
                filename = data[fn_start:fn_end].decode("utf-16-le", errors="replace")
            else:
                filename = "<unknown>"

            is_directory = bool(file_attributes & self.FILE_ATTRIBUTE_DIRECTORY)

            # Mask out the sequence number from file reference
            file_ref_number = file_ref & 0x0000FFFFFFFFFFFF

            return USNRecord(
                file_reference_number=file_ref_number,
                parent_file_reference_number=parent_ref & 0x0000FFFFFFFFFFFF,
                usn=usn,
                timestamp=timestamp,
                reason=reason,
                filename=filename,
                is_directory=is_directory,
            )

        except Exception as e:
            logger.debug(f"Failed to parse USN record at offset {offset}: {e}")
            return None
