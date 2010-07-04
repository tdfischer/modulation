#!/usr/bin/env python
#from distutils.core import setup
from setuptools import setup, find_packages

setup(
	name = "modulation",
	packages = find_packages(),
	version = '0.1',
	description = 'Universal Media server',
	author = 'Trever Fischer',
	author_email = 'tdfischer@fedoraproject.org',
	url = 'http://gitorious.org/modulation',
	license = 'GPL',
	install_requires = [
		'tagpy>=0.94.5',
		'python-musicbrainz2>=0.7.0',
		'shoutpy>=1',
	],
	classifiers = [
		'Development Status :: 2 - Pre-Alpha',
		'Environment :: No Input/Output (Daemon)',
		'Intended Audience :: Developers',
		'Intended Audience :: End Users/Desktop',
		'License :: OSI Approved :: GNU General Public License (GPL)',
		'Natural Language :: English',
		'Operating System :: POSIX :: Linux',
		'Programming Language :: Python',
		'Topic :: Communications :: File Sharing',
		'Topic :: Multimedia :: Graphics',
		'Topic :: Multimedia :: Sound/Audio',
		'Topic :: Multimedia :: Video'
	])
