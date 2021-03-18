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

from .util import r, eprint
import os

def get_options(tool, arch, out_noisy_warnings):
    common = [
            "--suppress_warnings", out_noisy_warnings,

            "--max_router_iterations", "500",
            "--routing_failure_predictor", "off",
            "--router_high_fanout_threshold", "-1",
            "--constant_net_method", "route",
            "--clock_modeling", "route",
            "--route_chan_width", "100",
            "--congested_routing_iteration_threshold", "0.8",
            "--check_rr_graph", "off",
    ]
    if arch == "ice40":
        eprint("WARNING: VPR and genfasm are unverified for FPGA family %s" % arch)
        return common + [
            "--router_init_wirelength_abort_threshold", "2",
            "--allow_unrelated_clustering", "off",
            "--target_ext_pin_util", "0.5",
            "--astar_fac", "1.0",
        ]
    elif arch == "xc7":
        eprint("WARNING: VPR and genfasm are unverified for FPGA family %s" % arch)
        return common + [
            "--place_delay_model", "delta_override",
            "--router_lookahead", "map",
            "--check_route", "quick",
            "--strict_checks", "off",
            "--allow_dangling_combinational_nodes", "on",
            "--disable_errors", "check_unbuffered_edges:check_route",
            "--incremental_reroute_delay_ripup", "off",
            "--base_cost_type", "delay_normalized_length_bounded",
            "--bb_factor", "10",
            "--initial_pres_fac", "4.0"
                        #"sum_pin_class:check_unbuffered_edges:load_rr_indexed_data_T_values:check_rr_node:trans_per_R:check_route:set_rr_graph_tool_comment:warn_model_missing_timing"
        ]


def device_base(device):
    return device.split("-")[0]

def run_vpr(top_module, arch, device, eblif, sdc, sfpath, args, noisy_warnings_log, stdout_log, env=None):
    used_env = env or os.environ
    env_modification = used_env.copy()
    env_modification["TOP"] = top_module

    sdc_arg = []
    if sdc is not None:
        sdc_arg = ["--sdc", sdc_arg]

    device_name = device

    arch_info = sfpath.get_arch_info(arch, device)
    r(
        [
            "vpr",
            arch_info.definition,
            eblif,
            "--device", device,
            "--read_rr_graph", arch_info.rr_graph,
            "--read_placement_delay_lookup", arch_info.place_delay   
        ] + get_options("vpr", arch, noisy_warnings_log) + sdc_arg + args,
        pipe_stdout=True,
        env=env_modification
    )
    r(["mv", "vpr_stdout.log", stdout_log])

def run_genfasm(top_module, arch, device, eblif, sfpath, args, noisy_warnings_log, stdout_log, env=None):
    used_env = env or os.environ
    env_modification = used_env.copy()
    env_modification["TOP"] = top_module

    arch_info = sfpath.get_arch_info(arch, device)
    r(
        [
            "genfasm",
            arch_info.definition,
            eblif,
            "--device", device,
            "--read_rr_graph", arch_info.rr_graph
        ] + get_options("genfasm", arch, noisy_warnings_log) + args,
        pipe_stdout=True,
        env=env_modification
    )
    r(["mv", "vpr_stdout.log", stdout_log])
    