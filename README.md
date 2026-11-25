# 无线麦 Ubuntu 版

把小米蓝牙遥控器 2（RC001）或 2 Pro（RC003）的语音通过蓝牙接收，并输出到 Ubuntu 的虚拟麦克风。此版本基于 [SayAll Windows 版](https://github.com/GetSayAll/remote-mic-app-windows)的 ATVV 协议、解码流程和模拟数据，并参考 [macOS 原项目](https://github.com/HD838A/remote-mic-app)。这是独立的 Ubuntu 移植工程，并非官方发行版。完整功能移植仍在进行，逐项状态见 [PORTING.md](PORTING.md)。

## 界面与移植状态

0.2.8 补齐 Linux 自定义快捷键录入接口，接入当前 GTK 窗口的按键边沿，可录入 Ctrl 等组合，并在取消、超时、失焦或退出时清理；录入前已按住的键须先松开。桌面保留组合（例如 Super、Alt+Tab）使用现有安全录入模式：鼠标选择修饰键，再单独按主键。不读取全局键盘，也不要求新增权限。

0.2.7 修复应用图标切换：默认与几何鸭使用独立资源，选择后同步更新侧栏、设置预览、窗口图标和当前用户的应用菜单入口；重启保留选择。设置 GTK 应用名称和 Wayland 程序标识，桌面显示「无线麦 Ubuntu 版」，避免显示 `__main__.py`。

0.2.6 将 ATVV 语音会话接入已配置的按住说话快捷键：开始时按下、停止/中断/退出时释放；拦截所选遥控器语音键原生的 F5 报告。桌面虚拟麦克风改用稳定设备名，避免重启后语音工具保存的麦克风失效。首次升级需在 Vokie 中重新选择一次 SayAll_Microphone。后端不可用时界面显示「快捷键输出未就绪」，不再仅凭配置保存显示已联动。

0.2.5 增加基于公开桌面注册信息的 Vokie 安装/运行检测及启动入口。

0.2.4 增加遥控器 evdev 按键捕获和 uinput 输出：支持已保存的基础快捷键、单击/双击/长按，以及鼠标点击/移动/滚轮动作。安装包为已验证的蓝牙设备 VID 2717 / PID 32b8 和虚拟输入节点配置活动桌面用户访问权限，不赋予普通键盘读取权限。当前真机验证了左方向键映射为 Esc；其他型号/按键仍需分别验收。停止监听、断连或退出会释放按住的输出并归还遥控器。

按键页显示「按键监听已就绪」才会执行映射；如果显示启动失败，请查看连接日志中的 `input_capture_failed`。配置保存后自动重启监听以应用修改。已保存但尚未实现的高级动作（例如组合动作运行、应用聚焦）仍会明确报不可用。

0.2.3 修复窗口卡死：单实例唤起改用本地套接字，避免占用 WebKit 垃圾回收信号。

0.2.2 增加电量读取（优先 BlueZ Battery1，回退标准 GATT Battery Service），连接后及每 60 秒刷新，断开后清除电量。

0.2.1 修复已配对设备不再广播时无法连接的问题，并增加单实例保护、记住设备自动重连及连接日志。

0.2.0 使用 Windows 上游的 Vue 页面和样式，由 GTK/WebKit 在 Linux 桌面加载，包含全部公开页面。专有 Logo 替换为本项目图标；Windows 字体在 Linux 上使用系统字体回退，不能声称逐像素完全一致。页面中的 Windows 驱动操作已替换为 Linux 提示。

已接入蓝牙扫描、连接、虚拟音频、增益、主题/语言持久化、配置导入导出、组合动作编辑及本机应用列表。组合动作执行、应用输入框聚焦、回眸文字捕获、MCP、托盘和自动更新尚未完成；相关操作会明确提示不可用，不使用演示数据假装成功。**本版本不是完整功能复刻的完成版本。**

## 功能与范围

- 图形界面扫描、连接；断线自动重试；接收遥控器按住语音键时的 16 kHz 音频。
- 在 PipeWire（含 pipewire-pulse）或 PulseAudio 中临时创建 `SayAll_Microphone`；退出后自动移除，不修改系统默认设备。
- 不包含语音识别、自动输入文字或全部上游高级功能。请在语音软件中选择这个麦克风，并使用该软件自己的语音触发方式。
- 协议和音频链路已经过模拟数据及本机音频服务测试，但尚未完成 RC001/RC003 的 Ubuntu 真机验收，蓝牙适配器、固件和系统配置可能影响连接。

## 安装桌面应用

适用于 Ubuntu 24.04 或更新版本，需启用 Ubuntu 的 Universe 软件源及网络连接。安装包在 `dist/` 目录，安装时 apt 会安装所需的蓝牙和音频工具：

```bash
sudo apt install ./dist/sayall-linux_0.2.8_all.deb
```

安装后在应用菜单中搜索「无线麦 Ubuntu 版」或「SayAll Linux」启动。也可以在终端运行 `sayall-linux`。卸载使用 `sudo apt remove sayall-linux`。音频系统需要 PipeWire 的 `pipewire-pulse` 兼容层或 PulseAudio；请以当前桌面用户运行应用。

重新构建：先用 Node.js 20.19+ 或 22.12+ 和 Corepack 运行 `./scripts/build-frontend.sh`，再运行 `./scripts/build-deb.sh`（需要 `dpkg-deb`）。安装包不包含 Python 第三方库，apt 会从已配置的软件源安装 `python3-bleak` 等依赖。

## 从源码运行

适用于带桌面会话和蓝牙的 Ubuntu，Python 3.10 或更新版本。以下命令需要网络和 sudo：

```bash
sudo apt update
sudo apt install python3 python3-venv python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 bluetooth bluez pulseaudio-utils python3-evdev
python3 -m venv --system-site-packages .venv
.venv/bin/pip install .
```

Ubuntu 使用 PipeWire 时，还需运行兼容层 `pipewire-pulse`；传统 PulseAudio 也可以。应用必须以当前桌面用户运行，不要使用 sudo 运行程序。

源码安装前需先构建前端（见上面的构建命令），再执行 `.venv/bin/pip install .` 将界面资源一起安装。使用源码虚拟环境时需带 `--system-site-packages`，以便访问系统 PyGObject/WebKit 绑定。

## 使用

1. 打开系统蓝牙，在遥控器进入配对模式后完成配对（通常长按「菜单 + 主页」；以设备说明为准）。若仍连接电视，先断开电视连接。
2. 从应用菜单打开「无线麦 Ubuntu 版」（源码运行可执行 `.venv/bin/sayall-linux`），点击「扫描设备」，选择遥控器，然后点击「连接」。
3. 连接成功后，在需要语音的应用中选择 `SayAll_Microphone` 作为输入设备。按住遥控器语音键说话，松开结束。
4. 退出应用会断开连接并移除临时设备。程序不会主动切换系统默认输入或输出。

源码运行时，命令行也可使用（安装桌面包后将 `.venv/bin/sayall-linux` 换成 `sayall-linux`）：

```bash
.venv/bin/sayall-linux --scan
.venv/bin/sayall-linux --connect AA:BB:CC:DD:EE:FF
```

按 Ctrl+C 退出。扫描列表可能包含其他具名蓝牙设备；只有提供兼容 ATVV 语音服务的设备才能连接。

## 排障

- 确认蓝牙已启用、遥控器已配对且没有连接其他主机。必要时在系统蓝牙设置里断开后重试；程序不会自动重置蓝牙适配器。
- `pactl info` 应显示可访问的 PulseAudio 或 PipeWire Pulse 服务；`pactl list short sources` 可检查连接期间是否出现带 `sayall_` 的输入源。若系统设置显示名称与 `SayAll_Microphone` 略有不同，以设备描述为准。
- 若语音软件早于设备启动，重新打开设备选择列表或重启语音软件。可用系统录音工具选择此麦克风检查输入电平。
- 突然强制终止进程可能留下临时音频模块；可通过 `pactl list short modules` 查看并手动卸载对应 `sayall_` 模块。正常退出会清理。
- 如果能连接但没有声音，提供系统版本、遥控器型号和错误提示有助于排查；请勿公开蓝牙地址或语音内容。

## 开发与测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

协议测试使用上游模拟的 RC001 数据，无法替代真机验收。

## 许可与来源

GPL-3.0-only，见 [LICENSE](LICENSE)。`sayall_linux/protocol.py` 中的 ATVV 协议、解码算法及 `tests/rc001-short-voice.json` 由 [GetSayAll/remote-mic-app-windows](https://github.com/GetSayAll/remote-mic-app-windows) 派生，参考提交 `98fd2a24a6a519809a82bfa02473c0a7835a610f`；原始模拟场景来源为 GetSayAll/hardware-simulation。上游项目及贡献者保留其版权。本项目未使用上游专有图标或品牌素材。
