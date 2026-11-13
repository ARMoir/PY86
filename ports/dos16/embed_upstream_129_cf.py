"""Put verified 8086 A/B scripts and executables into a bootable FAT16 CF IMG.

Requires a *separately prepared* 16 MiB bootable FreeDOS FAT16 hard-disk
image with an MBR and the mtools package. Never fabricates DOS boot code.
Only writes files into the existing FAT16 partition. Never modifies
KERNEL.SYS, COMMAND.COM, the MBR, or the partition boot sector.
"""
from argparse import ArgumentParser
from pathlib import Path
from zipfile import ZipFile
import struct
import subprocess
import tempfile

SIZE=16*1024*1024
NEEDED={"P24BASE.EXE","P24OPT.EXE","P29BASE.EXE","P29OPT.EXE",
        "RUN4.BAT","RUN12.BAT","RUN29.BAT","RUNVER.BAT",
        "DEMO.PY","CLOCK.PY"}

def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--archive",type=Path,required=True)
    args=p.parse_args()
    image=args.image.resolve()
    with image.open("rb") as f:
        mbr=f.read(512)
    if image.stat().st_size!=SIZE:
        raise SystemExit("Expected 16 MiB FAT16 FreeDOS disk; size mismatch")
    if mbr[510:512]!=b"\x55\xaa":
        raise SystemExit("Missing valid hard disk MBR boot signature")
    part=mbr[446:462]
    if part[4] not in (0x04,0x06,0x0e):
        raise SystemExit("First partition is not FAT16: "+hex(part[4]))
    start,count=struct.unpack_from("<II",part,8)
    if start<1 or count<4096 or start+count>SIZE//512:
        raise SystemExit("Invalid FAT16 primary partition geometry")
    offset=start*512
    with image.open("rb") as f:
        f.seek(offset)
        vbr=f.read(512)
    if vbr[510:512]!=b"\x55\xaa":
        raise SystemExit("Missing FAT16 partition boot signature")
    if struct.unpack_from("<H",vbr,11)[0]!=512 or vbr[16]!=2:
        raise SystemExit("Unexpected FAT16 BIOS parameter block")
    with ZipFile(args.archive) as z:
        names=set(z.namelist())
        if not NEEDED.issubset(names) or z.testzip() is not None:
            raise SystemExit("Test ZIP missing one or more validated executables")
        names={name for name in names
               if len(name.split("."))==2 and
               len(name.split(".")[0])<=8 and
               len(name.split(".")[1])<=3 and
               not name.startswith("__")}
        with tempfile.TemporaryDirectory() as tmp:
            for name in sorted(names):
                data=z.read(name)
                file=Path(tmp)/name
                file.write_bytes(data)
                subprocess.run(["mcopy","-o","-i",str(image)+"@@"+str(offset),
                                str(file),"::/"+name],check=True)
    out=subprocess.run(["mdir","-i",str(image)+"@@"+str(offset),"::/"],
                       capture_output=True,text=True,check=True)
    for name in NEEDED:
        if name.upper() not in out.stdout.upper():
            raise SystemExit("FAT16 postcopy verification failed: "+name)
    with image.open("rb") as f:
        if f.read(512)!=mbr:
            raise SystemExit("MBR must remain byte-for-byte unchanged")
        f.seek(offset)
        if f.read(512)!=vbr:
            raise SystemExit("FreeDOS partition boot sector changed")
    print("PASS bootable FAT16 test payload embedded",image)
    print("Partition LBA start",start,"sectors",count)
    print("DOS 8.3 files",len(names))
    print("FreeDOS boot files retained untouched (not boot-executed).")

if __name__=="__main__":
    main()
