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

import os
import sys
import subprocess
import pathlib
from collections import namedtuple

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class NonZeroExit(Exception):
    def __init(self, ec):
        self.ec = (ec & 255)

    def __str__(self):
        return "Command had a non-zero exit (%i)" % self.ec

# To silence stderr, pass it the expression open(os.devnull, "w")
def r(cmd, pipe_stdout=False, binary=False, stdout=None, stderr=None, **kwargs):
    if pipe_stdout: # Overrides stdout option
        stdout = subprocess.PIPE
    result = subprocess.run(cmd, stdout=stdout, stderr=stderr, **kwargs)
    if result.returncode != 0:
        eprint(("Command had a non-zero exit (%i): " % (result.returncode & 255)) + " ".join(cmd) )
        raise NonZeroExit(result.returncode)
    if pipe_stdout:
        if binary:
            return result.stdout
        else:
            return result.stdout.decode("utf-8")

def d2nt(dictionary):
    return namedtuple('result', dictionary.keys())(**dictionary)

def mkdirp(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

def extract_pixz(archive, extraction_path, files):
    pixz_file = open(archive)

    mkdirp(extraction_path)

    tarball = r([
        "pixz",
        "-x"
    ] + files, pipe_stdout=True, binary=True, stdin=pixz_file)

    tar_process = subprocess.Popen([
        "tar",
        "-x",
        "-C", extraction_path
    ], stdin=subprocess.PIPE)

    tar_process.stdin.write(tarball)
    tar_process.stdin.close()

    tar_process.wait()
