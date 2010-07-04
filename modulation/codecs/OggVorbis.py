# -*- coding: utf-8 -*-
import modulation.codecs as codecs
import subprocess
class OggVorbis(codecs.FileEncoder, codecs.FileDecoder):
    types = ["application/ogg"]
    def decode(self, input):
        proc = subprocess.Popen(("oggdec", "-Q", "/dev/stdin", "-o", "/dev/stdout"), stdout=subprocess.PIPE, stdin=input)
        return proc.stdout

    def encode(self, input):
        metadata = self.getMetadata()
        args = ("oggenc", "-Q", "-")
        if ('title' in metadata):
            args += ("-t", metadata['title'])
        if ('artist' in metadata):
            args += ('-a', metadata['artist'])
        if ('bitrate' in metadata):
            args+= ('-b', str(metadata['bitrate']))
            if (metadata['bitrate'] < 64):
                args += ('--downmix',)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=input)
        return proc.stdout

codecs.registerEncoder(OggVorbis)
codecs.registerDecoder(OggVorbis)
