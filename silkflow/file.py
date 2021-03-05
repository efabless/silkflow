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
from .util import d2nt, r, extract_pixz

from halo import Halo

import os

class FileManager(object):
    def __init__(self, symbiflow_base_dir, archive_realpath):
        self.base = symbiflow_base_dir
        self.share = os.path.join(self.base, "share", "symbiflow")

        self.devices = os.path.join(self.share, "devices")

        self.scripts = os.path.join(self.share, "scripts")

        self.archive_realpath = archive_realpath

    def jit_extract(self, files):
        if self.archive_realpath is None:
            return
        extract_path = os.path.dirname(self.base) # The reason for this is the base path points to family_path/install/

        files_filtered = filter(lambda x: not os.path.exists(x), files)
        relative_files = list(map(lambda x: os.path.relpath(x, extract_path), files_filtered))
    
        if len(relative_files) == 0:
            return

        with Halo(text='Extracting arch info…', spinner='dots'):
            extract_pixz(self.archive_realpath, extract_path, relative_files)

    def get_script(self, scr):
        return os.path.join(self.scripts, scr)

    def get_arch_script_folder(self, arch):
        return os.path.join(self.scripts, arch)

    def get_arch_script(self, arch, scr):
        return os.path.join(self.get_arch_script_folder(arch), scr)

    def get_yosys_script(self, arch, scr):
        return os.path.join(self.scripts, arch, "yosys", scr)

    def get_arch_info(self, arch, device):
        arch_dir = os.path.join(self.devices, arch)
        if arch == "ice40":
            device_dotted = ".".join(device.split("-"))
            device_underscored = "_".join(device.split("-"))
            def pinmap(for_part): # This is a function as some other architectures factor the part in.
                device_pinmap = os.path.join(arch_dir, "layouts", "icebox", "%s.pinmap.csv" % device_dotted)
                self.jit_extract([device_pinmap])
                return device_pinmap

            architecture_data = {
                "definition": os.path.join(arch_dir, "top-routing-virt", "arch.timing.xml"),
                "rr_graph": os.path.join(arch_dir, "rr_graph_%s.rr_graph.real.bin" % device_underscored),
                "place_delay": os.path.join(arch_dir, "rr_graph_%s.place_delay.bin" % device_underscored),
                # "vpr_grid_map": os.path.join(arch_dir, "vpr_grid_map.csv"),
            }
            
            self.jit_extract(architecture_data.values())

            architecture_data["pinmap"] = pinmap

            return d2nt(architecture_data)
        else:
            raise Exception("Unsupported architecture.")

    def get_python_path(self, arch):
        paths = [self.scripts, self.get_arch_script_folder(arch)]
        if arch == "ice40":
            icebox_result = r([
                "which",
                "icebox.py"
            ], pipe_stdout=True)
            icebox_path = icebox_result.strip()
            icebox_dir = os.path.dirname(icebox_path)
            paths.append(icebox_dir)
        return ":".join(paths)

    def get_python_env(self, arch):
        env = os.environ.copy()
        env["PYTHONPATH"] = self.get_python_path(arch)
        return env