"""Detect Vokie using public desktop registration and executable identity."""
import configparser
import os
from pathlib import Path
import shlex
import shutil

def desktop_entry():
    directories=[Path.home()/'.local/share/applications',Path('/usr/local/share/applications'),Path('/usr/share/applications')]
    for directory in directories:
        if not directory.exists():continue
        for path in directory.glob('*.desktop'):
            config=configparser.ConfigParser(interpolation=None,strict=False)
            try:
                config.read(path,encoding='utf-8')
                section=config['Desktop Entry']
                if section.get('Hidden','false').lower()=='true':continue
                if section.get('Name','').strip().casefold() not in ('vokie','vokie next'):continue
                command=shlex.split(section.get('Exec',''))
                if not command:continue
                binary=shutil.which(command[0])
                if binary and Path(binary).exists():return path,Path(binary).resolve()
            except (OSError,configparser.Error,ValueError,KeyError):continue
    return None

def installation():
    entry=desktop_entry()
    if not entry:return dict(installed=False,running=False)
    binary=entry[1]
    running=False
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:
            if process.stat().st_uid==os.getuid() and (process/'exe').resolve()==binary:
                running=True;break
        except OSError:pass
    return dict(installed=True,running=running)
