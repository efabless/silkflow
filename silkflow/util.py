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
from collections import namedtuple

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def r(cmd, pipe_stdout=False, binary=False, **kwargs):
    stdout = None
    if pipe_stdout:
        stdout = subprocess.PIPE
    result = subprocess.run(cmd, stdout=stdout, **kwargs)
    if result.returncode != 0:
        eprint("Command had a non-zero exit: " + " ".join(cmd))
        raise Exception("Command had a non-zero exit.")
    if pipe_stdout:
        if binary:
            return result.stdout
        else:
            return result.stdout.decode("utf-8")

def d2nt(dictionary):
    return namedtuple('result', dictionary.keys())(**dictionary)

def extract_pixz(archive, extraction_path, files):
    pixz_file = open(archive)

    extraction_array = []
    for file in files:
        extraction_array.append("-x")
        extraction_array.append(file)

    tarball = r([
        "pixz",
    ] + extraction_array, pipe_stdout=True, binary=True, stdin=pixz_file)

    tar_process = subprocess.Popen([
        "tar",
        "-x",
        "-C", extraction_path
    ], stdin=subprocess.PIPE)

    tar_process.stdin.write(tarball)
    tar_process.stdin.close()

    tar_process.wait()
