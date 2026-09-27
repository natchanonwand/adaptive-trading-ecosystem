"""Windows process-tree ownership: assign a suspended child to a kill-on-close job."""

import ctypes
import math
import os
import subprocess
import time
from ctypes import wintypes as w
from dataclasses import dataclass
from pathlib import Path
from threading import Event


@dataclass(frozen=True)
class Outcome:
    code: int | None
    timed_out: bool = False
    cancelled: bool = False


class Startup(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("reserved", w.LPWSTR),
        ("desktop", w.LPWSTR),
        ("title", w.LPWSTR),
        ("x", w.DWORD),
        ("y", w.DWORD),
        ("cx", w.DWORD),
        ("cy", w.DWORD),
        ("charsx", w.DWORD),
        ("charsy", w.DWORD),
        ("fill", w.DWORD),
        ("flags", w.DWORD),
        ("show", w.WORD),
        ("reservedsize", w.WORD),
        ("reservedbytes", ctypes.c_void_p),
        ("stdin", w.HANDLE),
        ("stdout", w.HANDLE),
        ("stderr", w.HANDLE),
    ]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class Limits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", w.DWORD),
        ("minimum", ctypes.c_size_t),
        ("maximum", ctypes.c_size_t),
        ("active", w.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class Extended(ctypes.Structure):
    _fields_ = [
        ("basic", Limits),
        ("io", ctypes.c_uint64 * 6),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process", ctypes.c_size_t),
        ("peak_job", ctypes.c_size_t),
    ]


def execute(
    executable: Path, arguments: list[str], cwd: Path, timeout: float, cancel: Event
) -> Outcome:
    if os.name != "nt" or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("WINDOWS_AND_FINITE_TIMEOUT_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.ResumeThread.argtypes = [w.HANDLE]
    kernel.ResumeThread.restype = w.DWORD
    kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.CreateProcessW.argtypes = [
        w.LPCWSTR,
        w.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        w.BOOL,
        w.DWORD,
        ctypes.c_void_p,
        w.LPCWSTR,
        ctypes.POINTER(Startup),
        ctypes.POINTER(ProcessInfo),
    ]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError("JOB_CREATION_FAILED")
    info = ProcessInfo()
    try:
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise OSError("JOB_LIMIT_FAILED")
        startup = Startup()
        startup.cb = ctypes.sizeof(startup)
        startup.flags = 1  # STARTF_USESHOWWINDOW
        startup.show = 0
        command = ctypes.create_unicode_buffer(
            subprocess.list2cmdline([str(executable), *arguments])
        )
        # Do not pass application/database secrets to an opaque external process.
        child_env = {
            key: os.environ[key]
            for key in ("SystemRoot", "WINDIR", "TEMP", "TMP", "SystemDrive")
            if key in os.environ
        }
        child_env["PATH"] = str(executable.parent)
        environment = ctypes.create_unicode_buffer(
            "\0".join(f"{k}={v}" for k, v in sorted(child_env.items())) + "\0\0"
        )
        # No shell, inherited handles, account credentials or visible helper window.
        if not kernel.CreateProcessW(
            str(executable),
            command,
            None,
            None,
            False,
            0x4 | 0x08000000 | 0x400,
            environment,
            str(cwd),
            ctypes.byref(startup),
            ctypes.byref(info),
        ):
            raise OSError("TESTER_PROCESS_CREATION_FAILED")
        if not kernel.AssignProcessToJobObject(job, info.process):
            kernel.TerminateProcess(info.process, 1)
            raise OSError("TESTER_JOB_ASSIGNMENT_FAILED")
        if kernel.ResumeThread(info.thread) == 0xFFFFFFFF:
            raise OSError("TESTER_RESUME_FAILED")
        deadline = time.monotonic() + timeout
        while True:
            if cancel.is_set():
                return Outcome(None, cancelled=True)
            if time.monotonic() >= deadline:
                return Outcome(None, timed_out=True)
            waited = kernel.WaitForSingleObject(info.process, 100)
            if waited == 0:
                code = w.DWORD()
                if not kernel.GetExitCodeProcess(info.process, ctypes.byref(code)):
                    raise OSError("TESTER_EXIT_STATUS_FAILED")
                return Outcome(code.value)
            if waited != 258:
                raise OSError("TESTER_WAIT_FAILED")
    finally:
        # Closing the owned job terminates all descendants, also after timeout/cancel/root exit.
        kernel.CloseHandle(job)
        if info.thread:
            kernel.CloseHandle(info.thread)
        if info.process:
            kernel.CloseHandle(info.process)
