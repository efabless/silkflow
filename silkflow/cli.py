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

from .vpr import run_genfasm, run_vpr, device_base
from .util import r, d2nt, mkdirp, extract_pixz, NonZeroExit
from .file import FileManager
from .error import eprint, ErrorReporter
from .__init__ import __version__

import click

import io
import os 
import re
import sys
import argparse
import tempfile
import traceback
import subprocess
import functools
from timeit import default_timer as timer

arch = os.environ.get("SYMBIFLOW_ARCH") or "ice40"
symbiflow_base_dir = os.getenv("SYMBIFLOW_BASE") or "/opt/symbiflow"

fm = FileManager(symbiflow_base_dir, os.getenv("SILKFLOW_PIXZ_ARCHIVE"))
er = ErrorReporter()
current_project = os.path.basename(os.getcwd())

class sio(object):
    def __init__(self):
        self.file = tempfile.TemporaryFile(mode='w+')
    
    def close(self):
        self.file.seek(0)
        final = self.file.read()
        self.file.close()
        return final

def handle_yosys_stderr(stderr, input_files=[]):
    file_error_rx = r"((?:[\w\.\-\:\/]+).v):(\d+)"
    warning_line_rx = r"warning\s*\:\s*[\s\S]*"

    for line in stderr.split("\n"):
        if line.strip() == "":
            continue
            
        warning = bool(re.match(warning_line_rx, line, flags=re.I))

        message = line
        file = None
        line_no = None

        result = re.match(file_error_rx, line)
        if result is not None and result[1] in input_files:
            file = result[1]
            line_no = int(result[2])

        er.add(warning, message, file, line_no)

def run_yosys_cmd(cmd, input_files=[], **kwargs):
    stderr = sio()
    try:
        r(cmd, **kwargs, stderr=stderr.file)
        stderr = stderr.close()
        handle_yosys_stderr(stderr, input_files)
    except NonZeroExit:
        stderr = stderr.close()
        handle_yosys_stderr(stderr, input_files)
        er.report()
        exit(65)

def synth_fn(top_module, device, part, prxray_device, xdc_files, verilog_files):
    COMMAND_NAME = "synth"

    if type(xdc_files) == str:
        xdc_files = xdc_files.split(":")

    log_file = "%s_%s.log" % (current_project, COMMAND_NAME)
    output_json = "%s_%s.json" % (current_project, COMMAND_NAME)
    output_verilog = "%s_%s.v" % (current_project, COMMAND_NAME)
    output_eblif = "%s.eblif" % (top_module)

    modified_env = os.environ.copy()
    modified_env["OUT_JSON"] = output_json
    modified_env["OUT_SYNTH_V"] = output_verilog
    modified_env["OUT_EBLIF"] = output_eblif
    modified_env["TOP"] = top_module

    if arch == "xc7":
        modified_env["INPUT_XDC_FILE"] = " ".join(xdc_files)
        modified_env["USE_ROI"] = "FALSE"
        modified_env["TECHMAP_PATH"] = fm.get_techmap_path(arch)

        database_dir = r(["prjxray-config"], pipe_stdout=True).strip()
        modified_env["PART_JSON"] = os.path.join(database_dir, prxray_device, part, "part.json")

        modified_env["OUT_FASM_EXTRA"] = "%s_fasm_extra.fasm" % top_module
        modified_env["OUT_SDC"] = "%s.sdc" % top_module

        modified_env["PYTHON3"] = sys.executable
        modified_env["UTILS_PATH"] = fm.scripts
        
    run_yosys_cmd([
        "yosys",
        "-Q", "-q",
        "-p", "tcl %s" % fm.get_yosys_script(arch, "synth.tcl"),
        "-l", log_file,
        *verilog_files
    ], env=modified_env, input_files=verilog_files)

    final_output_json = "%s.json" % top_module
    r([
        "python3",
        fm.get_script("split_inouts.py"),
        "-i", output_json,
        "-o", final_output_json 
    ], env=modified_env)

    run_yosys_cmd([
        "yosys",
        "-Q", "-q",
        "-p", "read_json %s; tcl %s" % (final_output_json, fm.get_yosys_script(arch, "conv.tcl"))
    ], env=modified_env)

    return d2nt({
        "json": final_output_json,
        "eblif": output_eblif
    })

