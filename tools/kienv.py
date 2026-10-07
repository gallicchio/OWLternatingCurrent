"""Find KiCad 10: its command-line tool, a Python that can `import pcbnew`,
and its stock libraries.

Looked for in this order (the first that exists wins):

  1. $KICAD_APPRUN      the AppRun of an extracted AppImage
  2. $KICAD_APPIMAGE    a KiCad 10 AppImage
  3. ~/.local/kicad10/AppDir/AppRun, then ~/.local/kicad10/squashfs-root/AppRun
  4. ~/.local/bin/kicad-10*.AppImage, ~/Applications, ~/Downloads
  5. kicad-cli on the PATH, with the system python3 (a distribution package)

Run KiCad's bundled Python through AppRun (`AppRun python3.11 script.py`).
Calling usr/bin/python3.11 directly with LD_LIBRARY_PATH set segfaults on
`import pcbnew` (KiCad 10.0.6, measured).

The build only needs the stock libraries when (re)vendoring parts into
hardware/lib (gen/library.py --vendor); everything else reads the project's
own copies, so a fresh clone builds on any machine with KiCad 10.
"""
import glob, os, shutil, subprocess, sys


def _x(p):
    return p and os.path.isfile(p) and os.access(p, os.X_OK)


def launcher():
    """The AppRun or AppImage that dispatches to kicad-cli and python3.11,
    or None for a system install."""
    for env in ("KICAD_APPRUN", "KICAD_APPIMAGE"):
        p = os.environ.get(env)
        if p:
            p = os.path.expanduser(p)
            if not _x(p):
                raise SystemExit("%s=%s is not an executable file" % (env, p))
            return p
    for p in ("~/.local/kicad10/AppDir/AppRun", "~/.local/kicad10/squashfs-root/AppRun"):
        p = os.path.expanduser(p)
        if _x(p):
            return p
    for d in ("~/.local/bin", "~/Applications", "~/Downloads", "~/bin", "/opt"):
        for p in sorted(glob.glob(os.path.join(os.path.expanduser(d), "[Kk]i[Cc]ad*10.*[Aa]pp[Ii]mage")), reverse=True):
            if _x(p):
                return p
    return None


def cli():
    """The command prefix for kicad-cli."""
    L = launcher()
    if L:
        return [L, "kicad-cli"]
    if shutil.which("kicad-cli"):
        return ["kicad-cli"]
    raise SystemExit("KiCad 10 not found: set KICAD_APPRUN or KICAD_APPIMAGE (see tools/kienv.py)")


def python():
    """The command prefix for a Python that can import pcbnew."""
    L = launcher()
    if L:
        return [L, "python3.11"]
    return [sys.executable]


def share():
    """KiCad's share/kicad directory (stock symbols, footprints, 3D models)."""
    cands = [os.environ.get("KICAD_SHARE", "")]
    L = launcher()
    if L and not L.lower().endswith(".appimage"):
        base = os.path.dirname(L)
        cands += [os.path.join(base, "share", "kicad"), os.path.join(base, "usr", "share", "kicad")]
    cands += ["/usr/share/kicad", "/usr/local/share/kicad"]
    for c in cands:
        # a directory called "symbols" proves nothing (~/.local/share/kicad/10.0/symbols
        # exists and is empty on any machine where KiCad ran): look for a known library
        if c and os.path.isdir(os.path.join(c, "symbols", "Device.kicad_symdir")):
            return c
    raise SystemExit("KiCad's stock libraries not found: set KICAD_SHARE to the share/kicad "
                     "directory of a KiCad 10 install (an extracted AppImage has one)")


def run_cli(args, cwd=None, ok=(0,)):
    r = subprocess.run(cli() + list(args), capture_output=True, text=True, cwd=cwd)
    if r.returncode not in ok:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("FAILED: kicad-cli %s" % " ".join(str(a) for a in args[:3]))
    return r.stdout + r.stderr


if __name__ == "__main__":
    print("launcher:", launcher())
    print("kicad-cli:", " ".join(cli()))
    print("python:   ", " ".join(python()))
    try:
        print("share:    ", share())
    except SystemExit as e:
        print("share:     (none) %s" % e)
    print(run_cli(["version"]).strip())
