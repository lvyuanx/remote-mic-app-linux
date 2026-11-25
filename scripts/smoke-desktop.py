"""Visit every public page in the real GTK host. Requires a desktop session."""
from gi.repository import GLib
from sayall_linux.desktop import run
failures = []
def check(window, view, api, close):
    index = 0
    def visit():
        nonlocal index
        if index == 8:
            close()
            return False
        target = index
        index += 1
        script = '(()=>{const links=document.querySelectorAll(".nav-item");if(links.length!==8)throw Error("navigation missing");links['+str(target)+'].click();return true})()'
        def done(view, result, *_):
            try:
                assert view.evaluate_javascript_finish(result).to_boolean()
                print('page', target, 'navigation passed', flush=True)
            except Exception as exc:
                failures.append(str(exc))
                close()
        view.evaluate_javascript(script, -1, None, None, None, done, None)
        GLib.timeout_add(1000, visit)
        return False
    GLib.timeout_add(3000, visit)
    GLib.timeout_add(20000, lambda: close())
run(check)
if failures:
    raise RuntimeError('; '.join(failures))
