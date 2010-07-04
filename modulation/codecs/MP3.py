# -*- coding: utf-8 -*-
import modulation.codecs
import subprocess
class MP3(modulation.codecs.FileEncoder, modulation.codecs.FileDecoder):
    types = ["audio/mpeg"]
    def encode(self, input, metadata):
        ### TODO: Metadata
        proc = subprocess.Popen(("lame", "-", "-"), stdin=input)
    def decode(self, input):
        proc = subprocess.Popen(("mpg321", "-q", "-s", "-"), stdin=input, stdout=subprocess.PIPE)
        return proc.stdout

modulation.codecs.registerEncoder(MP3)
modulation.codecs.registerDecoder(MP3)
