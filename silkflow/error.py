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

import json
import sys
import os

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class ErrorReporter(object):
    def __init__(self):
        self.all = []
        self.errors = []
        self.warnings = []

    def add(self, warning, message, file=None, line=None):
        entry = {
            "file": file,
            "line": line,
            "message": message
        }
        (self.warnings if warning else self.errors).append(entry)
        self.all.append(entry)
        return self
        
    def add_warning(self, message, file=None, line=None):
        return self.add(True, message, file, line)

    def add_error(self, message, file=None, line=None):
        return self.add(False, message, file, line)

    def report(self):
        for entry in self.all:
            eprint(entry["message"])
        eprint("PRINTJSONERRORS", os.getenv("PRINT_JSON_ERRORS"))
        if os.getenv("PRINT_JSON_ERRORS") == "1":
            print(json.dumps({
                "errors": self.errors,
                "warnings": self.warnings
            }))
        return self

