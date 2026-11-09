"""Ways to run Bambu Studio's command-line slicer on a case. Every runner gets the same input files and the same
arguments, in a fresh empty working directory with a fresh empty home (so no saved presets or app config can leak
in), LC_ALL=C (what the official AppImage's AppRun sets) and no network."""
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REFERENCE_IMAGE = "pandy-studio-reference:02.08.02.61"
BUILD_IMAGE = "pandy-studio-build"
SUDO = ["sudo", "-n"] if os.geteuid() != 0 else []


@dataclass
class Run:
    returncode: int
    seconds: float
    stdout: str
    stderr: str
    out_dir: Path


# Bambu Studio parallelises slicing with TBB, and its output then depends on thread timing: the official build
# gives different G-code for the same input from one run to the next (equivalence/README.md, "Determinism"). Pinned
# to one CPU (TBB sizes its pool from the CPU affinity mask) it is reproducible, so that is how every runner slices.
# Each worker thread of run.py gets its own CPU (set_cpu), so parallel cases don't share one.
_cpu = __import__("threading").local()


def set_cpu(n: int):
    _cpu.n = n


def pin():
    return ["--cpuset-cpus", str(getattr(_cpu, "n", 0))]


class Runner:
    name = "?"

    def describe(self) -> dict:
        return {"runner": self.name}

    def run(self, inputs: Path, args: list, out_dir: Path, timeout: int = 1800) -> Run:
        raise NotImplementedError


