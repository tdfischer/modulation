# -*- coding: utf-8 -*-
# Copyright 2010 Trever Fischer <tdfischer@fedoraproject.org>
#
# This file is part of modulation.
#
# modulation is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# modulation is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with modulation. If not, see <http://www.gnu.org/licenses/>.

"""
Modulation, the universal media framework
"""

import logging
import musicbrainz2.webservice
#import musicdns
import tagpy
import threading
import copy
from Queue import Queue, Empty
import threading
import weakref
import time
import inspect
import sys

_threadStartLock = threading.Lock()

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

_log = logging.getLogger("modulation")
_log.addHandler(NullHandler())

def allNodes():
    """Returns a list of all running Plugins"""
    ret = ()
    for node in threading.enumerate():
        if (isinstance(node, Plugin)):
            ret += (node,)
    return ret

def killAll():
    """Kills all running plugins"""
    _log.debug("Active nodes:")
    for node in allNodes():
        _log.debug("%s", node)
    for node in allNodes():
        _log.debug("Killing %s", node)
        node.kill()

def kickstart(*nodes):
    """Starts up a list of plugins"""
    for node in nodes:
        _log.debug("Kickstarting %s", node)
        node.acceptPacket(KickstartPacket(node))
    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt, e:
        killAll()
    _log.debug("Remaining threads:")
    for thread in threading.enumerate():
        _log.debug(repr(thread))

class Packet(object):
    """Packets form the base system of signaling changes to other plugins"""
    def __init__(self, origin=None):
        self.__origin = origin
        if __debug__:
            stack = inspect.stack()
            self._stack = []
            for frame in stack:
                f = inspect.getframeinfo(frame[0])
                self._stack.append("File \"%s\", line %i, in %s\n\t%s"%(f[0], f[1], f[2], f[3][0].strip()))
            del stack

    @property
    def origin(self):
        """The origin determines which plugin created the packet"""
        return self.__origin

    def __repr__(self):
        return "<%s from %r>"%(self.__class__.__name__, self.__origin)

class KillPacket(Packet):
    """Asks the Plugin to terminate"""
    pass

class KillAllPacket(KillPacket):
    """Asks the Plugin to terminate and forward the packet onto all connected plugins"""
    pass

class KickstartPacket(Packet):
    """Guaranteed to be the first packet a Plugin recieves"""
    pass

class ExceptionPacket(Packet):
    """Indicates that an exception has occured in an upstream Plugin"""
    def __init__(self, origin, exception):
        Packet.__init__(self, origin)
        self.__e = exception
    @property
    def exception(self):
        return self.__e

def input(pktType):
    """Decorator used to announce a method used to handle packets of a specific type"""
    def wrap(f):
        if (isinstance(f, Input)):
            f.addType(pktType)
            return f
        return Input(f, (pktType,))
    return wrap

class Input(object):
    """Wraps a method to ensure that it only ever recieves packet types it wants"""
    def __init__(self, func, pktTypes):
        for name in set(dir(func)) - set(dir(self)):
            setattr(self, name, getattr(func, name))
        for name in ("__doc__", "__name__"):
            setattr(self, name, getattr(func, name))
        if (len(inspect.getargspec(func).args) < 2):
            raise TypeError, "Inputs must have at least 2 arguments, not %i"%(len(inspect.getargspec(func).args))
        self.__func = func
        self.__types = pktTypes
        self.__bound = None
        
    def addType(self, pktType):
        self.__types += (pktType,)
    
    def types(self):
        return self.__types
        
    def handles(self, pkt):
        for pktType in self.__types:
            if (isinstance(pkt, pktType)):
                return True
        return False
    
    def __get__(self, obj, type=None):
        if (self.__bound is None):
            if (obj is None):
                self.__bound = self
            new_func = self.__func.__get__(obj, type)
            self.__bound = self.__class__(new_func, self.__types)
        return self.__bound
        
    def __call__(self, *args, **kwargs):
        return self.__func(*args, **kwargs)
        
    def __repr__(self):
        return repr(self.__func)
        
    def __str__(self):
        return str(self.__func)

