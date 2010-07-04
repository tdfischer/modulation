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

import sys
from modulation import PacketTimeout, Plugin, Packet
from modulation.media import MediaPacket, FileSource, MediaList
from modulation.controls import ControlPacket, Start, Stop
from modulation.streaming import StreamProgressPacket
from modulation.notifications import PlaylistEmpty, PlaybackComplete
import time

def walkPluginTree(node, callback, depth = 0, seen = []):
    """Walks along the plugin tree, calling callback once for each element"""
    callback(node, depth)
    for typeList in node.outputs().itervalues():
        for child in typeList:
            if (child not in seen):
                seen.append(child)
                walkPluginTree(child, callback, depth+1)

def dumpPluginTree(root):
    """Prints the tree of plugins"""
    walkPluginTree(root, _printPluginTreeNode)

def _printPluginTreeNode(node, depth):
    print '-'*depth, node

class Watchdog(Plugin):
    def __init__(self, timeout):
        Plugin.__init__(self)
        self._timeout = timeout

    def handlePacket(self, pkt):
        super(Watchdog, self).handlePacket(pkt)
        self.send(pkt)

    def _debugTree(self, node, depth):
        self._log.debug("%s %r",'-'*depth, node)

class PrintOutput(Plugin):
    """An output plugin that prints control packet data"""
    def __init__(self):
        Plugin.__init__(self)
    def _printMedia(self, media):
        self._log.info("Metadata:")
        for key,value in media.getMetadata().iteritems():
            self._log.info("\t%s: %s"%(key, value))
        self._log.info("Decoder: %s"%(media.getStream().getDecoder()))

    def handlePacket(self, pkt):
        super(PrintOutput, self).handlePacket(pkt)
        try:
            if (isinstance(pkt, MediaPacket)):
                self._log.info("New Media recieved from %s"%(pkt.origin))
                self._printMedia(pkt.getMedia())
            elif (isinstance(pkt, MediaList)):
                self._log.info("New MediaList recieved from %s"%(pkt.origin))
                for m in pkt.media:
                    self._printMedia(m)
            elif (isinstance(pkt, ControlPacket)):
                self._log.info("New control packet from %s: %s"%(pkt.origin, pkt))
            elif isinstance(pkt, StreamProgressPacket):
                self._log.info("Stream progress: %s/%s (%s%%)" % (pkt.value, pkt.max, pkt.percent*100))
            elif isinstance(pkt, PlaylistEmpty):
                self._log.info("Playlist is empty.")
            elif isinstance(pkt, PacketTimeout):
                self._log.info("Packet timeout. Here's the plugin tree:")
        except UnicodeEncodeError, e:
            pass
        except UnicodeDecodeError, e:
            pass

class NullInput(FileSource):
    """An input plugin that reads an endless stream from /dev/null"""
    def __init__(self):
        FileSource.__init__(self, "/dev/null")

class NullOutput(Plugin):
    """An output plugin that writes all data input to /dev/null"""
    def __init__(self, writeDelay=0):
        Plugin.__init__(self)
        self.__out = None
        self.__delay = writeDelay

    def handlePacket(self, pkt):
        super(NullOutput, self).handlePacket(pkt)
        if type(pkt) is MediaPacket:
            stream = pkt.media.getStream()
            size = pkt.media.getStream().size()
            count = 0
            while True:
                buf = stream.read(1024)
                count+=len(buf)
                self.send(StreamProgressPacket(self, count, size))
                self.__out.write(buf)
                time.sleep(self.__delay)
                if len(buf) == 0:
                    break
            self.send(PlaybackComplete(self))
        elif isinstance(pkt, Start):
            self.__out = open("/dev/null", "w")
        elif isinstance(pkt, Stop):
            self.kill()
