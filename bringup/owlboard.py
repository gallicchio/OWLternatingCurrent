"""The board's console, from Python: one command a line out, one JSON object a line back
(the bring-up image and the main firmware speak the same way; firmware/README.md).

    from owlboard import OwlBoard
    with OwlBoard() as b:                       # finds the USB port (VID 0x1209)
        print(b.cmd("rails"))                   # {'ok': True, 'v12': 12.01, ...}
        print(b.events)                         # unasked lines: boot, ledwalk, sweep_pt...

    OwlBoard(port="/dev/ttyACM0")               # a given port: USB, or the Debug Probe's
                                                # UART on J5 (115200 baud)
    OwlBoard(sim=SimBoard())                    # the bring-up image's command code built
                                                # for the PC (firmware/test/bringup_sim)

`cmd()` raises BoardError when the reply says "ok": false (check=False returns it).
"""

import glob
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM_BIN = Path(os.environ.get("OWL_BRINGUP_SIM", ROOT / "firmware" / "test" / "bringup_sim"))
USB_VID = "1209"


class BoardError(RuntimeError):
    def __init__(self, line, reply):
        super().__init__(f"{line!r}: {reply.get('error', reply)}")
        self.reply = reply


def find_port():
    """The board's USB CDC port: by-id names carry the VID only indirectly, so look at
    sysfs for a tty whose USB device has idVendor 1209."""
    for tty in sorted(glob.glob("/sys/class/tty/ttyACM*")):
        dev = os.path.realpath(os.path.join(tty, "device"))
        for up in (dev, os.path.dirname(dev)):
            vid = os.path.join(up, "idVendor")
            if not os.path.exists(vid):
                vid = os.path.join(os.path.dirname(up), "idVendor")
            if os.path.exists(vid) and open(vid).read().strip() == USB_VID:
                return "/dev/" + os.path.basename(tty)
    raise IOError("no OWLternating board on USB (no ttyACM with VID 1209): is it flashed and plugged in?")


class OwlBoard:
    def __init__(self, port=None, sim=None, baud=115200, timeout=3.0, env=None):
        self.events = []
        self.log = []                       # (time, 'tx'/'rx', text)
        self.sim = sim
        self.timeout = timeout
        if sim is not None:
            if not SIM_BIN.exists():
                raise IOError(f"{SIM_BIN} not built: make -C firmware/test bringup_sim")
            e = dict(os.environ)
            e.update(env or {})
            # unbuffered bytes: lines are split here, as for the serial port (a buffered
            # reader would hide lines from select() once a burst had arrived)
            self.proc = subprocess.Popen([str(SIM_BIN)], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, bufsize=0, env=e)
            self.ser = None
        else:
            import serial
            self.proc = None
            self.port = port or find_port()
            self.ser = serial.Serial(self.port, baud, timeout=0.1)
            time.sleep(0.1)
            self.ser.reset_input_buffer()
        self._buf = b""

    # -- lines --------------------------------------------------------------------------
    def _send(self, line):
        self.log.append((time.time(), "tx", line))
        if self.proc is not None:
            self.proc.stdin.write((line + "\n").encode())
        else:
            self.ser.write((line + "\n").encode())

    def _readline(self, deadline):
        if self.proc is not None:
            import select
            fd = self.proc.stdout.fileno()
            while True:
                if b"\n" in self._buf:
                    line, self._buf = self._buf.split(b"\n", 1)
                    return line.decode(errors="replace").strip()
                left = deadline - time.time()
                if left <= 0:
                    return None
                r, _, _ = select.select([fd], [], [], left)
                if r:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        raise IOError("the simulated board exited")
                    self._buf += chunk
        while time.time() < deadline:
            if b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                return line.decode(errors="replace").strip()
            self._buf += self.ser.read(256)
        return None

    def read_json(self, deadline):
        """The next JSON line before `deadline` (non-JSON lines, such as a boot banner,
        are logged and skipped). None on timeout."""
        while True:
            s = self._readline(deadline)
            if s is None:
                return None
            if not s:
                continue
            self.log.append((time.time(), "rx", s))
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                continue

    def cmd(self, line, timeout=None, check=True, on_event=None):
        """Send one command; collect events until its reply (a JSON object with "ok")."""
        self._send(line)
        deadline = time.time() + (timeout or self.timeout)
        while True:
            m = self.read_json(deadline)
            if m is None:
                raise TimeoutError(f"no reply to {line!r} within {timeout or self.timeout} s")
            if "ok" in m and "event" not in m:
                if self.sim is not None:
                    self.sim.observe(line, m)
                if check and not m["ok"]:
                    raise BoardError(line, m)
                return m
            self.events.append(m)
            if on_event:
                on_event(m)

    def wait_event(self, name, timeout=5.0):
        """The next event called `name` (already received, or arriving within timeout)."""
        for k, e in enumerate(self.events):
            if e.get("event") == name:
                return self.events.pop(k)
        deadline = time.time() + timeout
        while True:
            m = self.read_json(deadline)
            if m is None:
                return None
            if m.get("event") == name:
                return m
            self.events.append(m)

    def close(self):
        if self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=2)
            except Exception:                       # noqa: BLE001
                self.proc.kill()
        if self.ser is not None:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
