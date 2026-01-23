# ASHRAE Guideline 36 conformance Test

The American Society of Heating, Refrigerating and Air-Conditioning Engineers (ASHRAE) has established a set of standardized high performance sequences of operation for Heating, Ventilation and Air Conditioning (HVAC) systems in buildings through their "Guideline 36". In order to achieve the intended performance, these sequences must be translated and programmed accurately in the Building Automation System (BAS) controllers. Standardizing these sequences will allow for a more efficient product delivery mechanism where the sequences are programmed and tested centrally by each manufacturer, and then distributed to their dealers/engineering contractors. This approach would minimize the need for each installer to re-interpret and program the sequences, reduces risk of errors, and reduces the time required for commissioning in the field. 

To achieve this goal, a performance validation method is needed to provide independent confirmation that each manufacturer has programmed the Guideline 36 sequences accurately. A standardized method of test would also avoid the need for manual interpretation (and the associated human variability) that is required with typical functional testing approaches by automating the inputs and the range of expected responses. 

This software has been developed to conduct standardized, repeatable and manufacturer independent tests to validate that a BAS controller has been programmed in conformance with Guideline 36. Manufacturers would provide the controller (or the control program) and the software would run a suite of tests by setting a set of inputs to the controller and verifying the output signals from the controller matches the expected output as set by Guideline 36.


## Getting Started for a CDL Simulation Device

### Using Docker Compose
Install [Docker](https://www.docker.com/). Then, the following.

1. Build the ``simulation`` image (if first time) and run container in detached mode: 

    ```
    $ docker compose up simulation -d
    ```

2. Attach to the container interactively in the right working directory: 

    ```
    $ docker compose exec -w /mnt/shared simulation bash
    ```

3. Run a test(s) as described in the section "Run a Test."

4. Exit the container: ``ctrl+d``

5. Stop and remove the container: 

    ```
    $ docker compose down
    ```

### If Not Docker Compose or Want Customized Environment

1. Install Python3.  Recommend using Anaconda (easier installation of pyfmi).

2. Install Python packages listed in ``requirements/simulation.txt``.

3. Install [OpenModelica](https://openmodelica.org/) v1.25.0.

    - Note: there is a further dependency of the [Modelica Buildings Library](https://simulationresearch.lbl.gov/modelica/index.html).  OpenModelica already has access to the default version used in this software (v11.0.0).  However, if want to use a custom version of Modelica Buildings Library, it requires downloading or cloning the library and minor edits to `src/DeviceSimcdl.py` in function `DeviceSimcdl._compile_fmu()` to point to its path.

### Run a Test

1. Set up global configuration:

    - Copy `config/global_config_template.yaml` to `config/global_config.yaml` and fill in:
        - `test_type`: which conformance test to run (e.g., `vav_rh`)
        - `device_type`: `simulation` or `bacnet`
        - `test_runner` options: `save_csv`, `print_output`, `reset_points`

2. Configure the specific test:

    - Copy `conformance_tests/{test_type}/config/config_template.yaml` to `config.yaml` in the same directory and fill in:
        - Device settings for both simulation and bacnet
        - Test script filename
        - Point mapping file path

3. Prepare test files:

    - Save test script (Excel file) to `conformance_tests/{test_type}/test_scripts/`
    - Save point mapping file (CSV) to `conformance_tests/{test_type}/config/`
    - For simulation: place Modelica (.mo) or FMU files in `conformance_tests/{test_type}/simulation_files/`

4. Run the test:

    ```
    $ python src/Test.py
    
    # Optional command-line arguments:
    # --csv                  Save outputs to CSV
    # --name <test_name>     Specify output filename prefix
    # --reset                Reset points before test
    # --output               Print current values without running
    ```

Results will be saved to `conformance_tests/{test_type}/results/`

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
