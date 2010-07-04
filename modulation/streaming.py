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
from modulation import Packet, Plugin
import modulation.codecs
import os
import magic

import logging

class StreamPacket(Packet):
    """Base class for stream-related status updates"""
    pass

class StreamProgressPacket(StreamPacket):
    """Sent whenever media is streamed. Contains current progress"""
    def __init__(self, origin, value, max=1):
        StreamPacket.__init__(self, origin)
        self.__value = value
        self.__max = max

    def getValue(self):
        return self.__value

    def getMax(self):
        return self.__max

    def getPercent(self):
        try:
            return self.__value/self.__max
        except ZeroDivisionError, e:
            return 0
            
    value = property(getValue, None, None, "The absolute value")
    
    max = property(getMax, None, None, "The absolute maximum value")
    
    percent = property(getPercent, None, None, "The relative progress value")

class DataStream(object):
    """Base class for data streams
    
    Data streams can be any kind of media stream i.e. an ogg file, a mkv video, or a png image
    """
    def getStream(self):
        """Must return an independent copy of the underlying data stream."""
        raise NotImplementedError
        
    def open(self):
        """Opens the stream for reading or writing"""
        raise NotImplementedError
        
    def write(self, buf):
        """Writes data to the stream"""
        raise NotImplementedError
        
    def read(self, size):
        """Reads data from the stream"""
        raise NotImplementedError
        
    def close(self):
        """Closes the stream"""
        raise NotImplementedError
        
    def getDecoder(self):
        """Must return the decoder"""
        raise NotImplementedError
        
    def getEncoder(self):
        """Must return the encoder"""
        raise NotImplementedError
        
    def getSize(self):
        raise NotImplementedError
        

    @property
    def closed(self):
        raise NotImplementedError

class URLStream(DataStream):
    """A DataStream for a URLObject"""
    def __init__(self, url):
        super(URLStream, self).__init__(self)
        self.__url = url
        self.__stream = None

    def open(self):
        self.__stream = urllib2.urlopen(self.__url)
        
    def close(self):
        self.__stream.close()
    
    def read(self, size):
        return self.__stream.read(size)
            
    def write(self, buf):
        return self.__stream.write(buf)
        
    def getSize(self):
        if ('content-length' in self.__stream.headers):
            return int(self.__stream.headers['content-length'])
        return -1
        
    def getDecoder(self):
        return modulation.codecs.getDecoder(self.__stream.headers['content-type'])
        
    @property
    def closed(self):
        return not (self.__stream is None)

class FileStream(DataStream):
    """A DataStream for a FileObject"""
    def __init__(self, file):
        DataStream.__init__(self)
        self.__file = file
        self.__fh = None

    def getDecoder(self):
        c = magic.open(magic.MAGIC_MIME)
        c.load()
        type = c.file(self.__file).split(';')[0]
        return modulation.codecs.getDecoder(type)

    def open(self):
        self.__fh = open(self.__file, "r")

    def fileno(self):
        return self.__fh.fileno()

    def close(self):
        self.__fh.close()

    def read(self, size):
        return self.__fh.read(size)

    def write(self, buf):
        return self.__fh.write(buf)

    def getSize(self):
        return os.stat(self.__file).st_size

    def getPath(self):
        return self.__file

    @property
    def closed(self):
        return self.__fh.closed

    path = property(getPath, None, None, "The filesystem path to the file")