def pack_fn(top_module, device, eblif, part, pcf, net, sdc):
    COMMAND_NAME = "pack"
    
    noisy_warnings_log = "%s_noisy_warnings_%s.log" % (current_project, COMMAND_NAME)
    stdout_log = "%s_%s.log" % (current_project, COMMAND_NAME)
    
    run_vpr(top_module, arch, device, eblif, sdc, fm, ["--pack"], noisy_warnings_log, stdout_log)

    return "%s.net" % top_module

def generate_constraints_fn(top_module, device, eblif, part, pcf, net, sdc):
    COMMAND_NAME = "generate_constraints"

    pcf_options = []
    if pcf is not None:
        pcf_options = ["--pcf", pcf]

    arch_info = fm.get_arch_info(arch, device)
    pin_map = arch_info.pinmap(for_part=part)

    python_env = fm.get_python_env(arch)

    if arch == "ice40":
        iogen_script = fm.get_arch_script(arch, "ice40_create_ioplace.py")
        ioplace_file = "%s.io.place" % current_project
        
        r([
            "python3",
            iogen_script,
            "--blif", eblif,
            "--net", net,
            "--map", pin_map
        ] + pcf_options + [
            "--out", ioplace_file
        ], env=python_env)

        return ioplace_file
    elif arch == "xc7":
        vpr_grid_map = arch_info.vpr_grid_map

        iogen_script = fm.get_script("prjxray_create_ioplace.py")
        constraint_gen_script = fm.get_script("prjxray_create_place_constraints.py")

        ioplace_file = "%s.ioplace" % current_project

        ioplace_data = r([
            "python3",
            iogen_script,
            "--blif", eblif,
            "--net", net,
            "--map", pin_map
        ] + pcf_options, env=python_env,pipe_stdout=True)

        with open(ioplace_file, 'w') as f:
            f.write(ioplace_data)

        constraints_file = "%s_constraints.place" % current_project
        constraints_data = r([
            "python3",
            constraint_gen_script,
            "--blif", eblif,
            "--net", net,
            "--vpr_grid_map", vpr_grid_map,
            "--input", ioplace_file,
            "--arch", arch_info.definition
        ], env=python_env, pipe_stdout=True)

        with open(constraints_file, 'w') as f:
            f.write(constraints_data)

        return constraints_file

def place_fn(top_module, device, eblif, part, pcf, net, sdc):
    COMMAND_NAME = "place"
    
    noisy_warnings_log = "%s_noisy_warnings_%s.log" % (current_project, COMMAND_NAME)
    stdout_log = "%s_%s.log" % (current_project, COMMAND_NAME)
    
    eprint("Generating constraints…")
    constraints_file = generate_constraints_fn(top_module, device, eblif, part, pcf, net, sdc)

    run_vpr(top_module, arch, device, eblif, sdc, fm, ["--fix_clusters", constraints_file, "--place"], noisy_warnings_log, stdout_log)

def route_fn(top_module, device, eblif, part, pcf, net, sdc):
    COMMAND_NAME = "route"
    
    noisy_warnings_log = "%s_noisy_warnings_%s.log" % (current_project, COMMAND_NAME)
    stdout_log = "%s_%s.log" % (current_project, COMMAND_NAME)
    
    run_vpr(top_module, arch, device, eblif, sdc, fm, ["--route"], noisy_warnings_log, stdout_log)

def write_fasm_fn(top_module, device, eblif, part, pcf, net, sdc):
    COMMAND_NAME = "write_fasm"
    
    noisy_warnings_log = "%s_noisy_warnings_%s.log" % (current_project, COMMAND_NAME)
    stdout_log = "%s_%s.log" % (current_project, COMMAND_NAME)
    
    run_genfasm(top_module, arch, device, eblif, fm, [], noisy_warnings_log, stdout_log)

    fasm = "%s.fasm" % top_module
    fasm_extra = "%s_fasm_extra.fasm" % top_module
    if os.path.exists(fasm_extra):
        eprint("Found fasm extra, concatenating with existing result…")

        fasm_data = open(fasm).read()
        extra_data = open(fasm_extra).read()
        with open(fasm, 'w') as f:
            f.write(fasm_data)
            f.write(extra_data) 

    return fasm

