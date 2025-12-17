# ASHRAE Guideline 36 conformance Test

The American Society of Heating, Refrigerating and Air-Conditioning Engineers (ASHRAE) has established a set of standardized high performance sequences of operation for Heating, Ventilation and Air Conditioning (HVAC) systems in buildings through their "Guideline 36". In order to achieve the intended performance, these sequences must be translated and programmed accurately in the Building Automation System (BAS) controllers. Standardizing these sequences will allow for a more efficient product delivery mechanism where the sequences are programmed and tested centrally by each manufacturer, and then distributed to their dealers/engineering contractors. This approach would minimize the need for each installer to re-interpret and program the sequences, reduces risk of errors, and reduces the time required for commissioning in the field. 

To achieve this goal, a performance validation method is needed to provide independent confirmation that each manufacturer has programmed the Guideline 36 sequences accurately. A standardized method of test would also avoid the need for manual interpretation (and the associated human variability) that is required with typical functional testing approaches by automating the inputs and the range of expected responses. 

This software has been developed to conduct standardized, repeatable and manufacturer independent tests to validate that a BAS controller has been programmed in conformance with Guideline 36. Manufacturers would provide the controller (or the control program) and the software would run a suite of tests by setting a set of inputs to the controller and verifying the output signals from the controller matches the expected output as set by Guideline 36.


## Installation for a CDL Simulation Device
### Using Docker Compose
First build the ``simulation`` image (if first time) and run container in detached mode: ``$ docker compose up simulation -d``

Then interactively attach to the ``simulation`` container in the right working directory: ``$ docker compose exec -w /mnt/shared simulation bash``

Run a test(s) as described in the section "Run a Test."

Exit the container: ``ctrl+d``

Stop and remove the ``simulation`` container: ``$ docker compose down``.

### Set Up Environment Manually (if not Docker Compose or want to customize)
Install Python3.  Recommend using Anaconda (easier installation of pyfmi).

Install Python packages listed in ``requirements.txt``.

Install [OpenModelica](https://openmodelica.org/) v1.25.0.

- Note: there is a further dependency of the [Modelica Buildings Library](https://simulationresearch.lbl.gov/modelica/index.html).  OpenModelica already has access to the default version used in this software (v11.0.0).  However, if want to use a custom version of Modelica Buildings Library, it requires downloading or cloning the library and minor edits to `src/DeviceSimcdl.py` in function `DeviceSimcdl._compile_fmu()` to point to its path.

## Run a Test
### Configure the test
Save test script to `files/` and save point map to `files/simcdl/`.

Copy `src/config_template_simcdl.yaml` to `src/config.yaml` (or custom name) and fill in the necessary configuration information.

Configure `src/Test.py` function `__main__` to use `src/config.yaml` (or custom name), upon instantiation of `Test`.

### Start the test
Run the test: `$ python src/Test.py`


## Copyright Notice

Guideline 36 Conformance Test Copyright (c) 2019 to 2025, The Regents of the University of California through Lawrence Berkeley National Laboratory, and Battelle Memorial Institute through Pacific Northwest National Laboratory (both subject to receipt of any required approvals from the U.S. Dept. of Energy).
All rights reserved.

If you have questions about your rights to use or distribute this software,
please contact Berkeley Lab's Intellectual Property Office at
IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department
of Energy and the U.S. Government consequently retains certain rights.  As
such, the U.S. Government has been granted for itself and others acting on
its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the
Software to reproduce, distribute copies to the public, prepare derivative 
works, and perform publicly and display publicly, and to permit others to do so.

## License

Guideline 36 Conformance Test is available under the following [license](https://github.com/LBNL-ETA/guideline36_conformance_test/blob/master/LICENSE.txt).

## Development and contribution

You may report any issues with using the [Issues](https://github.com/LBNL-ETA/guideline36_conformance_test/issues) button.

Contributions in the form of Pull Requests are always welcome.
