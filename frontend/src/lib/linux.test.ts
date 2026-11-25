import { afterEach, describe, expect, it, vi } from 'vitest';
import { isLinuxRuntime, linuxCall } from './linux';

afterEach(() => { delete window.__SAYALL_LINUX__; delete window.webkit; vi.useRealTimers(); });
describe('Linux IPC', () => {
  it('receives native results without exposing Tauri', async () => {
    window.__SAYALL_LINUX__ = true;
    window.webkit = { messageHandlers: { linux: { postMessage: (raw) => {
      const request = JSON.parse(raw);
      expect(request.command).toBe('get_runtime_snapshot');
      window.__linuxResolve(request.id, { platform: 'linux' }, null);
    } } } };
    expect(isLinuxRuntime()).toBe(true);
    expect(await linuxCall('get_runtime_snapshot')).toEqual({ platform: 'linux' });
  });
  it('rejects native failures and publishes an explicit UI error', async () => {
    const notification = vi.fn();
    window.addEventListener('sayall:linux-error', notification);
    window.webkit = { messageHandlers: { linux: { postMessage: (raw) => {
      window.__linuxResolve(JSON.parse(raw).id, null, 'Linux: permission required');
    } } } };
    await expect(linuxCall('start_raw_input')).rejects.toThrow('permission required');
    expect(notification).toHaveBeenCalledOnce();
    window.removeEventListener('sayall:linux-error', notification);
  });
  it('bounds stalled requests', async () => {
    vi.useFakeTimers();
    window.webkit = { messageHandlers: { linux: { postMessage: () => {} } } };
    const result = expect(linuxCall('scan_paired_remotes')).rejects.toThrow('超时');
    await vi.advanceTimersByTimeAsync(30000);
    await result;
  });
});