def write_bitstream_fn(top_module, device, pxray_device, bit, fasm, part, frm2bit):
    if arch == "ice40":
        python_env = fm.get_python_env(arch)
        asc_file = "%s.asc" % (top_module)

        start = timer()
        r([
            "python3",
            fm.get_arch_script(arch, "fasm_icebox/fasm2asc.py"),
            "--device", device_base(device),
            fasm,
            asc_file
        ], env=python_env)
        end = timer()
        eprint(">> fasm2asc wasted %f seconds. :)" % (end - start))
        
        bitstream = r([
            "icepack",
            "top.asc"
        ], pipe_stdout=True, binary=True, env=python_env)

        with open(bit, 'wb') as f:
            f.write(bitstream)
    elif arch == "xc7":
        python_env = fm.get_python_env(arch)

        dbroot = r(["prjxray-config"], pipe_stdout=True).strip()
        dbroot = os.path.join(dbroot, pxray_device)

        frm2bit_args = []
        if frm2bit is not None:
            frm2bit_args.append("--frm2bit"),
            frm2bit_args.append(frm2bit)
        
        r([
            "xcfasm",
            "--db-root", dbroot,
            "--part", part,
            "--part_file", "%s/%s/part.yaml" % (dbroot, part),
            "--sparse",
            "--emit_pudc_b_pullup",
            "--fn_in", fasm,
            "--bit_out", bit
        ] + frm2bit_args, env=python_env)
        

# -- CLI --
@click.group()
@click.version_option(prog_name="Silkflow", version=__version__, message="%(prog)s - Version %(version)s\n© efabless Corporation 2021-present. All rights reserved.")
def cli():
    pass

def vpr_options(fn):
    @click.option('-t', '--top-module', required=True, help="Top module")
    @click.option('-D', '--device', required=True)
    @click.option('-e', '--eblif', required=True)
    @click.option('-P', '--part', default=None)
    @click.option('-p', '--pcf', default=None)
    @click.option('-n', '--net', default=None)
    @click.option('-s', '--sdc', default=None)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@click.command('synth', help="Synthesize")
@click.option('-t', '--top-module', required=True, help="Top module")
@click.option('-D', '--device', default=None, help="required if xc7")
@click.option('-P', '--part', default=None, help="required if xc7")
@click.option('-X', '--pxray-device', default=None, help="xc7 only, required - name of the device according to project xray (i.e. artix7, zynq7…)")
@click.option('-x', '--xdc-files', default=None, help="xc7 only - XDC files (comma,separated). File paths may not contain spaces.")
@click.argument('verilog_files', required=True, nargs=-1)
def synth(top_module, device, part, pxray_device, xdc_files, verilog_files):
    return synth_fn(top_module, device, pxray_device, part, xdc_files, verilog_files)
cli.add_command(synth)

@click.command('pack', help="Pack")
@vpr_options
def pack(top_module, device, eblif, part, pcf, net, sdc):
    return pack_fn(top_module, device, eblif, part, pcf, net, sdc)
cli.add_command(pack)

@click.command('generate_constraints', help="Generate constraints")
@vpr_options
def generate_constraints(top_module, device, eblif, part, pcf, net, sdc):
    return generate_constraints_fn(top_module, device, eblif, part, pcf, net, sdc)
cli.add_command(generate_constraints)

@click.command('place', help="Place")
@vpr_options
def place(top_module, device, eblif, part, pcf, net, sdc):
    return place_fn(top_module, device, eblif, part, pcf, net, sdc)
cli.add_command(place)

@click.command('route', help="Route")
@vpr_options
def route(top_module, device, eblif, part, pcf, net, sdc):
    return route_fn(top_module, device, eblif, part, pcf, net, sdc)
cli.add_command(route)

@click.command('write_fasm', help="Write FASM")
@vpr_options
def write_fasm(top_module, device, eblif, part, pcf, net, sdc):
    return write_fasm_fn(top_module, device, eblif, part, pcf, net, sdc)
cli.add_command(write_fasm)

@click.command('write_bitstream', help="Write bitstream")
@click.option('-t', '--top-module', required=True, help="Top module")
@click.option('-D', '--device', required=True)
@click.option('-X', '--pxray-device', default=None, help="xc7 only, required - name of the device according to project xray (i.e. artix7, zynq7…)")
@click.option('-b', '--bit', required=True)
@click.option('-f', '--fasm', required=True)
@click.option('-P', '--part', default=None)
@click.option('-F', '--frm2bit', default=None, help="xc7 only - frames to bit file")
def write_bitstream(top_module, device, pxray_device, bit, fasm, part, frm2bit):
    return write_bitstream_fn(top_module, device, pxray_device, bit, fasm, part, frm2bit)
