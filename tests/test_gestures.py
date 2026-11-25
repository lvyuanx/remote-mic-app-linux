import asyncio
import unittest
from sayall_linux.input_mapping import GestureEngine

SINGLE={'type':'shortcut','chord':{'keys':['backspace']}}
DOUBLE={'type':'shortcut','chord':{'keys':['escape']}}
LONG={'type':'shortcut','chord':{'keys':['home']}}
class Gestures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events=[]
        self.engine=GestureEngine(lambda a,m,o:self.events.append((a,m,o)),double_delay=.025,long_delay=.04)
    async def asyncTearDown(self):await self.engine.close()
    async def test_simple_shortcut_is_paired_without_waiting(self):
        self.engine.edge('power',116,1,{'single':SINGLE})
        self.assertEqual(self.events,[(SINGLE,'begin','power')])
        self.engine.edge('power',116,2,{'single':SINGLE})
        self.engine.edge('power',116,0,{'single':SINGLE})
        self.assertEqual(self.events[-1],(None,'end','power'))
        self.assertEqual(len(self.events),2)
    async def test_double_press_does_not_leak_single_action(self):
        actions={'single':SINGLE,'double':DOUBLE}
        for _ in range(2):
            self.engine.edge('power',116,1,actions)
            self.engine.edge('power',116,0,actions)
            await asyncio.sleep(.005)
        await asyncio.sleep(.03)
        self.assertEqual(self.events,[(DOUBLE,'pulse','power')])
    async def test_long_press_does_not_fire_single(self):
        actions={'single':SINGLE,'long':LONG}
        self.engine.edge('power',116,1,actions)
        await asyncio.sleep(.05)
        self.engine.edge('power',116,0,actions)
        self.assertEqual(self.events,[(LONG,'begin','power'),(None,'end','power')])
    async def test_shutdown_cancels_delayed_actions_and_releases_hold(self):
        self.engine.edge('power',116,1,{'single':SINGLE})
        self.engine.edge('up',103,1,{'single':SINGLE,'double':DOUBLE})
        self.engine.edge('up',103,0,{'single':SINGLE,'double':DOUBLE})
        await self.engine.close()
        await asyncio.sleep(.04)
        self.assertEqual(self.events,[(SINGLE,'begin','power'),(None,'end','power')])
    async def test_release_uses_action_from_press_even_if_config_changed(self):
        self.engine.edge('power',116,1,{'single':SINGLE})
        self.engine.edge('power',116,0,{'single':DOUBLE})
        self.assertEqual(self.events[-1],(None,'end','power'))
