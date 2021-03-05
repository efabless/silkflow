#!/usr/bin/env python3

# Copyright 2021 efabless Corporation
#
# Author: Mohamed Gaber <mohamed.gaber@efabless.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from setuptools import setup, find_packages
from setuptools.command.install import install
import platform

from silkflow.__init__ import __version__

if sys.version_info < (3,5):
    sys.exit('Python 3.5+ is required')

kwargs = dict(
    name='silkflow',
    packages=find_packages(),
    version=__version__,
    description='efabless Silkflow',
    long_description='',
    author='Mohamed Gaber',
    author_email='mohamed.gaber@efabless.com',
    install_requires=[
        "click",
        "halo"
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Development Status :: Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
    ],
    entry_points={
        'console_scripts': [
            'silkflow = silkflow.cli:main'
        ]
    }
)


setup(**kwargs)
