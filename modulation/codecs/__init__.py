# -*- coding: utf-8 -*-
__encoders__ = []
__decoders__ = []

def registerDecoder(codec):
    __decoders__.append(codec)

def registerEncoder(codec):
    __encoders__.append(codec)

def getDecoder(mime):
    for codec in __decoders__:
        if mime in codec.types:
            return codec()

def getEncoder(mime):
    for codec in __encoders__:
        if mime in codec.types:
            return codec()

class FileDecoder(object):
    def decode(self, file):
        raise NotImplementedError

class FileEncoder(object):
    def __init__(self):
        self.__bitrate = -1
        self.__meta = []
    def setBitrate(self, bitrate):
        self.__bitrate = bitrate
    def getBitrate(self):
        return self.__bitrate
    def setMetadata(self, meta):
        self.__meta = meta
    def getMetadata(self):
        return self.__meta
    def encode(self, input):
        raise NotImplementedError

#Load the system codecs
#import modulation.codecs.MP3
#import modulation.codecs.OggVorbis
#import modulation.codecs.Raw