def _prepare(inputs: Path, out_dir: Path) -> Path:
    """A world-writable working copy of the case inputs: the containers run as other users."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    work = out_dir / "work"
    shutil.copytree(inputs, work)
    (work / "out").mkdir()
    (work / "home").mkdir()
    for p in [out_dir, *work.rglob("*")]:
        p.chmod(0o777 if p.is_dir() else 0o666)
    work.chmod(0o777)
    return work


def _finish(work: Path, out_dir: Path, p, t0) -> Run:
    for f in (work / "out").iterdir():
        shutil.move(str(f), out_dir / f.name)
    (out_dir / "stdout.txt").write_text(p.stdout)
    (out_dir / "stderr.txt").write_text(p.stderr)
    shutil.rmtree(work, ignore_errors=True)
    return Run(p.returncode, time.time() - t0, p.stdout, p.stderr, out_dir)


class Reference(Runner):
    """The official Bambu Studio 02.08.02.61 AppImage, in Pandy Slicer's image (its Dockerfile pins the download's
    SHA-256): what Pandy Slicer runs, and what every candidate must match byte for byte."""
    name = "reference"

    @lru_cache(maxsize=1)
    def describe(self):
        image = subprocess.run([*SUDO, "docker", "image", "inspect", "-f", "{{.Id}}", REFERENCE_IMAGE],
                               capture_output=True, text=True).stdout.strip()
        return {"runner": self.name, "image": REFERENCE_IMAGE, "image_id": image,
                "binary": "/opt/bambu-studio/bin/bambu-studio (via AppRun)"}

    def run(self, inputs, args, out_dir, timeout=1800):
        work = _prepare(inputs, out_dir)
        t0 = time.time()
        p = subprocess.run([*SUDO, "docker", "run", "--rm", "--network", "none", *pin(), "-v", f"{work}:/work", "-w", "/work",
                            "-e", "HOME=/work/home", "-e", "LC_ALL=C", "--entrypoint", "/opt/bambu-studio/AppRun",
                            REFERENCE_IMAGE, *args, "--outputdir", "/work/out"],
                           capture_output=True, text=True, timeout=timeout)
        return _finish(work, out_dir, p, t0)


class Engine(Runner):
    """A Pandy Studio engine package (bin/pandy-engine + the reference's resources/), run on this machine: the x86-64
    build in the build image, or the arm64 build under QEMU user-mode emulation."""

    def __init__(self, package: Path, arch: str):
        self.package, self.arch = Path(package).resolve(), arch
        self.name = f"engine-{arch}" + ("-qemu" if arch == "aarch64" else "")

    def describe(self):
        return {"runner": self.name, "package": str(self.package), **package_identity(self.package)}

    def run(self, inputs, args, out_dir, timeout=3600):
        if self.arch == 'aarch64' and not Path('/usr/bin/qemu-aarch64-static').is_file():
            raise RuntimeError('QEMU is unavailable at /usr/bin/qemu-aarch64-static; use a real device runner')
        work = _prepare(inputs, out_dir)
        t0 = time.time()
        exe = ["/pkg/bin/pandy-engine"]
        if self.arch == "aarch64":
            exe = ["/usr/bin/qemu-aarch64-static", *exe]
        p = subprocess.run([*SUDO, "docker", "run", "--rm", "--network", "none", *pin(), "-u", "10001:10001",
                            "-v", f"{work}:/work", "-v", f"{self.package}:/pkg:ro", "-w", "/work",
                            *(["-v", "/usr/bin/qemu-aarch64-static:/usr/bin/qemu-aarch64-static:ro"] if self.arch == "aarch64" else []),
                            "-e", "HOME=/work/home", "-e", "LC_ALL=C", BUILD_IMAGE, *exe, *args, "--outputdir", "/work/out"],
                           capture_output=True, text=True, timeout=timeout)
        return _finish(work, out_dir, p, t0)


class Device(Runner):
    """The arm64 engine package on an Android phone over adb, as the app runs it: a static executable with the
    resources next to it, in a scratch directory."""

    def __init__(self, package: Path, serial: str):
        self.package, self.serial = Path(package).resolve(), serial
        self.name = f"device-{serial}"
        self.ident = package_identity(self.package)
        self.remote = f"/data/local/tmp/pandy-engine-{self.ident['engine_sha256'][:12]}"

    def adb(self, *a, **kw):
        return subprocess.run(["adb", "-s", self.serial, *a], capture_output=True, text=True, **kw)

    def describe(self):
        model = self.adb("shell", "getprop", "ro.product.model").stdout.strip()
        abi = self.adb("shell", "getprop", "ro.product.cpu.abi").stdout.strip()
        sdk = self.adb("shell", "getprop", "ro.build.version.sdk").stdout.strip()
        return {"runner": self.name, "model": model, "abi": abi, "sdk": sdk, "remote": self.remote, **self.ident}

    def fastest_cpu(self):
        """Follow AndroidEngine: inspect online CPUs and choose the first highest maximum frequency."""
        online = self.adb("shell", "cat /sys/devices/system/cpu/online").stdout.strip()
        cpus = []
        for part in online.split(','):
            bounds = part.split('-')
            if len(bounds) == 1:
                cpus.append(int(bounds[0]))
            elif len(bounds) == 2:
                cpus.extend(range(int(bounds[0]), int(bounds[1]) + 1))
            else:
                raise ValueError("Cannot determine online CPUs")
        if not cpus:
            raise ValueError("Cannot determine online CPUs")
        # AndroidEngine iterates 0 until Runtime.availableProcessors(), not arbitrary CPU IDs.
        count = len(cpus)
        values = []
        for cpu in range(count):
            result = self.adb("shell", f"cat /sys/devices/system/cpu/cpu{cpu}/cpufreq/cpuinfo_max_freq")
            try:
                values.append(int(result.stdout.strip()))
            except ValueError:
                values.append(0)
        return max(range(count), key=lambda cpu: values[cpu])

    def install(self):
        marker = f"{self.ident['engine_sha256']}:{self.ident['resources_sha256']}"
        if self.adb("shell", f"cat {self.remote}/.complete").stdout.strip() == marker:
            return
        uid = self.adb("shell", "id -u").stdout.strip()
        gid = self.adb("shell", "id -g").stdout.strip()
        if not uid.isdecimal() or not gid.isdecimal():
            raise RuntimeError("Cannot determine the device shell's user and group")
        with tempfile.TemporaryDirectory() as t:
            tar = Path(t) / "pkg.tar"
            subprocess.run(["tar", f"--owner={uid}", f"--group={gid}", "--numeric-owner", "-C", str(self.package), "-cf", str(tar), "."], check=True)
            self.adb("shell", f"rm -rf {self.remote} && mkdir -p {self.remote}")
            r = self.adb("push", str(tar), f"{self.remote}/pkg.tar")
            if r.returncode:
                raise RuntimeError(r.stderr)
        r = self.adb("shell", f"cd {self.remote} && tar -xf pkg.tar && rm pkg.tar && chmod 755 bin/pandy-engine && echo {marker} > .complete")
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)

    def run(self, inputs, args, out_dir, timeout=7200):
        self.install()
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        job = f"{self.remote}/job"
        self.adb("shell", f"rm -rf {job} && mkdir -p {job}/out {job}/home")
        for f in inputs.iterdir():
            self.adb("push", str(f), f"{job}/{f.name}")
        cmd = " ".join(shlex.quote(a) for a in args)
        t0 = time.time()
        # PANDY_ENGINE_HOME as the app sets it: the engine finds resources/ there (engine/android-location.c).
        mask = format(1 << self.fastest_cpu(), 'x')
        p = self.adb("shell", f"cd {job} && env -i HOME={job}/home LC_ALL=C TMPDIR={job} PANDY_ENGINE_HOME={self.remote} GLIBC_TUNABLES=glibc.pthread.rseq=0 PATH=/system/bin /system/bin/taskset {mask} {self.remote}/bin/pandy-engine {cmd} --outputdir {job}/out; echo PANDY_RC=$?",
                     timeout=timeout)
        seconds = time.time() - t0
        rc = int(p.stdout.rsplit("PANDY_RC=", 1)[1].strip()) if "PANDY_RC=" in p.stdout else -1
        listing = self.adb("shell", f"ls {job}/out").stdout.split()
        for name in listing:
            self.adb("pull", f"{job}/out/{name}", str(out_dir / name))
        (out_dir / "stdout.txt").write_text(p.stdout)
        (out_dir / "stderr.txt").write_text(p.stderr)
        self.adb("shell", f"rm -rf {job}")
        return Run(rc, seconds, p.stdout, p.stderr, out_dir)


def package_identity(package: Path) -> dict:
    """SHA-256 of the engine executable and of the resources tree (the hash of the sorted list of 'sha256  path'
    lines), so a report pins exactly what was tested and the app can show the same numbers."""
    import hashlib
    exe = Path(package) / "bin" / "pandy-engine"
    res = Path(package) / "resources"
    resources = resources_identity(res)
    return {"engine_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(), **resources}


DESKTOP_ONLY_RESOURCES = frozenset({"web", "hms", "images", "model", "tooltip", "i18n", "shaders"})


def resources_identity(res: Path, excluded=()) -> dict:
    import hashlib
    res = Path(res)
    if not res.is_dir():
        raise FileNotFoundError(f"Missing resources: {res}")
    lines = []
    for f in sorted(p for p in res.rglob("*") if p.is_file() and p.relative_to(res).parts[0] not in excluded):
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(res).as_posix()}")
    return {"resources_sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
            "resources_files": len(lines)}


def verify_resources(reference: Reference, candidate=None):
    """Require the materialised inputs, official image and candidate package to use the same resource tree."""
    code = ("import hashlib,pathlib; r=pathlib.Path('/opt/bambu-studio/resources'); "
            "fs=sorted(p for p in r.rglob('*') if p.is_file()); "
            "line=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(r).as_posix(); "
            "lines=[(p.relative_to(r).parts[0],line(p)) for p in fs]; "
            "digest=lambda a:hashlib.sha256('\\n'.join(a).encode()).hexdigest(); "
            f"excluded={sorted(DESKTOP_ONLY_RESOURCES)!r}; "
            "subset=[v for k,v in lines if k not in excluded]; "
            "print(digest([v for k,v in lines]),len(lines),digest(subset),len(subset))")
    p = subprocess.run([*SUDO, "docker", "run", "--rm", "--network", "none", "--entrypoint", "python3",
                        REFERENCE_IMAGE, "-c", code], capture_output=True, text=True, check=True, timeout=180)
    parts = p.stdout.strip().split()
    if len(parts) != 4:
        raise RuntimeError("Could not identify the official resources")
    expected = {"resources_sha256": parts[0], "resources_files": int(parts[1])}
    packaged = {"resources_sha256": parts[2], "resources_files": int(parts[3])}
    source = resources_identity(REPO / "build/reference/resources")
    if source != expected:
        raise RuntimeError("Reference image and extracted reference resources differ")
    if candidate is not None and not isinstance(candidate, Reference):
        actual = candidate.ident if isinstance(candidate, Device) else package_identity(candidate.package)
        allowed = [packaged] if isinstance(candidate, Device) else [packaged, expected]
        if not any(all(actual.get(key) == value for key, value in identity.items()) for identity in allowed):
            raise RuntimeError("Candidate and official reference resources differ")
    return {"reference": expected, "packaged": packaged}
