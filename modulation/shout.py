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

from __future__ import division
import shoutpy
import modulation.streaming
import modulation.media
import modulation.codecs.OggVorbis
import time

class ShoutcastOutputStream(modulation.streaming.DataStream):
    """A DataStream that outputs to an icecast server"""
    def __init__(self, user, password, mount):
        self.__shout = shoutpy.Shout()
        self.__shout.user = user
        self.__shout.password = password
        self.__shout.mount = mount
        self.__open = False
        self.__delay = 0

    def write(self, buf):
        try:
            delay = self.__delay - time.time()
            if (delay > 0):
                time.sleep(delay)
            else:
                print "Buffer underrun by %i ms"%(delay*-1000)
            self.__shout.send(buf)
            delay = self.__shout.delay()
            print "Need to delay %ims"%delay
            self.__delay = time.time()+delay/1000
        except RuntimeError, e:
            self.close()
            self.open()

    def open(self):
        self.__shout.open()
        self.__open = True

    def close(self):
        self.__shout.close()
        self.__open = False

    @property
    def closed(self):
        return self.__open

class ShoutcastOutput(modulation.media.MediaSink):
    def __init__(self, user, password, mount):
        modulation.media.MediaSink.__init__(self)
        self.setOutputStream(ShoutcastOutputStream(user, password, mount))
        self.getOutputStream().open()
        self.setBufferSize(2048)
    
    @modulation.input(modulation.media.MediaPacket)
    def playMedia(self, pkt):
        """Changes the current MediaObject being streamed"""
        encoder = modulation.codecs.getEncoder("application/ogg")
        meta = pkt.media.getMetadata()
        #Scale down for streaming on low bandwidth
        meta['bitrate'] = 32
        encoder.setMetadata(meta)
        fh = pkt.media.getStream()
        fh.open()
        self.setInputStream(encoder.encode(pkt.media.getStream().getDecoder().decode(fh)))
        self.setSize(pkt.media.getStream().getSize())
        self.startStreaming()
        
    @modulation.input(modulation.controls.Start)
    def play(self, pkt):
        """Begins streaming"""
        self.startStreaming()