import argparse
import asyncio
import signal
import sys
from . import bridge

def main():
    parser = argparse.ArgumentParser(description='Ubuntu ATVV 蓝牙遥控器语音桥接')
    parser.add_argument('--scan', action='store_true', help='扫描蓝牙设备')
    parser.add_argument('--connect', metavar='ADDRESS', help='连接指定蓝牙地址')
    args = parser.parse_args()
    if args.scan:
        for name, address in asyncio.run(bridge.scan()):
            print(f'{name}\t{address}')
    elif args.connect:
        async def run():
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
            await bridge.run(args.connect, stop, lambda text: print(text, flush=True))
        asyncio.run(run())
    else:
        from .desktop import run
        run()

if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        sys.exit(1)