cli.add_command(write_bitstream)

@click.command('run', help="Full flow")
@click.option('-t', '--top-module', required=True, help="Top module")
@click.option('-b', '--bit', required=True, help="Name of the bitstream output")
@click.option('-D', '--device', required=True)
@click.option('-P', '--part', required=True)
@click.option('-X', '--pxray-device', default=None, help="xc7 only, required - name of the device according to project xray (i.e. artix7, zynq7…)")
@click.option('-p', '--pcf', default=None, help = "Pin constraints file. One of -p or -x are required.")
@click.option('-x', '--xdc-files', default=None, help="xc7 only - XDC files (comma,separated). File paths may not contain spaces. One of -p or -x are required.")
@click.option('-F', '--frm2bit', default=None, help="xc7 only - frames to bit file")
@click.argument('verilog_files', required=True, nargs=-1)
def run(top_module, device, part, pxray_device, pcf, bit, xdc_files, verilog_files, frm2bit):
    start = timer()
    eprint("Starting flow…")

    eprint("\n---\n")

    eprint("Synthesizing…")
    synth_out = synth_fn(top_module, device, part, pxray_device, xdc_files, verilog_files)
    eblif = synth_out.eblif

    eprint("Packing…")
    net = pack_fn(top_module, device, eblif, part, pcf, None, None)

    eprint("Placing…")
    place_fn(top_module, device, eblif, part, pcf, net, None)

    eprint("Routing…")
    route_fn(top_module, device, eblif, part, pcf, net, None)

    eprint("Writing FASM…")
    fasm = write_fasm_fn(top_module, device, eblif, part, pcf, net, None)

    eprint("Writing bitstream…")
    write_bitstream_fn(top_module, device, pxray_device, bit, fasm, part, frm2bit)

    end = timer()
    eprint("Bitstream generated in %fs." % (end-start))
    er.report()
cli.add_command(run)

@click.command('setup', help='Setup environment from .pixz file')
@click.option('-i', '--install-dir', required=True)
@click.option('-f', '--family', required=True)
@click.argument('pixz_archive', required=True, nargs=1)
def setup(install_dir, family, pixz_archive):
    family_path = os.path.join(install_dir, family)
    env_yaml = os.path.join(family_path, "environment.yml")
    rc_file = os.path.join(family_path, ".rc")
    base_path = os.path.join(family_path, "install")
    bin_file_path = os.path.join(base_path, "bin")

    archive_realpath = os.path.realpath(pixz_archive)

    pixz_list = r(["pixz", "-l", pixz_archive], pipe_stdout=True).strip().rstrip().split("\n")

    pixz_extractable = list(filter(lambda x: not x.endswith("/") and not x.startswith("install/share/symbiflow/arch/"), pixz_list)) 

    extract_pixz(pixz_archive, family_path, pixz_extractable)

    r([
        "conda", "env", "create", "--verbose", "-f",
        env_yaml
    ])

    with open(rc_file, "w") as f:
        f.write("# AUTOGENERATED BY SILKFLOW\n")

        f.write("source $HOME/.bashrc\n")
        f.write("export PATH=%s:$PATH\n" % bin_file_path)
        f.write("export SYMBIFLOW_ARCH=%s\n" % family)
        f.write("export SYMBIFLOW_BASE=%s\n" % base_path)
        f.write("export SILKFLOW_PIXZ_ARCHIVE=%s\n" % archive_realpath)

        f.write("conda activate %s\n" % family)

    eprint("Done!")
cli.add_command(setup)

def main():
    try:
        if arch not in ["ice40", "xc7"]:
            er.add_error("FPGA family %s is currently unsupported by Silkflow." % arch).report()
            exit(64)
        cli()
    except NonZeroExit:
        eprint(traceback.format_exc())
        er.add_error("A Symbiflow command has unexpectedly failed.").report()
        exit(69)
    except Exception:
        eprint(traceback.format_exc())
        er.add_error("An unexpected exception has occurred with Silkflow.").report()
        exit(69)

if __name__ == '__main__':
    main()
