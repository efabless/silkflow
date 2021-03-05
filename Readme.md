# Silkflow BETA
A saner, python-based utility for working with Symbiflow scripts, binaries and architecture definitions.

# Requirements
* GNU/Linux - A number of the dependent conda packages don't support macOS and none of them support Microsoft Windows.
* Miniconda - https://docs.conda.io/en/latest/miniconda.html < This requires like 10 GB free space
* Pixz - https://github.com/vasi/pixz

# Installation & Usage
Ensure that conda and pixz are set up and in PATH. Make sure conda is also initialized: type `bash -c "conda init"` just to be sure.

First, install silkflow:
```sh
python3 -m pip install git+https://github.com/efabless/silkflow
```

First, get a silkflow-compatible .tar.pixz file: you can find some at https://github.com/donn/symbiflow-arch-def-artifacts/releases.

Then, set up the environment using this command:
```sh
silkflow --install-dir ~/symbiflow --family <name-of-family> /path/to/<name-of-family>.tar.pixz
# Where name of family is the name of the FPGA family in use, example: ice40, xc7, etc…
```

Next, go get a coffee. Seriously. This takes like 10 minutes.

After that you can type `bash --rcfile ~/symbiflow/<name-of-family>/.rc` to open a shell with the necessary environment variables.

Then you can invoke silkflow's other subcommands: type `silkflow --help` for help.

# Copyright & License
All rights reserved ©2021-present efabless Corporation. Available under the Apache License v2.0: see 'LICENSE'.