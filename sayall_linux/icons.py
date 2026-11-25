"""Apply app icon preferences to the GTK window and per-user desktop entry."""
import configparser
import io
import os
from pathlib import Path
import tempfile

ICONS={'standard':'sayall-linux','faceted-duck':'sayall-linux-duck'}

def icon_name(identifier):
    if identifier not in ICONS:raise ValueError('未知的应用图标')
    return ICONS[identifier]

def asset_path(identifier):
    filename=icon_name(identifier)+'.svg'
    for directory in (Path('/usr/share/icons/hicolor/scalable/apps'),Path(__file__).resolve().parent.parent/'packaging'):
        path=directory/filename
        if path.is_file():return path
    raise RuntimeError('应用图标资源缺失，请重新安装')

def write_launcher(identifier, data_home=None, system_entry=None):
    name=icon_name(identifier)
    directory=Path(data_home or os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'applications'
    target=directory/'sayall-linux.desktop'
    base=target if target.exists() else Path(system_entry or '/usr/share/applications/sayall-linux.desktop')
    config=configparser.ConfigParser(interpolation=None,strict=False)
    config.optionxform=str
    config.read(base,encoding='utf-8')
    if 'Desktop Entry' not in config:raise RuntimeError('没有找到有效的应用菜单入口')
    if config['Desktop Entry'].get('Icon')==name and target.exists():return target
    config['Desktop Entry']['Icon']=name
    buffer=io.StringIO();config.write(buffer,space_around_delimiters=False)
    directory.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=directory,prefix='.sayall-icon-')
    try:
        with os.fdopen(fd,'w') as stream:stream.write(buffer.getvalue())
        os.chmod(tmp,0o644)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return target

def apply_icon(identifier, window):
    path=asset_path(identifier)
    window.set_icon_from_file(str(path))
    return write_launcher(identifier)
