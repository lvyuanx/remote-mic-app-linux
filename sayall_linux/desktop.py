"""GTK/WebKit desktop host for the upstream Vue frontend."""
import asyncio
import concurrent.futures
import json
import signal
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import threading
import logging
from logging.handlers import RotatingFileHandler
from .instance import DesktopInstance
from .desktop_api import DesktopAPI

def run(test_hook=None):
    import gi
    gi.require_version('Gtk','3.0')
    gi.require_version('WebKit2','4.1')
    from gi.repository import Gtk, WebKit2, GLib, Gio, Gdk
    GLib.set_prgname("sayall-linux")
    GLib.set_application_name("无线麦 Ubuntu 版")
    Gdk.set_program_class("Sayall-linux")
    instance=DesktopInstance()
    if not instance.acquire(): return
    assets=Path(__file__).resolve().parent/'web'
    if not (assets/'index.html').exists():
        assets=Path(__file__).resolve().parent.parent/'frontend'/'dist'
    if not (assets/'index.html').exists():
        instance.close()
        raise RuntimeError('界面资源缺失，请重新构建或安装应用')
    class StaticHandler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
        def list_directory(self,path):
            self.send_error(403)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(StaticHandler,directory=str(assets)))
    origin='http://127.0.0.1:'+str(server.server_port)+'/'
    server_thread=threading.Thread(target=server.serve_forever,daemon=True)
    server_thread.start()
    loop=asyncio.new_event_loop()
    thread=threading.Thread(target=loop.run_forever,daemon=True)
    thread.start()
    api=DesktopAPI()
    logger=logging.getLogger('sayall.connection')
    logger.setLevel(logging.INFO)
    handler=RotatingFileHandler(api.directory/'connection.log',maxBytes=200000,backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    window=Gtk.Window(title='无线麦 Ubuntu 版')
    window.set_wmclass('sayall-linux','Sayall-linux')
    window.set_default_size(1180,800)
    window.set_size_request(960,640)
    window.set_decorated(False)
    from .icons import apply_icon
    try:apply_icon(api.settings.get('icon','standard'),window)
    except Exception as exc:
        logger.warning('event=icon_startup_failed error_type=%s',type(exc).__name__)
        window.set_icon_name('sayall-linux')
    manager=WebKit2.UserContentManager()
    manager.register_script_message_handler('linux')
    manager.add_script(WebKit2.UserScript.new('window.__SAYALL_LINUX__=true;',WebKit2.UserContentInjectedFrames.TOP_FRAME,WebKit2.UserScriptInjectionTime.START,None,None))
    view=WebKit2.WebView.new_with_user_content_manager(manager)
    view.get_settings().set_enable_developer_extras(False)
    window.add(view)
    closing=False
    def close(*_):
        nonlocal closing
        if closing: return True
        closing=True
        window.set_sensitive(False)
        future=asyncio.run_coroutine_threadsafe(api.disconnect(),loop)
        def finished(_):
            GLib.idle_add(Gtk.main_quit)
        future.add_done_callback(finished)
        return True
    window.connect('delete-event',close)
    def present():
        logger.info('event=window_activated source=local_socket')
        window.deiconify()
        window.present()
        return True
    instance.ready()
    def activate(_source, _condition):
        if instance.receive_activation(): present()
        return True
    activation_watch = GLib.io_add_watch(instance.socket.fileno(), GLib.IO_IN, activate)
    async def native(command,args):
        future=concurrent.futures.Future()
        def on_main():
            try: future.set_result(native_main(command,args))
            except Exception as exc: future.set_exception(exc)
            return False
        GLib.idle_add(on_main)
        return await asyncio.wrap_future(future)
    def file_dialog(save,title):
        dialog=Gtk.FileChooserDialog(title=title,transient_for=window,action=Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('取消',Gtk.ResponseType.CANCEL,'保存' if save else '打开',Gtk.ResponseType.OK)
        if save:
            dialog.set_current_name('sayall-configuration.json')
            dialog.set_do_overwrite_confirmation(True)
        result=dialog.run()
        path=dialog.get_filename() if result==Gtk.ResponseType.OK else None
        dialog.destroy()
        return path
    def native_main(command,args):
        if command=='apply_app_icon':
            apply_icon(args['identifier'],window)
            logger.info('event=app_icon_changed identifier=%s',args['identifier'])
            return args['identifier']
        if command in ('hide_main_window','hide_main_window_from_title_bar'):
            close(); return None
        if command=='minimize_main_window': window.iconify(); return None
        if command=='toggle_maximize_main_window':
            from gi.repository import Gdk
            if window.get_window().get_state() & Gdk.WindowState.MAXIMIZED: window.unmaximize()
            else: window.maximize()
            return None
        if command=='drag_window':
            from gi.repository import Gdk
            pointer=Gdk.Display.get_default().get_default_seat().get_pointer()
            _,x,y=pointer.get_position()
            window.begin_move_drag(1,x,y,Gtk.get_current_event_time())
            return None
        if command=='launch_vokie':
            from .vokie import desktop_entry
            entry=desktop_entry()
            if not entry:raise RuntimeError('没有找到已安装的 Vokie')
            Gio.DesktopAppInfo.new_from_filename(str(entry[0])).launch([],None)
            return None
        if command=='get_launch_at_login': return (Path.home()/'.config/autostart/sayall-linux.desktop').exists()
        if command=='set_launch_at_login':
            path=Path.home()/'.config/autostart/sayall-linux.desktop'
            path.parent.mkdir(parents=True,exist_ok=True)
            if args['enabled']: path.write_text('[Desktop Entry]\nType=Application\nName=SayAll Linux\nExec=sayall-linux\nX-GNOME-Autostart-enabled=true\n')
            elif path.exists(): path.unlink()
            return bool(args['enabled'])
        if command in ('scan_registered_apps','list_preset_apps'):
            api.apps={app.get_id():app for app in Gio.AppInfo.get_all() if app.should_show()}
            if command=='list_preset_apps': return [dict(id=key,name=app.get_display_name(),installed=True) for key,app in api.apps.items()]
            return [dict(target=key,name=app.get_display_name(),path=key) for key,app in api.apps.items()]
        if command in ('activate_app_for_learning','test_app_focus'):
            app=api.apps.get(args['target'])
            if not app: raise ValueError('请重新扫描应用列表')
            app.launch([],None); return None
        exports={'export_button_mapping_configuration':'mappings','export_combined_actions':'macros'}
        imports={'import_button_mapping_configuration':'mappings','import_combined_actions':'macros'}
        if command in exports:
            path=file_dialog(True,'导出配置')
            if not path: return False
            Path(path).write_text(json.dumps(api.settings.get(exports[command],{}),ensure_ascii=False,indent=2))
            return True
        if command in imports:
            path=file_dialog(False,'导入配置')
            if not path: return None
            value=json.loads(Path(path).read_text())
            key=imports[command]
            if not isinstance(value,dict) or (key=='mappings' and not isinstance(value.get('actions'),dict)) or (key=='macros' and not isinstance(value.get('definitions'),list)):
                raise ValueError('配置格式不正确')
            return api.save(key,value)
        urls={'open_official_website':'https://sayall.app/','open_git_hub_repository':'https://github.com/GetSayAll/remote-mic-app-windows','open_github_repository':'https://github.com/GetSayAll/remote-mic-app-windows','open_vokie_homepage':'https://vokie.com/','open_recommendations_website':'https://sayall.app/recommendations/'}
        if command in urls:
            Gio.AppInfo.launch_default_for_uri(urls[command],None); return None
        if command=='open_log_directory':
            Gio.AppInfo.launch_default_for_uri(api.directory.as_uri(),None); return str(api.directory)
        if command in ('open_windows_settings','open_vb_cable_download_page'):
            import subprocess
            subprocess.Popen(['gnome-control-center','bluetooth' if args.get('section')=='bluetooth' else 'sound'])
            return None
        if command in ('show_recommendations_page','retry_recommendations_page'): return 'failed'
        if command in ('hide_recommendations_page','go_back_recommendations_page'): return None
        raise NotImplementedError('Linux: 此功能的 Linux 后端尚未完成移植：'+command)
    api.native=native
    def input_event(event,value):
        names={'edge':'button-edge','gesture':'button-gesture','action-error':'linux-error'}
        if event not in names:return
        script='window.dispatchEvent(new CustomEvent('+json.dumps('sayall:'+names[event])+',{detail:'+json.dumps(value,ensure_ascii=False)+'}));'
        def send():
            if not closing:view.evaluate_javascript(script,-1,None,None,None,None,None)
            return False
        GLib.idle_add(send)
    api.event_sink=input_event
    def receive(_,result):
        try:
            data=json.loads(result.get_js_value().to_string())
            if not isinstance(data['id'],int) or not isinstance(data['command'],str) or not isinstance(data.get('args',{}),dict): return
        except (ValueError,KeyError,TypeError): return
        future=asyncio.run_coroutine_threadsafe(api.command(data['command'],data.get('args',{})),loop)
        def done(future):
            try: value,error=future.result(),None
            except Exception as exc: value,error=None,str(exc)
            script='window.__linuxResolve('+json.dumps(data['id'])+','+json.dumps(value,ensure_ascii=False)+','+json.dumps(error,ensure_ascii=False)+');'
            def finish():
                if not closing: view.evaluate_javascript(script,-1,None,None,None,None,None)
                return False
            GLib.idle_add(finish)
        future.add_done_callback(done)
    manager.connect('script-message-received::linux',receive)
    def policy(_,decision,kind):
        if kind in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
            uri=decision.get_navigation_action().get_request().get_uri()
            if not uri.startswith(origin):
                decision.ignore()
                if uri.startswith(('https://','http://')): Gio.AppInfo.launch_default_for_uri(uri,None)
                return True
        return False
    view.connect('decide-policy',policy)
    view.load_uri(origin+'index.html')
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,close)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGINT,close)
    window.show_all()
    if not test_hook:asyncio.run_coroutine_threadsafe(api.input.start(),loop)
    if api.settings.get('lastRemote') and not test_hook:
        asyncio.run_coroutine_threadsafe(api.command('connect_remote',{'deviceId':api.settings['lastRemote']}),loop)
    if test_hook: test_hook(window, view, api, close)
    Gtk.main()
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)
    GLib.source_remove(activation_watch)
    handler.close()
    logger.removeHandler(handler)
    instance.close()