class Plugin(threading.Thread):
    """A Plugin is the atomic element of a modulation graph
    
    Plugins send and recieve packets, and do stuff depending on what packet type they got.
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self._outputs = {}
        self._log = logging.getLogger("modulation.plugins.%s"%(self.__class__.__name__))
        self._q = Queue()
        self._running = True
        self._timeout = None

    def inputs(self):
        """Lists all inputs declared with the input() decorator"""
        ret = []
        for m in dir(self):
            if (isinstance(getattr(self, m), Input)):
                ret.append(getattr(self, m))
        return ret;
        
    def listenTo(self, other):
        """Connects the outputs of another plugin to this plugin's inputs"""
        other.connectOutput(self)

    def connectOutput(self, other, packetType = None):
        """Connects this plugin's output to another plugin's input."""
        if (not isinstance(other, Plugin)):
            raise TypeError
        if (not packetType in self._outputs):
            self._outputs[packetType] = []
        self._outputs[packetType].append(other)

    def outputs(self):
        """Returns the list of plugins listening for packets"""
        return self._outputs

    def disconnectOutput(self, other, packetType = None):
        """Causes a plugin to stop listening to this plugin's output"""
        self._outputs[packetType].remove(other)

    def handlePacket(self, pkt):
        """Called from this plugin's thread. Tells this plugin to operate on Packet pkt

        If you're writing a plugin, this is probably not the method to implement. Have
        a look at the input() decorator instead.
        """
        self._log.debug("Checking inputs: %s", self.inputs())
        for input in self.inputs():
            if (input.handles(pkt)):
                self._log.debug("Passing packet to %s", input)
                input(pkt)
            else:
                self._log.debug("%s doesn't want %s", input, pkt)

    def acceptPacket(self, pkt):
        """Places a packet into the plugin's message queue"""
        if (not isinstance(pkt, Packet)):
            raise TypeError, "Only Packets may be recieved."
        if (not self._running):
            self._log.warn("Recieved packet while dead.")
        else:
            if (isinstance(pkt, KillPacket)):
                self._log.debug("Caught kill packet.")
                #self.stop()
                if (isinstance(pkt, KillAllPacket)):
                    self._log.debug("Its a killall packet. Forwarding. Godspeed.")
                    self.send(pkt)
            _threadStartLock.acquire()
            if (not self.isAlive()):
                self._log.debug("Autostarting %r", self)
                if (not isinstance(pkt, KickstartPacket)):
                    self._q.put(KickstartPacket())
                self.start()
            _threadStartLock.release()
            self._q.put(pkt)
            self._log.debug("Accepted packet %r", pkt)

    def kill(self):
        """Asks this plugin to terminate"""
        self.acceptPacket(KillPacket(self))

    @input(KillPacket)
    def __kill(self, pkt=None):
        """Kills the thread"""
        self._kill()
        self._log.debug("Killing the loop.")
        self._running = False
        self._q.put(None)
        
    def _kill(self):
        """Called once a plugin is asked to clean up and exit"""
        pass

    def run(self):
        """The main loop for a plugin
        
        In this loop, plugins sit idle, waiting for a packet to show up.
        Once one does, it calls handlePacket(), which then passes the packet on to
        any registered inputs.
        """
        try:
            while (self._running):
                self._log.debug("Waiting for packets...")
                timeout = False
                try:
                    pkt = self._q.get(True, self._timeout)
                except Empty:
                    pkt = PacketTimeout(self)
                    timeout = True
                self._log.debug("Handling packet %s", pkt)
                #if (isinstance(pkt, KillPacket)):
                #    self._log.debug("Got a kill packet in the queue.")
                #    self.stop()
                #else:
                self.handlePacket(pkt)
                if (not timeout):
                    self._q.task_done()
        except Exception, e:
            if __debug__:
                trace = "Packet created here:\n"
                for line in pkt._stack:
                    trace+=line+"\n"
                self._log.error(trace)
            self._log.error("Exception caught. Passing it on.")
            self.kill()
            self.send(ExceptionPacket(self, e))
            raise
        self._log.debug("Exiting.")

    def _send(self, pkt, ptype):
        """Sends Packet pkt to all connected plugins waiting on ptype type packets"""
        if (ptype in self._outputs):
            for out in self._outputs[ptype]:
                if (out._running):
                    outpkt = copy.copy(pkt)
                    self._log.debug("Sending packet %r to %s", outpkt, out.__class__.__name__)
                    out.acceptPacket(outpkt)
                else:
                    self._log.debug("Removing dead node %s", out)
                    self._outputs[ptype].remove(out)

    def send(self, pkt):
        """Sends Packet pkt to all connected plugins"""
        if (not isinstance(pkt, Packet)):
            raise TypeError, "Only Packets can be sent."
        self._send(pkt, type(pkt))
        self._send(pkt, None)

class PacketTimeout(Packet):
    """Indicates a timeout while waiting for a packet"""
    pass